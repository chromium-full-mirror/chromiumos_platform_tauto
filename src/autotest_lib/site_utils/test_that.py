#!/usr/bin/python3
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import os
import signal
import subprocess
import sys

import logging
# Turn the logging level to INFO before importing other autotest
# code, to avoid having failed import logging messages confuse the
# test_that user.
logging.basicConfig(level=logging.INFO)

from autotest_lib.client.common_lib import logging_manager
from autotest_lib.server import server_logging_config
from autotest_lib.site_utils import test_runner_utils


def validate_arguments(arguments):
    """
    Validates parsed arguments.

    @param arguments: arguments object, as parsed by ParseArguments
    @raises: ValueError if arguments were invalid.
    """
    if arguments.remote == ':lab:':
        if arguments.args:
            raise ValueError('--args flag not supported when running against '
                             ':lab:')
        if arguments.pretend:
            raise ValueError('--pretend flag not supported when running '
                             'against :lab:')
        if arguments.ssh_verbosity:
            raise ValueError('--ssh_verbosity flag not supported when running '
                             'against :lab:')
        if not arguments.board or arguments.build == test_runner_utils.NO_BUILD:
            raise ValueError('--board and --build are both required when '
                             'running against :lab:')
    else:
        if arguments.web:
            raise ValueError('--web flag not supported when running locally')


