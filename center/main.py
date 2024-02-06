import os
import signal
import sys

os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
sys.path.append(os.path.join(os.path.dirname(__file__), "rpc"))

import argparse
import json
from center import metadata
from center.server import donut_run
from center.syncsvr import SyncSvr
from center.flask import flask_run

from center.scan_block import ScanBlock


def main(argv):
    """Program entry point.

    :param argv: command-line arguments
    :type argv: :class:`list`
    """
    author_strings = []
    for name, email in zip(metadata.authors, metadata.emails):
        author_strings.append('Author: {0} <{1}>'.format(name, email))

    epilog = '''
{project} {version}

{authors}
URL: <{url}>
'''.format(project=metadata.project, version=metadata.version, authors='\n'.join(author_strings), url=metadata.url)

    arg_parser = argparse.ArgumentParser(prog=argv[0], formatter_class=argparse.RawDescriptionHelpFormatter, description=metadata.description, epilog=epilog)
    arg_parser.add_argument('--config', type=argparse.FileType('r'), help='config file for center')
    arg_parser.add_argument('command', choices=['grpc', 'sync', 'flask'], nargs='?', help='the command to run')
    arg_parser.add_argument('-V', '--version', action='version', version='{0} {1}'.format(metadata.project, metadata.version))
    arg_parser.add_argument('-I', '--init', action='store_true', help='Whether to sync initial data?')
    arg_parser.add_argument('-L', '--local', action='store_true', help='Restoring data from local database')
    arg_parser.add_argument('-D', '--debug', action='store_true', help='debug mode')

    args = arg_parser.parse_args(args=argv[1:])
    config_info = procConfig(args.config)
    if args.command == "grpc":
        donut_run(config_info)
    elif args.command == "sync":
        flag = 2
        if args.init:
            flag = 0
        elif args.local:
            flag = 1

        # ss = SyncSvr(config_info, flag, args.debug, block=block)
        ss = ScanBlock(config_info, flag, args.debug)

        def handler(__signalnum: int, __frame) -> None:
            ss.Stop()

        signal.signal(signal.SIGINT, handler)
        ss.Run()
    elif args.command == "flask":
        flask_run(config_info)
        pass
    else:
        print(epilog)
    return 0


def procConfig(cf):
    config_info = {}
    if not cf:
        cf = open("./config.json", "r")
    config_info = json.load(cf)
    return config_info


def entry_point():
    """Zero-argument entry point for use with setuptools/distribute."""
    raise SystemExit(main(sys.argv))


if __name__ == '__main__':
    entry_point()
