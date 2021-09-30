#!/usr/bin/env python3
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Unit tests for server/cros/dynamic_suite/dynamic_suite.py."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import OrderedDict
from mock import patch, call
import os
import six
import shutil
import tempfile
import unittest

from autotest_lib.client.common_lib import control_data
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros import provision
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import suite as SuiteBase
from autotest_lib.server.cros.dynamic_suite import suite_common
from autotest_lib.server.cros.dynamic_suite.fakes import FakeControlData
from autotest_lib.server.cros.dynamic_suite.fakes import FakeMultiprocessingPool


class TypeMatcher(object):
    """Matcher for object is of type."""

    def __init__(self, expected_type):
        self.expected_type = expected_type

    def __eq__(self, other):
        return isinstance(other, self.expected_type)


class SuiteTest(unittest.TestCase):
    """Unit tests for dynamic_suite Suite class.

    @var _BUILDS: fake build
    @var _TAG: fake suite tag
    """

    _BOARD = 'board:board'
    _BUILDS = {provision.CROS_VERSION_PREFIX:'build_1',
               provision.FW_RW_VERSION_PREFIX:'fwrw_build_1'}
    _TAG = 'au'
    _ATTR = {'attr:attr'}
    _DEVSERVER_HOST = 'http://dontcare:8080'
    _FAKE_JOB_ID = 10

    def setUp(self):
        """Setup."""
        super(SuiteTest, self).setUp()
        self.maxDiff = None
        self.use_batch = suite_common.ENABLE_CONTROLS_IN_BATCH
        suite_common.ENABLE_CONTROLS_IN_BATCH = False
        self.tmpdir = tempfile.mkdtemp(suffix=type(self).__name__)
        getter_patch = patch.object(control_file_getter, 'ControlFileGetter')
        self.getter = getter_patch.start()
        self.addCleanup(getter_patch.stop)
        self.devserver = dev_server.ImageServer(self._DEVSERVER_HOST)

        self.files = OrderedDict(
                [('one', FakeControlData(self._TAG, self._ATTR, 'data_one',
                                         'FAST', job_retries=None)),
                 ('two', FakeControlData(self._TAG, self._ATTR, 'data_two',
                                         'SHORT', dependencies=['feta'])),
                 ('three', FakeControlData(self._TAG, self._ATTR, 'data_three',
                                           'MEDIUM')),
                 ('four', FakeControlData('other', self._ATTR, 'data_four',
                                          'LONG', dependencies=['arugula'])),
                 ('five', FakeControlData(self._TAG, {'other'}, 'data_five',
                                          'LONG', dependencies=['arugula',
                                                                'caligula'])),
                 ('six', FakeControlData(self._TAG, self._ATTR, 'data_six',
                                         'LENGTHY')),
                 ('seven', FakeControlData(self._TAG, self._ATTR, 'data_seven',
                                           'FAST', job_retries=1))])

        self.files_to_filter = {
            'with/deps/...': FakeControlData(self._TAG, self._ATTR,
                                             'gets filtered'),
            'with/profilers/...': FakeControlData(self._TAG, self._ATTR,
                                                  'gets filtered')}

    def additional_mocking(self):
        patcher = patch.object(control_data, 'parse_control_string')
        self.cf_getter_string = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        """Teardown."""
        suite_common.ENABLE_CONTROLS_IN_BATCH = self.use_batch
        super(SuiteTest, self).tearDown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def expect_control_file_parsing(self, suite_name=_TAG):
        """Expect an attempt to parse the 'control files' in |self.files|.

        @param suite_name: The suite name to parse control files for.
        """
        all_files = list(self.files.keys()) + list(self.files_to_filter.keys())
        self._set_control_file_parsing_expectations(False, all_files,
                                                    self.files, suite_name)

    def _set_control_file_parsing_expectations(self, already_stubbed,
                                               file_list, files_to_parse,
                                               suite_name):
        """Expect an attempt to parse the 'control files' in |files|.

        @param already_stubbed: parse_control_string already stubbed out.
        @param file_list: the files the dev server returns
        @param files_to_parse: the {'name': FakeControlData} dict of files we
                               expect to get parsed.
        """
        if not already_stubbed:
            self.additional_mocking()
        patcher = patch.object(suite_common.multiprocessing, 'Pool')
        self.mp_pool = patcher.start()
        self.addCleanup(patcher.stop)
        self.mp_pool.return_value = FakeMultiprocessingPool()

        self.getter.get_control_file_list.return_value = file_list
        get_control_file_contents_mock_list = []
        parse_mock_list = []
        for file, data in six.iteritems(files_to_parse):
            get_control_file_contents_mock_list.append(data.string)

            parse_mock_list.append(data)

        self.getter.get_control_file_contents.side_effect = get_control_file_contents_mock_list
        self.cf_getter_string.side_effect = parse_mock_list

    def expect_control_file_parsing_in_batch(self, suite_name=_TAG):
        """Expect an attempt to parse the contents of all control files in
        |self.files| and |self.files_to_filter|, form them to a dict.

        @param suite_name: The suite name to parse control files for.
        """
        DevServerGetter_patch = patch.object(control_file_getter,
                                             'DevServerGetter')
        self.getter = DevServerGetter_patch.start()
        self.addCleanup(DevServerGetter_patch.stop)

        patcher = patch.object(suite_common.multiprocessing, 'Pool')
        mp_pool = patcher.start()
        self.addCleanup(patcher.stop)
        mp_pool.return_value = FakeMultiprocessingPool()

        suite_info = {}
        thel = []
        expected_calls = []
        for k, v in six.iteritems(self.files):
            suite_info[k] = v.string
            thel.append(v)
            expected_calls.append(call(v.string, raise_warnings=True, path=k))
        self.cf_getter_string.side_effect = (thel)
        for k, v in six.iteritems(self.files_to_filter):
            suite_info[k] = v.string
        self.getter._dev_server = self._DEVSERVER_HOST
        self.getter.get_suite_info.return_value = suite_info
        return expected_calls

    def testFindAllTestInBatch(self):
        """Test switch on enable_getting_controls_in_batch for function
        find_all_test."""
        self.additional_mocking()
        self.use_batch = suite_common.ENABLE_CONTROLS_IN_BATCH
        expected_calls = self.expect_control_file_parsing_in_batch()
        suite_common.ENABLE_CONTROLS_IN_BATCH = True

        with patch.object(suite_common, '_should_batch_with') as sbw_mock:
            sbw_mock.return_value = True

            predicate = lambda d: d.suite == self._TAG
            tests = SuiteBase.find_and_parse_tests(self.getter, predicate,
                                                   self._TAG)
            self.assertEquals(len(tests), 6)
            self.assertTrue(self.files['one'] in tests)
            self.assertTrue(self.files['two'] in tests)
            self.assertTrue(self.files['three'] in tests)
            self.assertTrue(self.files['five'] in tests)
            self.assertTrue(self.files['six'] in tests)
            self.assertTrue(self.files['seven'] in tests)
            suite_common.ENABLE_CONTROLS_IN_BATCH = self.use_batch

        self.cf_getter_string.assert_has_calls(expected_calls, any_order=True)

    def testFindAndParseStableTests(self):
        """Should find only tests that match a predicate."""
        self.additional_mocking()

        self.expect_control_file_parsing()

        predicate = lambda d: d.text == self.files['two'].string
        tests = SuiteBase.find_and_parse_tests(self.getter,
                                               predicate,
                                               self._TAG)
        self.assertEquals(len(tests), 1)
        self.assertEquals(tests[0], self.files['two'])

    def testFindSuiteSyntaxErrors(self):
        """Check all control files for syntax errors.

        This test actually parses all control files in the autotest directory
        for syntax errors, by using the un-forgiving parser and pretending to
        look for all control files with the suite attribute.
        """

        autodir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        fs_getter = SuiteBase.create_fs_getter(autodir)
        predicate = lambda t: hasattr(t, 'suite')
        SuiteBase.find_and_parse_tests(fs_getter, predicate,
                                       forgiving_parser=False)

    def testFindAndParseTestsSuite(self):
        """Should find all tests that match a predicate."""
        self.additional_mocking()
        self.expect_control_file_parsing()

        predicate = lambda d: d.suite == self._TAG
        tests = SuiteBase.find_and_parse_tests(self.getter,
                                               predicate,
                                               self._TAG)
        self.assertEquals(len(tests), 6)
        self.assertTrue(self.files['one'] in tests)
        self.assertTrue(self.files['two'] in tests)
        self.assertTrue(self.files['three'] in tests)
        self.assertTrue(self.files['five'] in tests)
        self.assertTrue(self.files['six'] in tests)
        self.assertTrue(self.files['seven'] in tests)

    def testFindAndParseTestsAttr(self):
        """Should find all tests that match a predicate."""
        self.additional_mocking()
        self.expect_control_file_parsing()

        predicate = SuiteBase.matches_attribute_expression_predicate('attr:attr')
        tests = SuiteBase.find_and_parse_tests(self.getter,
                                               predicate,
                                               self._TAG)
        self.assertEquals(len(tests), 6)
        self.assertTrue(self.files['one'] in tests)
        self.assertTrue(self.files['two'] in tests)
        self.assertTrue(self.files['three'] in tests)
        self.assertTrue(self.files['four'] in tests)
        self.assertTrue(self.files['six'] in tests)
        self.assertTrue(self.files['seven'] in tests)


if __name__ == "__main__":
    unittest.main()
