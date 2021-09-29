# Lint as: python2, python3
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import difflib
import logging
import operator
import os
import re
import six

from autotest_lib.server.cros.dynamic_suite import boolparse_lib
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import suite_common


class _ControlFileRetriever(object):
    """Retrieves control files.

    This returns control data instances, unlike control file getters
    which simply return the control file text contents.
    """

    def __init__(self, cf_getter, forgiving_parser=True, run_prod_code=False,
                 test_args=None):
        """Initialize instance.

        @param cf_getter: a control_file_getter.ControlFileGetter used to list
               and fetch the content of control files
        @param forgiving_parser: If False, will raise ControlVariableExceptions
                                 if any are encountered when parsing control
                                 files. Note that this can raise an exception
                                 for syntax errors in unrelated files, because
                                 we parse them before applying the predicate.
        @param run_prod_code: If true, the retrieved tests will run the test
                              code that lives in prod aka the test code
                              currently on the lab servers by disabling
                              SSP for the discovered tests.
        @param test_args: A dict of args to be seeded in test control file under
                          the name |args_dict|.
        """
        self._cf_getter = cf_getter
        self._forgiving_parser = forgiving_parser
        self._run_prod_code = run_prod_code
        self._test_args = test_args


    def retrieve_for_test(self, test_name):
        """Retrieve a test's control data.

        This ignores forgiving_parser because we cannot return a
        forgiving value.

        @param test_name: Name of test to retrieve.

        @raises ControlVariableException: There is a syntax error in a
                                          control file.

        @returns a ControlData object
        """
        return suite_common.retrieve_control_data_for_test(
                self._cf_getter, test_name)


    def retrieve_for_suite(self, suite_name=''):
        """Scan through all tests and find all tests.

        @param suite_name: If specified, this method will attempt to restrain
                           the search space to just this suite's control files.

        @raises ControlVariableException: If forgiving_parser is False and there
                                          is a syntax error in a control file.

        @returns a dictionary of ControlData objects that based on given
                 parameters.
        """
        tests = suite_common.retrieve_for_suite(
                self._cf_getter, suite_name, self._forgiving_parser,
                self._test_args)
        if self._run_prod_code:
            for test in six.itervalues(tests):
                test.require_ssp = False

        return tests


def list_all_suites(build, devserver, cf_getter=None):
    """
    Parses all ControlData objects with a SUITE tag and extracts all
    defined suite names.

    @param build: the build on which we're running this suite.
    @param devserver: the devserver which contains the build.
    @param cf_getter: control_file_getter.ControlFileGetter. Defaults to
                      using DevServerGetter.

    @return list of suites
    """
    if cf_getter is None:
        cf_getter = _create_ds_getter(build, devserver)

    suites = set()
    predicate = lambda t: True
    for test in find_and_parse_tests(cf_getter, predicate):
        suites.update(test.suite_tag_parts)
    return list(suites)


def test_file_similarity_predicate(test_file_pattern):
    """Returns predicate that gets the similarity based on a test's file
    name pattern.

    Builds a predicate that takes in a parsed control file (a ControlData)
    and returns a tuple of (file path, ratio), where ratio is the
    similarity between the test file name and the given test_file_pattern.

    @param test_file_pattern: regular expression (string) to match against
                              control file names.
    @return a callable that takes a ControlData and and returns a tuple of
            (file path, ratio), where ratio is the similarity between the
            test file name and the given test_file_pattern.
    """
    return lambda t: ((None, 0) if not hasattr(t, 'path') else
            (t.path, difflib.SequenceMatcher(a=t.path,
                                             b=test_file_pattern).ratio()))


def test_name_similarity_predicate(test_name):
    """Returns predicate that matched based on a test's name.

    Builds a predicate that takes in a parsed control file (a ControlData)
    and returns a tuple of (test name, ratio), where ratio is the similarity
    between the test name and the given test_name.

    @param test_name: the test name to base the predicate on.
    @return a callable that takes a ControlData and returns a tuple of
            (test name, ratio), where ratio is the similarity between the
            test name and the given test_name.
    """
    return lambda t: ((None, 0) if not hasattr(t, 'name') else
            (t.name,
             difflib.SequenceMatcher(a=t.name, b=test_name).ratio()))


