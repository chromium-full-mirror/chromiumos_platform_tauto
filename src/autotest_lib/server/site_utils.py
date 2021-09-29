# Lint as: python2, python3
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import grp
import logging
import os
import re
import traceback

from autotest_lib.client.bin.result_tools import utils as result_utils
from autotest_lib.client.bin.result_tools import utils_lib as result_utils_lib
from autotest_lib.client.bin.result_tools import view as result_view
from autotest_lib.client.common_lib import lsbrelease_utils
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import host_queue_entry_states


CONFIG = global_config.global_config

_SHERIFF_JS = CONFIG.get_config_value('NOTIFICATIONS', 'sheriffs', default='')
_LAB_SHERIFF_JS = CONFIG.get_config_value(
        'NOTIFICATIONS', 'lab_sheriffs', default='')
_CHROMIUM_BUILD_URL = CONFIG.get_config_value(
        'NOTIFICATIONS', 'chromium_build_url', default='')

LAB_GOOD_STATES = ('open', 'throttled')

ENABLE_DRONE_IN_RESTRICTED_SUBNET = CONFIG.get_config_value(
        'CROS', 'enable_drone_in_restricted_subnet', type=bool,
        default=False)

# Wait at most 10 mins for duts to go idle.
IDLE_DUT_WAIT_TIMEOUT = 600

# Mapping between board name and build target. This is for special case handling
# for certain Android board that the board name and build target name does not
# match.
ANDROID_TARGET_TO_BOARD_MAP = {
        'seed_l8150': 'gm4g_sprout',
        'bat_land': 'bat'
        }
ANDROID_BOARD_TO_TARGET_MAP = {
        'gm4g_sprout': 'seed_l8150',
        'bat': 'bat_land'
        }


class TestLabException(Exception):
    """Exception raised when the Test Lab blocks a test or suite."""
    pass


class ParseBuildNameException(Exception):
    """Raised when ParseBuildName() cannot parse a build name."""
    pass


class Singleton(type):
    """Enforce that only one client class is instantiated per process."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Fetch the instance of a class to use for subsequent calls."""
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                    *args, **kwargs)
        return cls._instances[cls]

class EmptyAFEHost(object):
    """Object to represent an AFE host object when there is no AFE."""

    def __init__(self):
        """
        We'll be setting the instance attributes as we use them.  Right now
        we only use attributes and labels but as time goes by and other
        attributes are used from an actual AFE Host object (check
        rpc_interfaces.get_hosts()), we'll add them in here so users won't be
        perplexed why their host's afe_host object complains that attribute
        doesn't exist.
        """
        self.attributes = {}
        self.labels = []


def ParseBuildName(name):
    """Format a build name, given board, type, milestone, and manifest num.

    @param name: a build name, e.g. 'x86-alex-release/R20-2015.0.0' or a
                 relative build name, e.g. 'x86-alex-release/LATEST'

    @return board: board the manifest is for, e.g. x86-alex.
    @return type: one of 'release', 'factory', or 'firmware'
    @return milestone: (numeric) milestone the manifest was associated with.
                        Will be None for relative build names.
    @return manifest: manifest number, e.g. '2015.0.0'.
                      Will be None for relative build names.

    """
    match = re.match(r'(trybot-)?(?P<board>[\w-]+?)(?:-chrome)?(?:-chromium)?'
                     r'-(?P<type>\w+)/(R(?P<milestone>\d+)-'
                     r'(?P<manifest>[\d.ab-]+)|LATEST)',
                     name)
    if match and len(match.groups()) >= 5:
        return (match.group('board'), match.group('type'),
                match.group('milestone'), match.group('manifest'))
    raise ParseBuildNameException('%s is a malformed build name.' % name)


def remote_wget(source_url, dest_path, ssh_cmd):
    """wget source_url from localhost to dest_path on remote host using ssh.

    @param source_url: The complete url of the source of the package to send.
    @param dest_path: The path on the remote host's file system where we would
        like to store the package.
    @param ssh_cmd: The ssh command to use in performing the remote wget.
    """
    wget_cmd = ("wget -O - %s | %s 'cat >%s'" %
                (source_url, ssh_cmd, dest_path))
    utils.run(wget_cmd)


