# Created on 28th Nov 2017 by Lei
# Please refer to spcrapy for more info. If you want to konw more about Dynamic Rich Protected Content
# scraping, please keep an eye on my github page https://github.com/yiak.wy

import os

# import core asynchronous downloader using mutlplexing technology
from core.downloader.handlers.async_socket_http11 import Queue, urlparse, async_download, async_urlopen, is_redirect, StopImediately
from config import settings

import logging
import utils.Log as Log
_logger = logging.getLogger("base_spider")


class StopCrawling(Exception):pass


class BaseAsyncSpider:
    """
    Base Asynchronous Spider : Implements a specific crawling algorithm

    Key Members :

        _run() : fetch url from task queue and execute crawling routine

        crawl(url, max_direct, depth) :
            implement strategies to crawl links and remove duplicated links:
    """

    logger = Log.LogAdapter(_logger, "base_spider")

    def __init__(self, root_url, max_redirect, max_depth, loop=None, queue=None):
        self._q = queue or Queue(maxsize=10000)
        self.root_url = root_url
        self.max_redirect = max_redirect
        self.max_depth = max_depth
        self._loop = loop 
        self.seen_urls = set()
        data = (root_url, max_redirect, 0)
        self._q.put_nowait(data)
        self._is_media_type_to_be_downloaded = False
        self._media_types_to_be_downloaded = []
        # @todo TODO(add switch support), see @webkit downloader usage tests.core.downloader.handlers.test_webkit_runtime.py
        self.cur_addr = None
        self.use_webkit_engine = False

    def _run(self):
        while True:
            # import pdb; pdb.set_trace()
            url, max_redirect, depth = yield from self._q.get()
            yield from self.crawl(url, max_redirect, 0)
            self._q.task_done()

    def parse_links(self, response):
        raise Exception("Not Implemented!")

    def crawl(self, url, max_redirect, depth):
        """
        :param url: str, parsed url
        :param max_redirect: int, maximum redirection for an endpoint
        :param depth: int, depth go into from root url
        :return: None
        """
        self.logger.info("crawling %s at depth %d, seen urls %d" % (url, depth, len(self.seen_urls)))
        parsed = urlparse(url)
        self.cur_addr = parsed
        filename = os.path.basename(parsed.path)

        def is_media_type(link):
            for media_ext in self._media_types_to_be_downloaded:
                if link is not None and link.endswith(media_ext):
                    return True

            return False

        # handling media type
        if self._is_media_type_to_be_downloaded:
            if len(self._media_types_to_be_downloaded) > 0:
                for media_ext in self._media_types_to_be_downloaded:
                    if filename is not None and filename.endswith(media_ext):
                        if self.count >= self.target_number:
                            raise StopImediately()
                        yield from async_download(url, dirname=self.dirname, loop=self._loop)
                        self.count += 1
                        return

        response = None
        try:
            response = yield from async_urlopen(url, parsed_url=parsed, timeout=settings.TIME_OUT, loop=self._loop)
            yield from response.read()
        # import pdb; pdb.set_trace()
            if depth >= self.max_depth:
                raise StopCrawling()
            if is_redirect(response.status):
                if max_redirect > 0:
                    next_url = response.get_header('location')
                else:
                    self.logger.error("url %s exeeds maximum of redirection %d" % (url, self.max_redirect))
                    return

                if next_url in self.seen_urls: return 

                self.logger.info("url %s is redirected to %s" % (url, next_url))

                self.seen_urls.add(next_url)
                data = (next_url, max_redirect-1, depth)
                self._q.put_nowait(data)
            else:
                links = yield from self.parse_links(response)
                links_to_wait = []
                for link in set(links).difference(self.seen_urls):
                    data = (link, self.max_redirect, depth + 1)
                    if is_media_type(link):
                        self._q.put_nowait(data)
                    else:
                        links_to_wait.append(data)
                for data in links_to_wait:
                    self._q.put_nowait(data)
                self.seen_urls.update(links)
        except StopCrawling:
            self.logger.info("StopCrawing ...")
            pass
        finally:
            if response:
                response.close()
