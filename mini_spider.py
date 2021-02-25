# Copyright (c) 2017, Lei Wang
# All rights reserved.
# Author yiak.wy@gmail.com
#   Updated on Dec 25, 2020 by Lei

## system libraries

import sys
import os
from os.path import join, abspath, realpath, dirname

ROOT = dirname(realpath(__file__))
sys.path.insert(0, ROOT)
from config import settings, get_conf
import argparse

setattr(settings, "ROOT", ROOT)

# sys.path.insert(0, "%s/core"   % ROOT)
# sys.path.insert(0, "%s/lib"    % ROOT)
# sys.path.insert(0, "%s/utils"  % ROOT)
# sys.path.insert(0, "%s/cloud"  % ROOT)
# sys.path.insert(0, "%s/cmds"   % ROOT)
# sys.path.insert(0, "%s/config" % ROOT)
# sys.path.insert(0, "%s/models" % ROOT)

from io import StringIO
import logging

# urlparse utility
try:
    from urllib.parse import urlparse, urlencode, quote_plus, parse_qsl
except:
    # py2
    from urlparse import urlparse, urlencode, quote_plus, parse_qsl

## third party libraries
from lxml import etree


## customer libraries
from core.downloader.handlers.async_socket_http11 import Task, SimpleEventLoop, Queue
from core.spiders.base_spider import BaseAsyncSpider

import utils.Log as Log
_logger = logging.getLogger("spiders")

from config import settings

DEBUG_ETREE = True