def matches_attribute_expression_predicate(test_attr_boolstr):
    """Returns predicate that matches based on boolean expression of
    attributes.

    Builds a predicate that takes in a parsed control file (a ControlData)
    ans returns True if the test attributes satisfy the given attribute
    boolean expression.

    @param test_attr_boolstr: boolean expression of the attributes to be
                              test, like 'system:all and interval:daily'.

    @return a callable that takes a ControlData and returns True if the test
            attributes satisfy the given boolean expression.
    """
    return lambda t: boolparse_lib.BoolstrResult(
        test_attr_boolstr, t.attributes)


def test_file_matches_pattern_predicate(test_file_pattern):
    """Returns predicate that matches based on a test's file name pattern.

    Builds a predicate that takes in a parsed control file (a ControlData)
    and returns True if the test's control file name matches the given
    regular expression.

    @param test_file_pattern: regular expression (string) to match against
                              control file names.
    @return a callable that takes a ControlData and and returns
            True if control file name matches the pattern.
    """
    return lambda t: hasattr(t, 'path') and re.match(test_file_pattern,
                                                     t.path)


def test_name_matches_pattern_predicate(test_name_pattern):
    """Returns predicate that matches based on a test's name pattern.

    Builds a predicate that takes in a parsed control file (a ControlData)
    and returns True if the test name matches the given regular expression.

    @param test_name_pattern: regular expression (string) to match against
                              test names.
    @return a callable that takes a ControlData and returns
            True if the name fields matches the pattern.
    """
    return lambda t: hasattr(t, 'name') and re.match(test_name_pattern,
                                                     t.name)


def test_name_equals_predicate(test_name):
    """Returns predicate that matched based on a test's name.

    Builds a predicate that takes in a parsed control file (a ControlData)
    and returns True if the test name is equal to |test_name|.

    @param test_name: the test name to base the predicate on.
    @return a callable that takes a ControlData and looks for |test_name|
            in that ControlData's name.
    """
    return lambda t: hasattr(t, 'name') and test_name == t.name


def name_in_tag_similarity_predicate(name):
    """Returns predicate that takes a control file and gets the similarity
    of the suites in the control file and the given name.

    Builds a predicate that takes in a parsed control file (a ControlData)
    and returns a list of tuples of (suite name, ratio), where suite name
    is each suite listed in the control file, and ratio is the similarity
    between each suite and the given name.

    @param name: the suite name to base the predicate on.
    @return a callable that takes a ControlData and returns a list of tuples
            of (suite name, ratio), where suite name is each suite listed in
            the control file, and ratio is the similarity between each suite
            and the given name.
    """
    return lambda t: [(suite,
                       difflib.SequenceMatcher(a=suite, b=name).ratio())
                      for suite in t.suite_tag_parts] or [(None, 0)]


def name_in_tag_predicate(name):
    """Returns predicate that takes a control file and looks for |name|.

    Builds a predicate that takes in a parsed control file (a ControlData)
    and returns True if the SUITE tag is present and contains |name|.

    @param name: the suite name to base the predicate on.
    @return a callable that takes a ControlData and looks for |name| in that
            ControlData object's suite member.
    """
    return suite_common.name_in_tag_predicate(name)


def create_fs_getter(autotest_dir):
    """
    @param autotest_dir: the place to find autotests.
    @return a FileSystemGetter instance that looks under |autotest_dir|.
    """
    # currently hard-coded places to look for tests.
    subpaths = ['server/site_tests', 'client/site_tests']
    directories = [os.path.join(autotest_dir, p) for p in subpaths]
    return control_file_getter.FileSystemGetter(directories)


def _create_ds_getter(build, devserver):
    """
    @param build: the build on which we're running this suite.
    @param devserver: the devserver which contains the build.
    @return a FileSystemGetter instance that looks under |autotest_dir|.
    """
    return control_file_getter.DevServerGetter(build, devserver)


def _non_experimental_tests_predicate(test_data):
    """Test predicate for non-experimental tests."""
    return not test_data.experimental


