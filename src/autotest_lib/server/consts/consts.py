# Copyright (c) 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.utils.labellib import Key

### Constants for label prefixes
CROS_VERSION_PREFIX = Key.CROS_VERSION
CROS_ANDROID_VERSION_PREFIX = Key.CROS_ANDROID_VERSION
FW_RW_VERSION_PREFIX = Key.FIRMWARE_RW_VERSION
FW_RO_VERSION_PREFIX = Key.FIRMWARE_RO_VERSION
FW_CR50_RW_VERSION_PREFIX = Key.FIRMWARE_CR50_RW_VERSION

# So far the word cheets is only way to distinguish between ARC and Android
# build.
_CROS_ANDROID_BUILD_REGEX = r'.+/cheets.*/P?([0-9]+|LATEST)'


def get_version_label_prefix(image):
    """
    Determine a version label prefix from a given image name.

    Parses `image` to determine what kind of image it refers
    to, and returns the corresponding version label prefix.

    Known version label prefixes are:
      * `CROS_VERSION_PREFIX` for Chrome OS version strings.
        These images have names like `cave-release/R57-9030.0.0`.
      * `CROS_ANDROID_VERSION_PREFIX` for Chrome OS Android version strings.
        These images have names like `git_nyc-arc/cheets_x86-user/3512523`.

    @param image: The image name to be parsed.
    @returns: A string that is the prefix of version labels for the type
              of image identified by `image`.

    """
    if re.match(_CROS_ANDROID_BUILD_REGEX, image, re.I):
        return CROS_ANDROID_VERSION_PREFIX
    else:
        return CROS_VERSION_PREFIX
