# Copyrite (c) 2017, 2020, Lei Wang
# All rights reserved.
# Author yiak.wy@gmail.com
#  Updated on Dec 25, 2020
#     1. fea(async_urlopen): add support to websites with Protocol HTTPS, [M2] refactored to baidu CodeMaster competition
#  Updated on Feb 20, 2021
#     1. optimize(aysnc_urlopen): optimize reading speed for SSL non-blocking socket
# reference:
#     1. https://stackoverflow.com/questions/28508374/ssl-connect-for-non-blocking-socket
#     2. https://github.com/darrenjs/openssl_examples
#     3.

import os
import logging
_logger = logging.getLogger("downloader/handlers/async_socket_http11")
import utils.Log as Log
import time

try:
    from urllib.request import urlopen
except:
    # py2
    from urllib2 import urlopen
# urlparse utility
try:
    from urllib.parse import urlparse, urlencode, quote_plus
except:
    # py2
    from urlparse import urlparse, urlencode, quote_plus
import http

try:
    from asyncio import JoinableQueue as Queue
except ImportError:
    # py35+
    from asyncio import Queue

import ctypes as ct

# multiplexing through python interface
from asyncio import AbstractEventLoop
from selectors import DefaultSelector, EVENT_WRITE, EVENT_READ
import socket, ssl
import selectors
from PIL import Image
import io

from config import settings


# Used inside Response I/O event once async_urlopen builds a connection successfully, yiakwy
PROC_IN_PROGRESS = -1
DEBUG_TIME_ELAPSE = True

def timmer(func):
    def wrapper(*args, **keywords):
        # start time
        start = time.perf_counter()
        # original call
        result = func(*args, **keywords)

        elapse = time.perf_counter() - start

        # errors reporting control
        # later will change it to log version
        if DEBUG_TIME_ELAPSE:
            print(func.__name__, ':\n\tconsumed ', '{0:<2.6f}'.format(elapse), ' seconds')
        return result

    return wrapper

class Handle:
    """
    Callback Wrapper with exception handler
    """

    def __init__(self, cb, *args):
        """
        :param cb: Func, callback function
        :param args: List<Object>, list of arguments to the passed callback function
        """
        self._cb = cb
        self._args = args
        self.logger = Log.LogAdapter(_logger, "Handle <%s>" % cb.__name__)

    def _run(self, fut):
        try:
            self._cb(fut, *self._args)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.logger.info(e)
            raise(e)


# Simple Future class, reference to
# https://github.com/python/cpython/blob/a6fba9b827e395fc9583c07bc2d15cd11f684439/Lib/asyncio/futures.py#L30:7
class Future:
    """
    Callback result and execution address wrapper

    Future is itself "iterable" to enable chainning of calls to "yield" and "yield from".

    Pythonic "yield" and "yield from" keep records of stack frame addresses in user space to jump to and from execution
    places.

    Key members :
      add_done_callback (handle), add a callback wrapper
      remove_done_callback (handle), remove a callback wrapper

      set_ret(ret), store the result retrieved after a callback and execute all callbacks wrapper immediately
      _execute_callbacks : execute callbacks and clear remained tasks.
    """
    
    def __init__(self, *, loop=None):
        """
        :param loop: A async events dispatching query loop
        """
        self._ret = None
        self._callbacks = []
        self._loop = loop
 
    def __iter__(self):
        yield self
        return self._ret

    def cancel(self):
        return True

    def add_done_callback(self, handle):
        self._callbacks.append(handle)

    def remove_done_callback(self, handle):
        if handle in self._callbacks:
            self._callbacks.remove(handle)

    def set_ret(self, ret):
        self._ret = ret
        self._execute_callbacks()

    def _execute_callbacks(self):
        callbacks = self._callbacks[:]
        self._callbacks[:] = []
        for h in callbacks:
            h._run(self)


# stop the task iteration 
class Cancel(Exception):pass 


class Task(Future):
    """
    A special callback result and execution address wrapper:

        The class accepts a special function, which is generator, as callback. Since generator cannot call itself
        automatically. The class works as a driver to drive code forward.

    Key members :

        _step(fut : Future) : when the task is ready (fetched by event loop and set callback result to itself), try to
        drive it to run continuously by issuing "send" -- a special jump to and from a address in user space stacks.
    """

    def __init__(self, coro, *, loop=None):
        super().__init__(loop=loop)
        self._coro = coro
        self._step(self)

    def cancel(self):
        self._coro.throw(Cancel())

    def _step(self, fut):
        """
        :param fut: Task or Future, the task itself or a future fetched after a callback completes
        :return: None
        """
        try:
            ret = self._coro.send(fut._ret)
            if not isinstance(ret, Future) and not hasattr(ret, "add_done_callback"):
                ret0 = ret 
                while True:
                    ret1 = self._coro.send(ret0)
                    if isinstance(ret1, Future):
                        break
                    ret0 = ret1 
        except Cancel:
            # not useful for the moment
            # when user call Task.cancel this will return back to event loop
            self._cancelled = True
            return
        except StopIteration as e:
            self.set_ret(e.value)
            return
        except Exception as e:
            import traceback; traceback.print_exc()
            raise(e)
        h = Handle(self._step)
        if isinstance(ret, Future) or hasattr(ret, "add_done_callback"):
            next_fut = ret
        else:
            next_fut = ret1 
        next_fut.add_done_callback(h)


