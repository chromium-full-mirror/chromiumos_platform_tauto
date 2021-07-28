# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from autotest_lib.server import test
from autotest_lib.client.common_lib import error


class infra_ServerFail(test.test):
    """A server test which fails."""
    version = 1

    def run_once(self):
        """Starting point of this test."""
        raise error.TestError("Server side test correctly failing")
