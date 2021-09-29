#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This is a convenience module to import all available types of hosts.

Implementation details:
You should 'import hosts' instead of importing every available host module.
"""

# host abstract classes
from autotest_lib.server.hosts.base_classes import Host
from autotest_lib.server.hosts.remote import RemoteHost

# factory function
from autotest_lib.server.hosts.factory import create_host
from autotest_lib.server.hosts.factory import create_target_machine
from autotest_lib.server.hosts.factory import create_companion_hosts
