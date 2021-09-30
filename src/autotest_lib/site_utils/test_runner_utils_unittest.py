#!/usr/bin/env python3
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from autotest_lib.server.hosts import host_info
from autotest_lib.site_utils import test_runner_utils


class TypeMatcher(object):
    """Matcher for object is of type."""

    def __init__(self, expected_type):
        self.expected_type = expected_type

    def __eq__(self, other):
        return isinstance(other, self.expected_type)


class ContainsMatcher:
    """Matcher for object contains attr."""

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __eq__(self, rhs):
        try:
            return getattr(rhs, self._key) == self._value
        except Exception:
            return False


class SampleJob(object):
    """Sample to be used for mocks."""

    def __init__(self, id=1):
        self.id = id


class FakeTests(object):
    """A fake test to be used for mocks."""

    def __init__(self, text, deps=[]):
        self.text = text
        self.test_type = 'client'
        self.dependencies = deps
        self.name = None


class TestRunnerUnittests(unittest.TestCase):
    """Test test_runner_utils."""

    autotest_path = 'ottotest_path'
    suite_name = 'sweet_name'
    test_arg = 'suite:' + suite_name
    remote = 'remoat'
    build = 'bild'
    board = 'bored'
    fast_mode = False
    suite_control_files = ['c1', 'c2', 'c3', 'c4']
    results_dir = '/tmp/test_that_results_fake'
    id_digits = 1
    ssh_verbosity = 2
    ssh_options = '-F /dev/null -i /dev/null'
    args = 'matey'
    retry = True

    def _results_directory_from_results_list(self, results_list):
        """Generate a temp directory filled with provided test results.

        @param results_list: List of results, each result is a tuple of strings
                             (test_name, test_status_message).
        @returns: Absolute path to the results directory.
        """
        global_dir = tempfile.mkdtemp()
        for index, (test_name, test_status_message) in enumerate(results_list):
            dir_name = '-'.join(['results',
                                 "%02.f" % (index + 1),
                                 test_name])
            local_dir = os.path.join(global_dir, dir_name)
            os.mkdir(local_dir)
            os.mkdir('%s/debug' % local_dir)
            with open("%s/status.log" % local_dir, mode='w+') as status:
                status.write(test_status_message)
                status.flush()
        return global_dir


    def test_generate_report_status_code_success_with_retries(self):
        global_dir = self._results_directory_from_results_list([
            ("dummy_Flaky", "FAIL"),
            ("dummy_Flaky", "GOOD: nonexistent test completed successfully")])
        status_code = test_runner_utils.generate_report(
            global_dir, just_status_code=True)
        self.assertEquals(status_code, 0)
        shutil.rmtree(global_dir)


    def test_generate_report_status_code_failure_with_retries(self):
        global_dir = self._results_directory_from_results_list([
            ("dummy_Good", "GOOD: nonexistent test completed successfully"),
            ("dummy_Bad", "FAIL"),
            ("dummy_Bad", "FAIL")])
        status_code = test_runner_utils.generate_report(
            global_dir, just_status_code=True)
        self.assertNotEquals(status_code, 0)
        shutil.rmtree(global_dir)


    def test_perform_local_run(self):
        """Test a local run that should pass."""
        patcher = patch.object(test_runner_utils, '_auto_detect_labels')
        _auto_detect_labels_mock = patcher.start()
        self.addCleanup(patcher.stop)

        _auto_detect_labels_mock.return_value = [
                'os:cros', 'has_chameleon:True'
        ]

        patcher3 = patch.object(test_runner_utils, 'run_job')
        run_job_mock = patcher3.start()
        self.addCleanup(patcher3.stop)

        for control_file in self.suite_control_files:
            run_job_mock.return_value = (0, '/fake/dir')
        test_runner_utils.perform_local_run(self.autotest_path, ['mock_test'],
                                            self.remote,
                                            self.fast_mode,
                                            build=self.build,
                                            board=self.board,
                                            ssh_verbosity=self.ssh_verbosity,
                                            ssh_options=self.ssh_options,
                                            args=self.args,
                                            results_directory=self.results_dir,
                                            job_retry=self.retry,
                                            ignore_deps=False)
        run_job_mock.assert_called_with('mock_test',
                                        self.remote,
                                        TypeMatcher(host_info.HostInfo),
                                        self.autotest_path,
                                        self.results_dir,
                                        self.fast_mode,
                                        self.id_digits,
                                        self.ssh_verbosity,
                                        self.ssh_options,
                                        TypeMatcher(str),
                                        False,
                                        False,
                                        None,
                                        n=1)

if __name__ == '__main__':
    unittest.main()