def is_in_lab():
    """Check if current Autotest instance is in lab

    @return: True if the Autotest instance is in lab.
    """
    test_server_name = CONFIG.get_config_value('SERVER', 'hostname')
    return test_server_name.startswith('cautotest')


def host_in_lab(hostname):
    """Check if the execution is against a host in the lab"""
    return (not utils.in_moblab_ssp()
            and not lsbrelease_utils.is_moblab()
            and utils.host_is_in_lab_zone(hostname))


def get_data_key(prefix, suite, build, board):
    """
    Constructs a key string from parameters.

    @param prefix: Prefix for the generating key.
    @param suite: a suite name. e.g., bvt-cq, bvt-inline, infra_qual
    @param build: The build string. This string should have a consistent
        format eg: x86-mario-release/R26-3570.0.0. If the format of this
        string changes such that we can't determine build_type or branch
        we give up and use the parametes we're sure of instead (suite,
        board). eg:
            1. build = x86-alex-pgo-release/R26-3570.0.0
               branch = 26
               build_type = pgo-release
            2. build = lumpy-paladin/R28-3993.0.0-rc5
               branch = 28
               build_type = paladin
    @param board: The board that this suite ran on.
    @return: The key string used for a dictionary.
    """
    try:
        _board, build_type, branch = ParseBuildName(build)[:3]
    except ParseBuildNameException as e:
        logging.error(str(e))
        branch = 'Unknown'
        build_type = 'Unknown'
    else:
        embedded_str = re.search(r'x86-\w+-(.*)', _board)
        if embedded_str:
            build_type = embedded_str.group(1) + '-' + build_type

    data_key_dict = {
        'prefix': prefix,
        'board': board,
        'branch': branch,
        'build_type': build_type,
        'suite': suite,
    }
    return ('%(prefix)s.%(board)s.%(build_type)s.%(branch)s.%(suite)s'
            % data_key_dict)


def is_shard():
    """Determines if this instance is running as a shard.

    Reads the global_config value shard_hostname in the section SHARD.

    @return True, if shard_hostname is set, False otherwise.
    """
    hostname = CONFIG.get_config_value('SHARD', 'shard_hostname', default=None)
    return bool(hostname)

def is_restricted_user(username):
    """Determines if a user is in a restricted group.

    User in restricted group only have access to main.

    @param username: A string, representing a username.

    @returns: True if the user is in a restricted group.
    """
    if not username:
        return False

    restricted_groups = CONFIG.get_config_value(
            'AUTOTEST_WEB', 'restricted_groups', default='').split(',')
    for group in restricted_groups:
        try:
            if group and username in grp.getgrnam(group).gr_mem:
                return True
        except KeyError as e:
            logging.debug("%s is not a valid group.", group)
    return False


def get_special_task_status(is_complete, success, is_active):
    """Get the status of a special task.

    Emulate a host queue entry status for a special task
    Although SpecialTasks are not HostQueueEntries, it is helpful to
    the user to present similar statuses.

    @param is_complete    Boolean if the task is completed.
    @param success        Boolean if the task succeeded.
    @param is_active      Boolean if the task is active.

    @return The status of a special task.
    """
    if is_complete:
        if success:
            return host_queue_entry_states.Status.COMPLETED
        return host_queue_entry_states.Status.FAILED
    if is_active:
        return host_queue_entry_states.Status.RUNNING
    return host_queue_entry_states.Status.QUEUED


