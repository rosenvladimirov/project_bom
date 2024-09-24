#!/usr/bin/python3
from __future__ import absolute_import

import argparse
import os
import sys
from urllib.parse import non_hierarchical

# Add ../ to the path
# Works if this script is executed without installing the module
script_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
sys.path.insert(0, os.path.dirname(script_dir))
# Pretend we are part of a module
# Avoids: ImportError: attempted relative import with no known parent package
__package__ = os.path.basename(script_dir)
__import__(__package__)


# python 2 and 3 compatibility hack
def to_utf(s):
    if isinstance(s, bytes):
        return s.decode('utf-8')
    else:
        return s


def main():
    cli_mode = False
    create_wx_app = 'INTERACTIVE_HTML_BOM_NO_DISPLAY' not in os.environ
    try:
        import wx
    except ImportError:
        cli_mode = True
        create_wx_app = False

    if create_wx_app:
        app = wx.App()
        if hasattr(wx, "APP_ASSERT_SUPPRESS"):
            app.SetAssertMode(wx.APP_ASSERT_SUPPRESS)
    elif create_wx_app and hasattr(wx, "DisableAsserts"):
        wx.DisableAsserts()

    from .core.ibom import main as ibom_main
    from .core.config import Config
    from .core.logger import Logger
    from .ecad import get_parser_by_extension
    from .version import version
    from .errors import (ExitCodes, ParsingException, exit_error)

    parser = argparse.ArgumentParser(
            description='KiCad InteractiveHtmlBom plugin CLI.',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('file',
                        type=lambda s: to_utf(s),
                        help="KiCad PCB file")

    Config.add_options(parser, version)
    args = parser.parse_args()
    logger = Logger(cli=cli_mode)

    if not os.path.isfile(args.file):
        exit_error(logger, ExitCodes.ERROR_FILE_NOT_FOUND,
                   "File %s does not exist." % args.file)

    print("Loading %s" % args.file)

    config = Config(version, os.path.dirname(os.path.abspath(args.file)))

    parser = get_parser_by_extension(
        os.path.abspath(args.file), config, logger)

    if args.show_dialog:
        if not create_wx_app:
            exit_error(logger, ExitCodes.ERROR_NO_DISPLAY,
                       "Can not show dialog when "
                       "INTERACTIVE_HTML_BOM_NO_DISPLAY is set.")
        try:
            from .core.ibom_dialog import run_with_dialog
            run_with_dialog(parser, config, logger)
        except ParsingException as e:
            exit_error(logger, ExitCodes.ERROR_PARSE, e)
    else:
        config.set_from_args(args)
        try:
            ibom_main(parser, config, logger)
        except ParsingException as e:
            exit_error(logger, ExitCodes.ERROR_PARSE, str(e))
    return 0


if __name__ == "__main__":
    main()
