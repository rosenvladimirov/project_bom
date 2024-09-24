import sys
import logging

try:
    import wx
except ImportError:
    pass


class Logger(object):

    def __init__(self, cli=False):
        self.cli = cli
        self.logger = logging.getLogger('InteractiveHtmlBom')
        self.logger.setLevel(logging.INFO)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)-15s %(levelname)s %(message)s")
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def info(self, *args):
        if self.cli:
            self.logger.info(*args)

    def error(self, msg):
        if self.cli:
            self.logger.error(msg)
        else:
            wx.MessageBox(msg)

    def warn(self, msg):
        if self.cli:
            self.logger.warning(msg)
        else:
            wx.LogWarning(msg)


log = None
