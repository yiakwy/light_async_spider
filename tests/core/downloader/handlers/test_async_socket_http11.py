#!/usr/bin/env python
# Copyright (c) 2017, Lei Wang
# All rights reserved.
# Author yiak.wy@gmail.com
from core.downloader.handlers.async_socket_http11 import async_download, SimpleEventLoop
import utils.Log as Log
from config import settings

def test_download_with_asyn_urlopen():
    Log.InitLogFrmConfig(settings.LOGGING)
    loop = SimpleEventLoop()
    url = "http://konachan.net/image/4df6757f418f47dabe659ff043503d0c/Konachan.com%20-%20254793%20animal%20cat%20kazeno%20original.jpg"
    loop.run_until_complete(async_download(url, loop=loop))

    # assert the existence fo the file


if __name__ == "__main__":
    test_download_with_asyn_urlopen()