class StopEventLoop(Exception):pass
class StopImediately(Exception):pass


# https://github.com/python/cpython/blob/a6fba9b827e395fc9583c07bc2d15cd11f684439/Lib/asyncio/base_events.py#L232
class SimpleEventLoop(AbstractEventLoop):
    """
    Implements the interface by standard python 3.6 asyncio library. However we provide much richer I/O processing to natively
    support HTTP/HTTPS with multiplexing technology and run async codes in sequence manner.

    See AbstractEventLoop interface for details of methods to be implemented. Note I didn't implement abstract methods I don't use

    Key members :

        _process_evts(ready_evts : List[Tuple[SelectorKey, _EventMask]]), called when I/O is ready by kernel

    """

    def __init__(self):
        self._stopped = False 
        self._stopping = False
        self._selector = DefaultSelector()
        self.logger = Log.LogAdapter(_logger, "SimpleEventLoop")

    def isStopping(self):
        return self._stopping

    def set_timeout(self, timeout):
        self.timeout = timeout

    def set_stopping(self, fut):
        self._stopping = False if self._stopping else True
        raise StopEventLoop 

    def run_until_complete(self, coro):
        task = Task(coro, loop=self)
        h = Handle(self.set_stopping)
        task.add_done_callback(h)
        try:
            self.run_forever()
        except StopImediately:
            pass 
        except StopEventLoop:
            pass 
        except Exception as e:
            import traceback;traceback.print_exc()
            raise(e)
        finally:
            self.logger.info("The event loop die.")
            task.remove_done_callback(h)

    def run_forever(self):
        while not self.isStopping():
            self._run_once()

    def _run_once(self):
        ready_evts = self._selector.select(self.timeout)
        self._process_evts(ready_evts)
    
    def _process_evts(self, ready_evts):
        """
        :param ready_evts: List[Tuple[SelectorKey, _EventMask]]
        :return:
        """
        for key, mask in ready_evts:
            (reader, writer) = key.data
            if mask & selectors.EVENT_READ and reader is not None:
                reader()
            if mask & selectors.EVENT_WRITE and writer is not None:
                writer()
    
    # used by standard asyncio.Queue
    def create_future(self):
        return Future(loop=self)

    def close(self):
        pass

    def is_closed(self):
        return self._stopped 

    def __del__(self):
        if not self.is_closed():
            self.close()


class Request:
    """
    A simple HTTP Request with customer socket.

    Usually, HTTPRequest in python system library is handling blocked socket, since we are dealing with asynchronous events
    we have to manually process sockets telegraph.

    The key idea is to reuse the parser from HTTPRequest to decode messages while keep a non-blocking socket in use.


    Key Members:

        send(sock, is_secured=False) : send messages to remote
    """

    def __init__(self, method, url, 
            parsed_url=None, headers=None):
        self.url = url 
        self.parsed_url = parsed_url or urlparse(url)
        self.method = method
        self._cert = None

    def send(self, sock, is_secured=False):
        """
        :param sock: Sock or SSLContext.SSLSocket, network device file descriptor
        :param is_secured: is message encrypted
        :return: Response
        """
        _req_msg = ""
        if not is_secured:
            _req_msg = '{} {} HTTP/1.0\r\nHost: {}\r\nConnection: keep-alive\r\n\r\n'.format(self.method, self.url,
                                                                                             self.parsed_url.hostname)
        else:
            if self._cert is None:
                self._cert = sock.getpeercert()
                logging.info("Verified Certificate:\n%s" % self._cert)
            _req_msg = '{} {} HTTP/1.1\r\nHost: {}\r\nConnection: keep-alive\r\n\r\n'.format(self.method,
                                                                                             self.parsed_url.path or "/",
                                                                                             self.parsed_url.hostname)
        sock.send(_req_msg.encode("utf-8"))
        return Response(self.method, self.url, sock)