def parse_arguments(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse
    @returns:    parsed arguments
    @raises SystemExit if arguments are malformed, or required arguments
            are not present.
    """
    return _parse_arguments_internal(argv)[0]


def _parse_arguments_internal(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse
    @returns:    tuple of parsed arguments and argv suitable for remote runs
    @raises SystemExit if arguments are malformed, or required arguments
            are not present.
    """
    local_parser, remote_argv = parse_local_arguments(argv)

    parser = argparse.ArgumentParser(description='Run remote tests.',
                                     parents=[local_parser])

    parser.add_argument('remote', metavar='REMOTE',
                        help='hostname[:port] for remote device. Specify '
                             ':lab: to run in test lab. When tests are run in '
                             'the lab, test_that will use the client autotest '
                             'package for the build specified with --build, '
                             'and the lab server code rather than local '
                             'changes.')
    test_runner_utils.add_common_args(parser)
    parser.add_argument('-b', '--board', metavar='BOARD',
                        action='store',
                        help='Board for which the test will run. '
                             'Default: %(default)s')
    parser.add_argument('-m',
                        '--model',
                        metavar='MODEL',
                        help='Specific model the test will run against. '
                        'Matches the model:FAKE_MODEL label for the host.')
    parser.add_argument('-i', '--build', metavar='BUILD',
                        default=test_runner_utils.NO_BUILD,
                        help='Build to test. Device will be reimaged if '
                             'necessary. Omit flag to skip reimage and test '
                             'against already installed DUT image. Examples: '
                             'link-paladin/R34-5222.0.0-rc2, '
                             'lumpy-release/R34-5205.0.0')
    parser.add_argument('-p', '--pool', metavar='POOL', default='suites',
                        help='Pool to use when running tests in the lab. '
                             'Default is "suites"')
    parser.add_argument(
            '--autotest_dir',
            metavar='AUTOTEST_DIR',
            help='Use AUTOTEST_DIR instead of normal board sysroot '
            'copy of autotest.')
    parser.add_argument('--allow-chrome-crashes',
                        action='store_true',
                        default=False,
                        dest='allow_chrome_crashes',
                        help='Ignore chrome crashes when producing test '
                        'report. This flag gets passed along to the '
                        'report generation tool.')
    parser.add_argument('--ssh_private_key', action='store',
                        default=test_runner_utils.TEST_KEY_PATH,
                        help='Path to the private ssh key.')
    parser.add_argument('--companion_hosts',
                        action='store',
                        default=None,
                        help='Companion duts for the test.')
    return parser.parse_args(argv), remote_argv


def parse_local_arguments(argv):
    """
    Strips out arguments that are not to be passed through to runs.

    Add any arguments that should not be passed to remote test_that runs here.

    @param argv: argument list to parse.
    @returns: tuple of local argument parser and remaining argv.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-w', '--web', dest='web', default=None,
                        help='Address of a webserver to receive test requests.')
    parser.add_argument('-x', '--max_runtime_mins', type=int,
                        dest='max_runtime_mins', default=20,
                        help='Default time allowed for the tests to complete.')
    parser.add_argument('--no-retries', '--no-retry',
                        dest='retry', action='store_false', default=True,
                        help='For local runs only, ignore any retries '
                             'specified in the control files.')
    _, remaining_argv = parser.parse_known_args(argv)
    return parser, remaining_argv


def perform_bootstrap_into_autotest_root(arguments, autotest_path, argv):
    """
    Perfoms a bootstrap to run test_that from the |autotest_path|.

    This function is to be called from test_that's main() script, when
    test_that is executed from the source tree location. It then executes
    and waits on the version of test_that.py in |autotest_path|.

    @param arguments: A parsed arguments object, as returned from
                      test_that.parse_arguments(...).
    @param autotest_path: Full absolute path to the autotest root directory.
    @param argv: The arguments list, as passed to main(...)

    @returns: The return code of the test_that script that was executed in
              |autotest_path|.
    """
    logging_manager.configure_logging(
            server_logging_config.ServerLoggingConfig(),
            use_console=True,
            verbose=arguments.debug)
    logging.info('Re-running test_that script in %s copy of autotest.',
                 autotest_path)
    script_command = os.path.join(autotest_path, 'site_utils',
                                  'test_that.py')
    if not os.path.exists(script_command):
        raise test_runner_utils.TestThatRunError(
            'Unable to bootstrap to autotest root, %s not found.' %
            script_command)
    proc = None
    def resend_sig(signum, stack_frame):
        #pylint: disable-msg=C0111
        if proc:
            proc.send_signal(signum)
    signal.signal(signal.SIGINT, resend_sig)
    signal.signal(signal.SIGTERM, resend_sig)

    proc = subprocess.Popen([script_command] + argv)

    return proc.wait()


def _main_for_all_run(argv, arguments):
    """
    Effective entry point test runs.

    @param argv: Script command line arguments.
    @param arguments: Parsed command line arguments.
    """
    results_directory = test_runner_utils.create_results_directory(
            arguments.results_dir, arguments.board)
    test_runner_utils.add_ssh_identity(results_directory,
                                       arguments.ssh_private_key)
    arguments.results_dir = results_directory

    # TODO, maybe need to force a board/model specification.

    if arguments.autotest_dir:
        autotest_path = arguments.autotest_dir
    else:
        # TODO, make this default to wherever this file is +1
        # Might need eventually come back to sysroot for deps. TBD.
        raise Exception("need to provide autotest_dir")

    site_utils_path = os.path.join(autotest_path, 'site_utils')

    if not os.path.exists(autotest_path):
        print(('%s does not exist. Have you run '
               'build_packages? Or if you are using '
               '--autotest_dir, make sure it points to '
               'a valid autotest directory.' % autotest_path), file=sys.stderr)
        return 1

    realpath = os.path.realpath(__file__)
    site_utils_path = os.path.realpath(site_utils_path)

    # If we are not executing in the given path, relaunch there.
    if os.path.dirname(realpath) != site_utils_path:
        return perform_bootstrap_into_autotest_root(
                arguments, autotest_path, argv)
    else:
        return test_runner_utils.perform_run_from_autotest_root(
                autotest_path,
                argv,
                arguments.tests,
                arguments.remote,
                build=arguments.build,
                board=arguments.board,
                model=arguments.model,
                args=arguments.args,
                ignore_deps=not arguments.enforce_deps,
                results_directory=results_directory,
                ssh_verbosity=arguments.ssh_verbosity,
                ssh_options=arguments.ssh_options,
                iterations=arguments.iterations,
                fast_mode=arguments.fast_mode,
                debug=arguments.debug,
                allow_chrome_crashes=arguments.allow_chrome_crashes,
                pretend=arguments.pretend,
                job_retry=arguments.retry,
                companion_hosts=arguments.companion_hosts)

def main(argv):
    """
    Entry point for test_that script.

    @param argv: arguments list
    """
    arguments, remote_argv = _parse_arguments_internal(argv)
    try:
        validate_arguments(arguments)
    except ValueError as err:
        print(('Invalid arguments. %s' % str(err)), file=sys.stderr)
        return 1

    _main_for_all_run(argv, arguments)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
