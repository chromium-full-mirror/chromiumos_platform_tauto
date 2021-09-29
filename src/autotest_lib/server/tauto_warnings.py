import logging

from autotest_lib.client.common_lib import error


def lab_services_warn_and_error(cmd, err=True):
    """Log a warning & (optional) err if the given dut service is called."""
    logging.warning(
            "%s is (currently) depricated and being moved to dut-services.",
            cmd)
    if err:
        raise error.LabServicesNotWired("%s not yet wired." % cmd)
