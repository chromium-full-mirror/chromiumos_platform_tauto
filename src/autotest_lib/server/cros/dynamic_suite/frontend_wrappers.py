# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math


def convert_timeout_to_retry(backoff, timeout_min, delay_sec):
    """Compute the number of retry attempts for use with chromite.retry_util.

    @param backoff: The exponential backoff factor.
    @param timeout_min: The maximum amount of time (in minutes) to sleep.
    @param delay_sec: The amount to sleep (in seconds) between each attempt.

    @return: The number of retry attempts in the case of exponential backoff.
    """
    # Estimate the max_retry in the case of exponential backoff:
    # => total_sleep = sleep*sum(r=0..max_retry-1, backoff^r)
    # => total_sleep = sleep( (1-backoff^max_retry) / (1-backoff) )
    # => max_retry*ln(backoff) = ln(1-(total_sleep/sleep)*(1-backoff))
    # => max_retry = ln(1-(total_sleep/sleep)*(1-backoff))/ln(backoff)
    total_sleep = timeout_min * 60
    numerator = math.log10(1 - (total_sleep / delay_sec) * (1 - backoff))
    denominator = math.log10(backoff)
    return int(math.ceil(numerator / denominator))


class RetryingAFE():
    """Wrapper around frontend.AFE that retries all RPCs.

    Timeout for retries and delay between retries are configurable.
    """

    def __init__(self, **dargs):
        """Constructor

        @param timeout_min: timeout in minutes until giving up.
        @param delay_sec: pre-jittered delay between retries in seconds.
        """
        return


class RetryingTKO():
    """Wrapper around frontend.TKO that retries all RPCs.

    Timeout for retries and delay between retries are configurable.
    """

    def __init__(self, **dargs):
        """Constructor

        @param timeout_min: timeout in minutes until giving up.
        @param delay_sec: pre-jittered delay between retries in seconds.
        """
        return
