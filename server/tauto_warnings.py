import logging


def repair_provision_warn_and_error():
    """Log a warning then raise an error if repair or provision is called."""
    logging.warning(
        "Repair is (currently) depricated and being moved to lab services.")