def get_special_task_exec_path(hostname, task_id, task_name, time_requested):
    """Get the execution path of the SpecialTask.

    This method returns different paths depending on where a
    the task ran:
        * main: hosts/hostname/task_id-task_type
        * Shard: main_path/time_created
    This is to work around the fact that a shard can fail independent
    of the main, and be replaced by another shard that has the same
    hosts. Without the time_created stamp the logs of the tasks running
    on the second shard will clobber the logs from the first in google
    storage, because task ids are not globally unique.

    @param hostname        Hostname
    @param task_id         Special task id
    @param task_name       Special task name (e.g., Verify, Repair, etc)
    @param time_requested  Special task requested time.

    @return An execution path for the task.
    """
    results_path = 'hosts/%s/%s-%s' % (hostname, task_id, task_name.lower())

    # If we do this on the main it will break backward compatibility,
    # as there are tasks that currently don't have timestamps. If a host
    # or job has been sent to a shard, the rpc for that host/job will
    # be redirected to the shard, so this global_config check will happen
    # on the shard the logs are on.
    if not is_shard():
        return results_path

    # Generate a uid to disambiguate special task result directories
    # in case this shard fails. The simplest uid is the job_id, however
    # in rare cases tasks do not have jobs associated with them (eg:
    # frontend verify), so just use the creation timestamp. The clocks
    # between a shard and main should always be in sync. Any discrepancies
    # will be brought to our attention in the form of job timeouts.
    uid = time_requested.strftime('%Y%d%m%H%M%S')

    # TODO: This is a hack, however it is the easiest way to achieve
    # correctness. There is currently some debate over the future of
    # tasks in our infrastructure and refactoring everything right
    # now isn't worth the time.
    return '%s/%s' % (results_path, uid)


def get_job_tag(id, owner):
    """Returns a string tag for a job.

    @param id    Job id
    @param owner Job owner

    """
    return '%s-%s' % (id, owner)


def get_hqe_exec_path(tag, execution_subdir):
    """Returns a execution path to a HQE's results.

    @param tag               Tag string for a job associated with a HQE.
    @param execution_subdir  Execution sub-directory string of a HQE.

    """
    return os.path.join(tag, execution_subdir)


def is_inside_chroot():
    """Check if the process is running inside chroot.

    @return: True if the process is running inside chroot.

    """
    return os.path.exists('/etc/cros_chroot_version')


def parse_job_name(name):
    """Parse job name to get information including build, board and suite etc.

    Suite job created by run_suite follows the naming convention of:
    [build]-test_suites/control.[suite]
    For example: lumpy-release/R46-7272.0.0-test_suites/control.bvt
    The naming convention is defined in rpc_interface.create_suite_job.

    Test job created by suite job follows the naming convention of:
    [build]/[suite]/[test name]
    For example: lumpy-release/R46-7272.0.0/bvt/login_LoginSuccess
    The naming convention is defined in
    server/cros/dynamic_suite/tools.create_job_name

    Note that pgo and chrome-perf builds will fail the method. Since lab does
    not run test for these builds, they can be ignored.
    Also, tests for Launch Control builds have different naming convention.
    The build ID will be used as build_version.

    @param name: Name of the job.

    @return: A dictionary containing the test information. The keyvals include:
             build: Name of the build, e.g., lumpy-release/R46-7272.0.0
             build_version: The version of the build, e.g., R46-7272.0.0
             board: Name of the board, e.g., lumpy
             suite: Name of the test suite, e.g., bvt

    """
    info = {}
    suite_job_regex = '([^/]*/[^/]*(?:/\d+)?)-test_suites/control\.(.*)'
    test_job_regex = '([^/]*/[^/]*(?:/\d+)?)/([^/]+)/.*'
    match = re.match(suite_job_regex, name)
    if not match:
        match = re.match(test_job_regex, name)
    if match:
        info['build'] = match.groups()[0]
        info['suite'] = match.groups()[1]
        info['build_version'] = info['build'].split('/')[1]
        try:
            info['board'], _, _, _ = ParseBuildName(info['build'])
        except ParseBuildNameException:
            # Try to parse it as Launch Control build
            # Launch Control builds have name format:
            # branch/build_target-build_type/build_id.
            try:
                _, target, build_id = utils.parse_launch_control_build(
                        info['build'])
                build_target, _ = utils.parse_launch_control_target(target)
                if build_target:
                    info['board'] = build_target
                    info['build_version'] = build_id
            except ValueError:
                pass
    return info


def verify_not_root_user():
    """Simple function to error out if running with uid == 0"""
    if os.getuid() == 0:
        raise error.IllegalUser('This script can not be ran as root.')


