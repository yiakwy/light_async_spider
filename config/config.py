'''
Created on 15 Jul, 2016

@author: wangyi
'''

import os 
# from config import cfg
import importlib
import global_settings

ENVIRON_CONFIG = "config"

try:
  basestring
except NameError:
  basestring = str

class ImproperlyConfigured(Exception): pass 

class Settings:
    """
    Setting loader : dynamically loading settings defined in a settings.py, simliar to classloader
    """
    
    def __init__(self, custom_settings=None):
        """
        :param custom_settings: str, relative path to customer settings file in the module
        """
        # update global settings 
        for setting in dir(global_settings):
            if setting.isupper() and not setting.startswith("__"):
                setattr(self, setting, getattr(global_settings, setting))
                
        if custom_settings is None:
            custom_settings = os.environ.get(ENVIRON_CONFIG)
        if custom_settings is not None and isinstance(custom_settings, basestring):
            try:
                custom_settings = importlib.import_module(custom_settings)
            except Exception as ex:
                raise ImproperlyConfigured("")

        if custom_settings is not None:
            self._setting_module = custom_settings
            self._overriden_vals = set()
            for setting in dir(custom_settings):
                if setting.isupper():
                    val = getattr(custom_settings, setting)
                    # do some checking
                    # @todo : TODO
                    
                    # overriden
                    setattr(self, setting, val)
                    self._overriden_vals.add(setting)
                    
    def __str__(self):
        ret = []
        ret.append("\nConfigurations:\n")
        for setting in dir(self):
            if setting.isupper() and not setting.startswith("__"):
                ret.append("{:30} {}\n".format(setting, getattr(self, setting)))
        ret.append("\n")
        return "".join(ret)
        
    def __repr__(self):
        return "<Setting Object: {}>".format(self._setting_module.__name__)


# Python configuration file parser and loader
import configparser
import json

JSON_VALUES = ("ROOT_URLS", "RULES_SET")

def get_conf(conf):
    """Parse a sectioned configuration file using ConfigParser.

    Each section in a configuration file contains a header, indicated by
    a name in square brackets (`[]'), plus key/value options, indicated by
    `name' and `value' delimited with a specific substring (`=' or `:' by
    default).

    Values can span multiple lines, as long as they are indented deeper
    than the first line of the value. Depending on the parser's mode, blank
    lines may be treated as parts of multiline values or ignored.

    Configuration files may include comments, prefixed by specific
    characters (`#' and `;' by default). Comments may appear on their own
    in an otherwise empty line or may be entered in lines holding values or
    section names.
    """
    config = configparser.ConfigParser()
    settings = Settings()

    config_obj = {}

    if conf is not None and isinstance(conf, basestring):
        config.read(conf)
    else:
        raise Exception("Expect conf to a file but find with %s" % type(conf))

    # parsing sections
    for section in config.sections():
        print("loading section %s ..." % section)
        section_values = {}
        config_obj[section] = section_values
        if section in JSON_VALUES:
            for options in config.options(section):
                # strip new lines
                json_str = ''.join(config.get(section, options).split())
                val = json.loads(json_str)
                print("ok %s" % json.dumps(val, indent=2))
                section_values[options] = val

        else:
            for options in config.options(section):
                val = config.get(section, options)
                if val == "":
                    val = None
                section_values[options] = val
                pass
            pass

    return config_obj
