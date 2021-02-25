#!/usr/bin/env python
# Copyrite (c) 2017, Lei Wang
# All rights reserved.
# Author yiak.wy@gmail.com
import logging
from logging.config import dictConfig

from config import settings
import sys
import os

def InitLogFrmConfig(config=None):
    if config is None:
        config = settings.LOGGING

    # mkdir
    if not os.path.isdir(settings.LOG_DIR):
        os.makedirs(settings.LOG_DIR)

    dictConfig(config)

class LogAdapter(logging.LoggerAdapter):
    """
    Log Message Adaptor : Adapt each log message with a specific message prefix

    Key function to implemnt : process(msg : Message, kwargs : Map<Key, Object>)
    """

    def __init__(self, logger, prefix, **kwargs):
        """
        :param logger: Logger
        :param prefix: str, message prefix, usually names of class, modules and packages
        :param kwargs: Map<Key, Object>, keywords used by base logging.LoggerAdaptor
        """
        logging.LoggerAdapter.__init__(self, logger, kwargs)
        self.prefix = prefix 

    def process(self, msg, kwargs):
        return "[%s] %s" % (self.prefix, msg), kwargs


if __name__ == "__main__":
    import sys
    from os.path import abspath, join, dirname
    root = abspath(join("..", dirname(__file__)))
    sys.path.insert(0, root)
    print(root)