def get_hostname_from_machine(machine):
    """Lookup hostname from a machine string or dict.

    @returns: Machine hostname in string format.
    """
    hostname, _ = get_host_info_from_machine(machine)
    return hostname


def get_host_info_from_machine(machine):
    """Lookup host information from a machine string or dict.

    @returns: Tuple of (hostname, afe_host)
    """
    if isinstance(machine, dict):
        return (machine['hostname'], machine['afe_host'])
    else:
        return (machine, EmptyAFEHost())


def get_afe_host_from_machine(machine):
    """Return the afe_host from the machine dict if possible.

    @returns: AFE host object.
    """
    _, afe_host = get_host_info_from_machine(machine)
    return afe_host


def get_connection_pool_from_machine(machine):
    """Returns the ssh_multiplex.ConnectionPool from machine if possible."""
    if not isinstance(machine, dict):
        return None
    return machine.get('connection_pool')


def get_creds_abspath(creds_file):
    """Returns the abspath of the credentials file.

    If creds_file is already an absolute path, just return it.
    Otherwise, assume it is located in the creds directory
    specified in global_config and return the absolute path.

    @param: creds_path, a path to the credentials.
    @return: An absolute path to the credentials file.
    """
    if not creds_file:
        return None
    if os.path.isabs(creds_file):
        return creds_file
    creds_dir = CONFIG.get_config_value('SERVER', 'creds_dir', default='')
    if not creds_dir or not os.path.exists(creds_dir):
        creds_dir = common.autotest_dir
    return os.path.join(creds_dir, creds_file)


@contextlib.contextmanager
def TrivialContextManager(*args, **kwargs):
    """Context manager that does nothing.

    @param *args: Ignored args
    @param **kwargs: Ignored kwargs.
    """
    yield


def _get_default_size_info(path):
    """Get the default result size information.

    In case directory summary is failed to build, assume the test result is not
    throttled and all result sizes are the size of existing test results.

    @return: A namedtuple of result size informations, including:
            client_result_collected_KB: The total size (in KB) of test results
                    collected from test device. Set to be the total size of the
                    given path.
            original_result_total_KB: The original size (in KB) of test results
                    before being trimmed. Set to be the total size of the given
                    path.
            result_uploaded_KB: The total size (in KB) of test results to be
                    uploaded. Set to be the total size of the given path.
            result_throttled: True if test results collection is throttled.
                    It's set to False in this default behavior.
    """
    total_size = file_utils.get_directory_size_kibibytes(path);
    return result_utils_lib.ResultSizeInfo(
            client_result_collected_KB=total_size,
            original_result_total_KB=total_size,
            result_uploaded_KB=total_size,
            result_throttled=False)


def collect_result_sizes(path, log=logging.debug):
    """Collect the result sizes information and build result summary.

    It first tries to merge directory summaries and calculate the result sizes
    including:
    client_result_collected_KB: The volume in KB that's transfered from the test
            device.
    original_result_total_KB: The volume in KB that's the original size of the
            result files before being trimmed.
    result_uploaded_KB: The volume in KB that will be uploaded.
    result_throttled: Indicating if the result files were throttled.

    If directory summary merging failed for any reason, fall back to use the
    total size of the given result directory.

    @param path: Path of the result directory to get size information.
    @param log: The logging method, default to logging.debug
    @return: A ResultSizeInfo namedtuple containing information of test result
             sizes.
    """
    try:
        client_collected_bytes, summary, files = result_utils.merge_summaries(
                path)
        result_size_info = result_utils_lib.get_result_size_info(
                client_collected_bytes, summary)
        html_file = os.path.join(path, result_view.DEFAULT_RESULT_SUMMARY_NAME)
        result_view.build(client_collected_bytes, summary, html_file)

        # Delete all summary files after final view is built.
        for summary_file in files:
            os.remove(summary_file)
    except:
        log('Failed to calculate result sizes based on directory summaries for '
            'directory %s. Fall back to record the total size.\nException: %s' %
            (path, traceback.format_exc()))
        result_size_info = _get_default_size_info(path)

    return result_size_info