class Response:
    """
    A simple HTTP Response with customer socket.

    Usually, HTTPResponse in python system library is handling blocked socket, since we are dealing with asynchronous events
    we have to manually process sockets telegraph.

    The key idea is to reuse the parser from HTTPResponse to decode messages while keep a non-blocking socket in use.

    Key Members:

        _read(chunk : Number, iter = 0 : Number) : read a chunk of data from kernel synchronously
        _parse(res_txt : Bytes) : parse message from socket into HTTP response format

        read(chunk : Number) : read a chunk of data asynchronously
        close() : close the network device file descriptor
    """

    def __init__(self, method, url, sock, loop=None):
        """
        :param method: HTTP method used, currently we only support 'GET'
        :param url: str, parsed url string
        :param sock: Sock or SSLContext.SSLSocket, network device file descriptor
        :param loop: SimpleEventLoop, a simple event loop with natively multiplexing technology support
        """
        self.method = method
        self.url = url
        self.sock = sock
        self._loop = loop 
        # traditional response info, reference HTTPResponse 
        self._response = None
        self._chunked = None

    def __iter__(self):
        yield self

    def set_loop(self, loop):
        self._loop = loop 

    def _read(self, buf_size, iter=0):
        fut = Future()
        fd = self.sock.fileno()

        @timmer
        def onReadable():
            sock = self.sock
            CHUNK = buf_size

            if hasattr(sock, "_sslobj"):
                # ssl recv will raise an exception for streaming socket, yiakwy Dec 26, 2020, also discussion with Giampaolo Rodola https://bugs.python.org/issue3890
                buf = ct.create_string_buffer(CHUNK+1)
                try:
                    # readed = self.sock.read(CHUNK, buf)
                    # ret = buf.value

                    ret = b""
                    while CHUNK > 0:
                        readed = self.sock.recv(CHUNK)# self.sock.read(CHUNK, buf)
                        if len(readed) == 0:#not readed:
                            time.sleep(1e-6)
                            raise EOFError
                        ret += readed#buf.value
                        CHUNK -= len(readed)#readed

                    # if readed < CHUNK:
                    #     logging.info("reading %d bytes at iteration %d" % (readed, iter))
                except ssl.SSLWantReadError:
                    if len(ret) == 0:
                        ret = PROC_IN_PROGRESS
                except EOFError:
                    pass
                except Exception as e:
                    print(e.args[0])
                    SystemExit(e)
                fut.set_ret(ret)
            else:
                fut.set_ret(self.sock.recv(CHUNK))

        self._loop._selector.register(fd, EVENT_READ, (onReadable, None))
        chunk = yield from fut
        self._loop._selector.unregister(fd)
        return chunk 

    def read(self, CHUNK=None):
        if self._chunked is not None and CHUNK is not None:
            return self._chunked   
        CHUNK = CHUNK or 8192
        ret = b""
        while True:
            chunk = yield from self._read(CHUNK)
            if chunk == PROC_IN_PROGRESS:
                # continue to read
                continue
            if not chunk: # empty
                time.sleep(1e-3)
                continue#break
            ret += chunk
            if chunk.endswith(b'0\r\n\r\n'): # HTTP1.1 chunk end sign
                # detach the connection
                break
            else:
                print("read chunk size : %3.3f M" % (len(ret) / 1024))
        self._chunked = ret
        self._parse(ret)
        return ret 

    def recv(self, buf_size, media_type=None):
        CHUNK = buf_size
        CHUNK = CHUNK or 8192
        ret = b""
        target_size = -1
        while True:
            chunk = yield from self._read(CHUNK)
            if chunk == PROC_IN_PROGRESS:
                # continue to read
                continue
            if not chunk: # empty
                time.sleep(1e-3)
                continue#break
            ret += chunk
            if chunk.endswith(b'0\r\n\r\n') or len(chunk) < CHUNK: # HTTP1.1 chunk end sign, also see https://en.wikipedia.org/wiki/Chunked_transfer_encoding
                # detach the connection
                break
            else:
                print("read chunk size : %3.3f M" % (len(ret) / 1024))
        return ret

    def get_header(self, header):
        return self._response.getheader(header)

    @property 
    def status(self):
        return self._response.status 
    
    @property 
    def body(self):
        return self._response.read()

    @property
    def headers(self):
        return self._response.headers

    def _parse(self, res_txt):
        try:
            from httplib import HTTPResponse
        except:
            # py3
            from http.client import HTTPResponse
        try:
            from BytesIO import BytesIO
        except:
            # py3
            from io import BytesIO

        class _FakeSocket():

            def __init__(self, bytes):
                self._fp = BytesIO(bytes)

            # https://github.com/python/cpython/blob/c9758784eb321fb9771e0bc7205b296e4d658045/Lib/http/client.py#L217
            # https://stackoverflow.com/questions/24728088/python-parse-http-response-string 
            def makefile(self, *args, **kwargs):
                return self._fp
        
        fsock = _FakeSocket(res_txt)
        self._response = HTTPResponse(fsock)
        self._response.begin()
        # freshly added to avoid chunked HTTPResponse
        self._response.chunked = False

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()


