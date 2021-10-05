# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from setuptools import find_packages, setup

setup(
    name='autotest_lib',
    version='1.0',
    description='Tauto harness package',
    packages=find_packages(),
    package_data={'': ['*']},
    entry_points={
        'console_scripts': [
            'tauto = autotest_lib.client.bin.autotest',
            'tauto_client = autotest_lib.client.bin.autotest_client',
            'tautod = autotest_lib.client.bin.autotestd',
            'tautod_monitor = autotest_lib.client.bin.autotestd_monitor',
        ]
    }
)
