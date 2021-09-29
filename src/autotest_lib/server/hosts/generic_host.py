# Lint as: python2, python3
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.hosts import abstract_ssh


class GenericHost(abstract_ssh.AbstractSSHHost):
    """Chromium OS specific subclass of Host."""

    @staticmethod
    def check_host(host, timeout=10):
        """Check if the host is alive."""
        try:
            host.run('test -e')

            return True
        except Exception:
            return False

    def _initialize(self, hostname, *args, **dargs):
        """Initialize superclasses."""
        super(GenericHost, self)._initialize(hostname=hostname, *args, **dargs)
