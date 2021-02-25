"""
global settings for mini_spider project

Author: Lei Wang (yiak.wy@gmail.com)
Date: 2017/11/22
"""

import sys
import os

# Root path will be compute dynamically in runtime

# downlaoder
TIME_OUT=15

# mail 
MAIL_ADDR=["mail.x.com", "devops@x.com", "notify@x.com"]
MAIL_CREDENTIALS=["devops@x.com", "password"]
MAIL_HOSTS="localhost"

LOG_DIR = './log/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': "%(asctime)s [%(levelname)s]:%(filename)s, %(name)s, in line %(lineno)s >> %(message)s",
            'datefmt': "%a, %d, %b, %Y %H:%M:%S", #"%d/%b/%Y %H:%M:%S"
            }
    # add different formattrs here
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'verbose'
            },
        'email_remote': {
            'level': 'ERROR',
            'class': 'logging.handlers.SMTPHandler',
            'formatter': 'verbose',
            'mailhost': MAIL_HOSTS,
            'fromaddr': 'mini_spider_notify@yiak.co',
            'toaddrs': MAIL_ADDR,
            'subject': 'mini spider project ERROR!',
            'credentials': MAIL_CREDENTIALS

        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter':'verbose',
            'filename': os.path.join(LOG_DIR, 'mini_spider.log')
         }

    },
    'loggers': {
        'downloader/handlers/async_socket_http11': {
            'handlers': ['console', 'file'],
            'propagate': True,
            'level': 'INFO'
            },
        'spiders': {
            'handlers': ['console', 'file'],
            'propagate': True,
            'level': 'INFO'
            },
        'base_spider': {
            'handlers': ['console', 'file'],
            'propagate': True,
            'level': 'INFO'
            }
    }
}

# HTTPS support
CERT_FILE = '/etc/ssl/certs/ca-certificates.crt'

# see see https://github.com/python/cpython/blob/master/Lib/test/test_ssl.py for supported (tested) cipher algorithms
CHIPHER = 'AES128-GCM-SHA256'

# Webkit support
JsInjRoot = "/home/yiakwy/WorkSpace/Bitbucket/mini_spider/remote_inj_js_call_wireless_protocol"