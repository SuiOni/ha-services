import logging


class LogErrors:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.logger.exception(
                'Exception suppressed: %s',
                exc_value,
                exc_info=(exc_type, exc_value, traceback),
            )
            return True  # Suppress the exception
        return False
