'''
Originally Created by Lei Wang (yiak.wy@gmail.com) on 21 May, 2015
Refactored on 27 Dec 2020 by Lei Wang (yiak.wy@gmail.com)
CopyRight ALL RIGHTS RESERVED
Reference Solution:
  I also made a selenium patch for scrapy several years ago and this solution much more slighter than
  the old one : https://github.com/scrapy/scrapy/pull/1326
'''

import sys
import os
import logging
_logger = logging.getLogger("downloader/handlers/webkit_runtime")

# urlparse utility
try:
    from urllib.parse import urlparse, urlencode, quote_plus
except:
    # py2
    from urlparse import urlparse, urlencode, quote_plus

import subprocess, threading
from selectors import DefaultSelector, EVENT_WRITE, EVENT_READ
import selectors

from core.downloader.handlers.async_socket_http11 import Future
from config import settings
import utils.Log as Log
import time

# Used inside Response I/O event once async_urlopen builds a connection successfully, yiakwy
PROC_IN_PROGRESS = -1

class Request:
    """
    A simple HTTP Request wrapper with customer socket for Remote Inject Javascript Call (RIJC) wireless protocol.

    Webkit is used parsing HTTP response and exported in c++ and ES6 Node environments by V8 machine.
    To enable anonymously crawling any sites open the public, based on Selenium wireless protocol, we proposed and implemented
    Remote Injected Javascript Call (RIJC) to communicate with Webkit environment.

    Key Members:

        send(sock, pipe, is_secured=False) : send messages to remote
    """

    def __init__(self, method, url,
            parsed_url=None, headers=None):
        self.url = url
        self.parsed_url = parsed_url or urlparse(url)
        self.method = method
        self._cert = None

    # @todo TODO
    def send(self, pipe, is_secured=False):
        """
        :param pipe: communication channel between principle and webkit processes
        :param is_secured:
        :return:
        """
        # implement the remote injected js call (RIJC) wireless protocol, see readme

        return Response(self.method, self.url, pipe)


class Response:
    """
    A simple HTTP Response wrapper with customer socket for Remote Inject Javascript Call (RIJC) wireless protocol.

    Webkit is used parsing HTTP response and exported in c++ and ES6 Node environments by V8 machine.
    To enable anonymously crawling any sites open the public, based on Selenium wireless protocol, we proposed and implemented
    Remote Injected Javascript Call (RIJC) to communicate with Webkit environment.

    Key Members:

        _read(chunk : Number, iter = 0 : Number) : read a chunk of data from kernel synchronously
        _parse(res_txt : Bytes) : parse message from socket into HTTP response format

        read(chunk : Number) : read a chunk of data asynchronously
        close() : close the network device file descriptor
    """

    def __init__(self, method, url, pipe_session, loop=None):
        """
        :param method: str, HTTP method, currently we only support 'GET' method
        :param url: str, parsed url
        :param pipe_session: PipeSession, a pipe connected to subprocess.
        :param loop: SimpleEventLoop
        """
        self.method = method
        self.url = url
        self.pipe = pipe_session # pay attention to here
        self._loop = loop
        # traditional response info, reference HTTPResponse
        self._response = None
        self._chunked = None

    def __iter__(self):
        yield self

    def set_loop(self, loop):
        self._loop = loop

    def _read(self, CHUNK, iter=0):
        fut = Future()
        fd = self.pipe.fileno()

        def onReadable():
            fut.set_ret(self.pipe.recv(CHUNK))

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
            if not chunk:
                break
            ret += chunk
        self._chunked = ret
        self._parse(ret)
        return ret

    def get_header(self, header):
        return self._response.getheader(header)

    @property
    def status(self):
        return self._response.status

    @property
    def body(self):
        return self._response.read()

    # @todo TODO
    def _parse(self, res_txt):
        # @todo TODO populating status, body and other attributes
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

    # @todo TODO
    def close(self):
        pass

class PipeSession(subprocess.Popen):
    """
    A pipe object wrapper to communicate with subprocess
    """

    def __init__(self, *args, **kwargs):
        subprocess.Popen.__init__(self, *args, **kwargs)

    # @todo TODO
    def send(self):
        pass

    # @todo TODO
    def recv(self, CHUNK=None):
        for line in iter(self.stdout.readline, b""):
            sys.stdout.write(line.decode('utf-8'))
            sys.stdout.flush()
            yield line

            if line.count('__remote_inj_js_call<<<STOP>>>') == 1:
                self.stdin.write('__remote_inj_js_cal<<<CLOSE>>>\n')
                self.stdin.flush()
                break
        pass


# @todo (STATUS : under refactoring)
class WebkitRuntime:
    """
    launch and execute webkit environment (a lightweight javascript will be injected into a headless browser)
    """

    def __init__(self, webkit_client, loop=None):
        """
        :param webkit_client: str, webkit_client name
        :param loop:
        """
        self._client = webkit_client
        self.args = ["/usr/local/bin/phantomjs",
                     os.path.join(settings.JsInjRoot, self._client+'.js')]
        self.options = [
            "--ignore-ssl-errors=true",
        ]
        self._pipe_session = None
        self._loop = loop

    def render(self, url='', tar='', method='GET', *args, **kwargs):
        # encode a http request
        query = urlencode(kwargs)
        if method == 'GET':
            url = "{}?{}".format(url, query)
        else:
            raise Exception("%s is not supported by %s for the moment, pull requests are welcome!" % (method,
                                                                                                      self.__class__.__name__))
        command = [arg for arg in self.args]
        command.extend([url, tar])
        command.extend(self.options)

        self._pipe_session = PipeSession(command, 1024, False,
                                     stdin =subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)


        # @todo TODO create RIJC wireless protocol request
        parsed = urlparse(url)
        req = Request('GET', url, parsed_url=parsed)

        # @todo TODO create RIJC wireless protocol response
        response = req.send()
        response.set_loop(self._loop)