def find_and_parse_tests(cf_getter, predicate, suite_name='',
                         add_experimental=False, forgiving_parser=True,
                         run_prod_code=False, test_args=None):
    """
    Function to scan through all tests and find eligible tests.

    Search through all tests based on given cf_getter, suite_name,
    add_experimental and forgiving_parser, return the tests that match
    given predicate.

    @param cf_getter: a control_file_getter.ControlFileGetter used to list
           and fetch the content of control files
    @param predicate: a function that should return True when run over a
           ControlData representation of a control file that should be in
           this Suite.
    @param suite_name: If specified, this method will attempt to restrain
                       the search space to just this suite's control files.
    @param add_experimental: add tests with experimental attribute set.
    @param forgiving_parser: If False, will raise ControlVariableExceptions
                             if any are encountered when parsing control
                             files. Note that this can raise an exception
                             for syntax errors in unrelated files, because
                             we parse them before applying the predicate.
    @param run_prod_code: If true, the suite will run the test code that
                          lives in prod aka the test code currently on the
                          lab servers by disabling SSP for the discovered
                          tests.
    @param test_args: A dict of args to be seeded in test control file.

    @raises ControlVariableException: If forgiving_parser is False and there
                                      is a syntax error in a control file.

    @return list of ControlData objects that should be run, with control
            file text added in |text| attribute. Results are sorted based
            on the TIME setting in control file, slowest test comes first.
    """
    logging.debug('Getting control file list for suite: %s', suite_name)
    retriever = _ControlFileRetriever(cf_getter,
                                      forgiving_parser=forgiving_parser,
                                      run_prod_code=run_prod_code,
                                      test_args=test_args)
    tests = retriever.retrieve_for_suite(suite_name)
    if not add_experimental:
        predicate = _ComposedPredicate([predicate,
                                        _non_experimental_tests_predicate])
    return suite_common.filter_tests(tests, predicate)


def find_possible_tests(cf_getter, predicate, suite_name='', count=10):
    """
    Function to scan through all tests and find possible tests.

    Search through all tests based on given cf_getter, suite_name,
    add_experimental and forgiving_parser. Use the given predicate to
    calculate the similarity and return the top 10 matches.

    @param cf_getter: a control_file_getter.ControlFileGetter used to list
           and fetch the content of control files
    @param predicate: a function that should return a tuple of (name, ratio)
           when run over a ControlData representation of a control file that
           should be in this Suite. `name` is the key to be compared, e.g.,
           a suite name or test name. `ratio` is a value between [0,1]
           indicating the similarity of `name` and the value to be compared.
    @param suite_name: If specified, this method will attempt to restrain
                       the search space to just this suite's control files.
    @param count: Number of suggestions to return, default to 10.

    @return list of top names that similar to the given test, sorted by
            match ratio.
    """
    logging.debug('Getting control file list for suite: %s', suite_name)
    tests = _ControlFileRetriever(cf_getter).retrieve_for_suite(suite_name)
    logging.debug('Parsed %s control files.', len(tests))
    similarities = {}
    for test in six.itervalues(tests):
        ratios = predicate(test)
        # Some predicates may return a list of tuples, e.g.,
        # name_in_tag_similarity_predicate. Convert all returns to a list.
        if not isinstance(ratios, list):
            ratios = [ratios]
        for name, ratio in ratios:
            similarities[name] = ratio
    return [s[0] for s in
            sorted(list(similarities.items()), key=operator.itemgetter(1),
                   reverse=True)][:count]


class _ComposedPredicate(object):
    """Return the composition of the predicates.

    Predicates are functions that take a test control data object and
    return True of that test is to be included.  The returned
    predicate's set is the intersection of all of the input predicates'
    sets (it returns True if all predicates return True).
    """

    def __init__(self, predicates):
        """Initialize instance.

        @param predicates: Iterable of predicates.
        """
        self._predicates = list(predicates)

    def __repr__(self):
        return '{cls}({this._predicates!r})'.format(
            cls=type(self).__name__,
            this=self,
        )

    def __call__(self, control_data_):
        return all(f(control_data_) for f in self._predicates)