class MyAsyncSpider(BaseAsyncSpider):
    """
    Implementation Code of Spider Services. This module demonstrates how to use `BaseAsyncSpider` in business side.

    Example:
        see examples from `fetch_imgs_from_root` and `fetch_imgs_from_urls` in this module

    Key members to implement:
      parse_links(response : Response)

    """

    logger = Log.LogAdapter(_logger, "MyAsyncSpider")

    # sitemap relevant, designed for "konachan.net"
    Rules_linked_websites = [
        "//div[@class='paginator']/a/@href",
        "//ul[@id='tag-sidebar']/li/a[2]/@href"
    ]

    Rules_for_images_media_type = [
        "//img[@class='preview']/@src",
    ]

    # extend your customer links patten here
    Rules_your_general_rule = [

    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        """
        :param target_number: maximum of number of links to be crawled 
        :param count: used by BaseAsyncSpider to count the number of links crawled
        :param dirname : the directory name to store media resources
        :param _is_media_type_to_be_downloaded : whether to download media types
        :param _media_types_to_be_downloaded : media types to be downloaded
        """
        self.target_number = 1000000000
        self.count = 0
        self.dirname = "../images"
        self._is_media_type_to_be_downloaded = True
        self._media_types_to_be_downloaded = ["jpg", ]

    def parse_links(self, response):
        """
        :param response: Response, similiar to HTTPResponse, defined async_socket_http11 downloader
        :return: List<str>, parsed urls from document object and return to BaseAsyncSpider which defined crawler algorithms
        to be used.
        """
        # import pdb; pdb.set_trace()
        parser = etree.HTMLParser()
        body = response.body.decode(response.headers.get_content_charset() or "utf-8")
        tree = etree.parse(StringIO(body), parser=parser)
        if DEBUG_ETREE:
            if etree.tostring(tree) is None:
                raise Exception("Bad Values!")

        urls = []
        hostname = self.cur_addr.hostname

        # process relative path
        def _process_extracted_path(path):
            parsed = urlparse(path)
            hostname = self.cur_addr.hostname
            scheme = self.cur_addr.scheme
            if parsed.hostname is not None and parsed.hostname is not "":
                hostname = parsed.hostname
            if parsed.scheme is not None and parsed.scheme is not "":
                scheme = parsed.scheme

            kw = dict(parse_qsl(parsed.query))
            parsed_path = parsed.path if len(kw) == 0 else "{}?{}".format(parsed.path, urlencode(kw))

            url = "%s://%s/%s" % (scheme, hostname, parsed_path[1:])
            return url

        if hostname == "konachan.net":
            for rule in self.Rules_for_images_media_type:
                try:
                    for path in tree.xpath(rule):
                        url = _process_extracted_path(path)
                        yield url
                        urls.append(url)
                except Exception as e:
                    print(e)

            for rule in self.Rules_linked_websites:
                for path in tree.xpath(rule):
                    # the value will be sent to outer layer
                    url = _process_extracted_path(path)
                    yield url
                    urls.append(url)

        for rule in self.Rules_your_general_rule:
            for path in tree.xpath(rule):
                url = _process_extracted_path(path)
                yield url
                urls.append(url)

        # @todo TODO dump the parsed urls to files

        return urls


def fetch_imgs_from_root(root_url):
    """
    :param root_url: str, parsed root url the crawler starting from
    :return: None, produced data and files are processed internally by base crawlers defined in core/spiders/base_spider.py
    """
    Log.InitLogFrmConfig(settings.LOGGING)
    loop = SimpleEventLoop()
    loop.set_timeout(settings.TIME_OUT)
    # Note I just freshly added support to HTTPS
    spider = MyAsyncSpider(root_url=root_url, max_redirect=3, max_depth=10, loop=loop)

    def routine(concurrency):
        tasks = [Task(spider._run()) for _ in range(concurrency)]

        yield from spider._q.join()
        for t in tasks:
            t.cancel()

    loop.run_until_complete(routine(1000))


def fetch_imgs_from_urls(urls):
    """
    :param urls: List<str>, a list of parsed urls
    :return: None, produced data and files are processed internally by base crawlers defined in core/spiders/base_spider.py
    """
    Log.InitLogFrmConfig(settings.LOGGING)
    loop = SimpleEventLoop()
    loop.set_timeout(settings.TIME_OUT)
    q = Queue(maxsize=10000)

    def routine(urls):
        tasks = []
        for url in urls:
            spider = MyAsyncSpider(root_url=url, max_redirect=3, max_depth=settings.MAX_DEPTH, loop=loop, queue=q)

            # configure attributes parsed from spider.conf


            task = Task(spider._run())
            tasks.append(task)

        yield from q.join()
        for t in tasks:
            t.cancel()

    loop.run_until_complete(routine(urls))


def shell(raw_args):
    usage = """
    mini.py [--<opt>]
        -c : spider configuration file
        -v : show software version
        """

    __version__ = (0,1,0)

    parser = argparse.ArgumentParser(description=__doc__, usage=usage)
    parser.add_argument('-c', '--conf', help="")
    parser.add_argument('-v', '--version', action='version', version='.'.join(map(lambda x:str(x), __version__)))
    parser.add_argument('argc', nargs='?', type=int)
    parser.add_argument('argv', nargs=argparse.REMAINDER, help="arguments for sub command")

    args = parser.parse_args(raw_args)

    if args.conf:
        print("reading %s ... " % args.conf)
        conf_path = os.path.join(ROOT, args.conf)
        conf_obj = get_conf(conf_path)

        if conf_obj.get('spider', None) is not None:
            url_list_file = conf_obj['spider'].get('url_list_file', None)
            output_directory = conf_obj['spider'].get('output_directory', None)
            max_depth = conf_obj['spider'].get('max_depth', None)
            crawl_interval = conf_obj['spider'].get('crawl_interval', None)
            crawl_timeout = conf_obj['spider'].get('crawl_timeout', None)
            target_url = conf_obj['spider'].get('target_url', None)

            def is_valid_fn(fn):
                if fn is not None and fn is not "":
                    if os.path.exists(fn) and os.path.isfile(fn):
                        return True
                    else:
                        logging.error("%s is not a valid file" % fn)
                    return False
                logging.error("fn is an empty string or None!")
                return False

            def is_dir(path):
                if path is not None and path is not "":
                    if os.path.exists(path) and os.path.isdir(path):
                        return True
                    else:
                        logging.warning("%s is not a valid directory" % path)
                    return False
                logging.error("path is an empty string or None!")
                return False

            def parse_url(field):
                if field is not None and field is not "":
                    import re
                    # see https://github.com/django/django/blob/master/django/core/validators.py#L74
                    # also see
                    # https://stackoverflow.com/questions/827557/how-do-you-validate-a-url-with-a-regular-expression-in-python
                    url_regex = re.compile(r"""((http|https)\:\/\/)? # scheme
                        [a-zA-Z0-9\.\/\?\: # port
                        @\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])* # path""",
                                           re.IGNORECASE | re.VERBOSE)
                    searched = url_regex.search(field)
                    if searched is not None:
                        return searched.string
                    else:
                        logging.error("URL path <%s> is not a valid url" % field)
                    return None
                logging.error("field is an empty string or None!")
                return None

            def parse_number(field):
                if field is not None:
                    try:
                        val = int(field)
                    except ValueError:
                        logging.error("%s is not a number" % field)
                        return None
                    return val
                logging.error("field is None!")
                return None

            urls = []
            if is_valid_fn(url_list_file):
                with open(url_list_file, 'r') as f:
                    for line in f.readlines():
                        url = parse_url(line.strip())
                        if url is not None:
                            urls.append(url)

            if is_dir(output_directory):
                setattr(settings, "output_directory".upper(), output_directory)
            else:
                os.system("mkdir -p %s" % output_directory)
                setattr(settings, "output_directory".upper(), "./log/output")

            max_depth = parse_number(max_depth)
            if max_depth is not None:
                setattr(settings, "max_depth".upper(), max_depth)
            else:
                setattr(settings, "max_depth".upper(), 10)

            crawl_interval = parse_number(crawl_interval)
            if crawl_interval is not None:
                setattr(settings, "crawl_interval".upper(), crawl_interval)
            else:
                setattr(settings, "crawl_interval".upper(), -1) # no throttling strategy configured

            crawl_timeout = parse_number(crawl_timeout)
            if crawl_interval is not None:
                settings.TIME_OUT = crawl_timeout

            if target_url is not None and target_url is not "":
                # is a valid regex
                import re
                target_url_regex = re.compile(target_url, re.IGNORECASE)
                setattr(settings, "target_url_regex".upper(), target_url_regex)

            fetch_imgs_from_urls(urls)
        # older configuration file format, see spider.conf.bak
        elif conf_obj.get('ROOT_URL', None) is not None:
            root_url = conf_obj['ROOT_URL'].get("ROOT_URL".lower(), None)
            if root_url is None:
                raise(Exception("Wrong input! option <ROOT_URL> in section 'ROOT_URL' is required!"))
            fetch_imgs_from_root(root_url)
        else:
            raise Exception("Not supported for the moment, pull requests are welcome!")

    else:
        print("Not valid input!")
        parser.print_help()

if __name__ == "__main__":
    sys.exit(shell(sys.argv[1:]))