def async_urlopen(url, parsed_url=None, timeout=None, loop=None):
    """
    :param url: str, parsed url
    :param parsed_url: Object, parsed url object
    :param timeout: Number, timeout for kernel to wait for response
    :param loop: SimpleEventLoop
    :return: Response
    """
    logger = Log.LogAdapter(_logger, "async_urlopen")

    parsed = parsed_url or urlparse(url)
    is_secured_sock_used = False

    if parsed.scheme == 'http':
        sock = socket.socket()
        addr = (parsed.hostname, parsed.port or 80)
    elif parsed.scheme == 'https':
        uns_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = (parsed.hostname, parsed.port or 443)

        # Note ssl connect has a bug, hence I decided to connect manually
        uns_sock.connect(addr)

        is_secured_sock_used = True

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        # create secure socket
        sock = ssl_ctx.wrap_socket(uns_sock, server_hostname=parsed.hostname)#, do_handshake_on_connect=False)
        # @todo TODO (hard coded)
        ssl_ctx.load_verify_locations(settings.CERT_FILE)
        # please check ctx.get_ciphers(), also @see https://github.com/python/cpython/blob/master/Lib/test/test_ssl.py
        # how to use it, yiakwy
        ssl_ctx.set_ciphers(settings.CHIPHER)
        # sock.do_handshake()
    else:
        raise SystemExit("scheme %s is not supported yet" % parsed.scheme)

    sock.setblocking(False)
    loop.set_timeout(timeout)

    try:
        logger.info("connectting to addr (%s,%d)" % addr)
        if not is_secured_sock_used:
            sock.connect(addr)
    except BlockingIOError as e:
        print(e)
    except Exception as e:
        raise(e)

    fut = Future()

    def onConnected():
        fut.set_ret(None)
    
    fd = sock.fileno()
    loop._selector.register(fd, EVENT_WRITE, (None, onConnected))
    yield from fut
    logger.info("TCP connection built.")
    loop._selector.unregister(fd)
    # initiate http reuqest
    req = Request('GET', url, parsed_url=parsed)
    response = req.send(sock, is_secured=is_secured_sock_used)
    response.set_loop(loop)
    return response


# dataset downloader
def async_download(url, timeout=settings.TIME_OUT, loop=None,
                   success_handler=None, err_handler=None, dirname=None):
    """
    :param url: str, parsed url target address
    :param timeout: Number, timeout for kernel to wait for response from remote
    :param loop: SimpleEventLoop
    :param success_handler: callback when success
    :param err_handler: callback when an error is thrown
    :param dirname: str, directory path for downloaded files
    :return: Response
    """
    # TO DO: logger adpator
    logger = Log.LogAdapter(_logger, "download")
    logger.info("parsing url ...")
    parsed = urlparse(url)
    logger.info("url parsed.")
    filename = os.path.basename(parsed.path)
    if os.path.isfile(filename):
        logger.warn("The file has already existed")
    # connect I/O
    # write I/O, socket write http request to remote
    # response = urlopen(url, timeout=timeout)
    logger.info("downloading ...")
    start = time.time()
    response = yield from async_urlopen(url, timeout=timeout, loop=loop)
    elapsed = time.time() - start
    logger.info("connection built, eslapsed :%s sec" % elapsed)
    CHUNK = 8192
    
    dirname = dirname or "downloaded_data"
    if not os.path.exists(dirname):
        os.mkdir(dirname)
    
    logger.info("writing data to local file ...")

    ## The codes works with http but not https
    # import pdb; pdb.set_trace()
    # with open(os.path.join(dirname, filename), "wb") as f:
    #     while True:
    #         # read I/O
    #         # import pdb; pdb.set_trace()
    #         chunk = yield from response._read(CHUNK) # read from socked's chunk
    #         if not chunk:
    #             break
    #         f.write(chunk)

    is_complete = False
    total_read = -1
    content_length = -1
    bytes_str = b''
    while not is_complete:
        chunk = yield from response.recv(CHUNK)
        bytes_str += chunk

        if content_length == -1:
            response._chunked = bytes_str
            response._parse(bytes_str) # TODO to be optimized

        try:
            total_read = len(response.body)
            if content_length == -1:
                content_length = int(response.get_header('CONTENT-LENGTH'))
            if  total_read >= content_length:
                break
        except http.client.IncompleteRead:
            pass
        except Exception as e:
            print(e)
            SystemExit(e)

    response._chunked = bytes_str
    response._parse(bytes_str)
    content = response.body
    image_buf = io.BytesIO(content)

    im = Image.open(image_buf)
    im.save(os.path.join(dirname, filename))

    logger.info("done.")

    response.close()
    return filename


def is_redirect(code):
    """
    :param code: Int, HTTP status code
    :return: bool
    """
    return code >= 300 and code <= 399

