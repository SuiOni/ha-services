import logging
from unittest import TestCase

from ha_services.mqtt4homeassistant.utilities.error_handling import LogErrors


class LogErrorsTestCase(TestCase):
    def test_happy_path(self):
        logger = logging.getLogger('test_logger_no_exception')

        log_output = []
        handler = logging.StreamHandler(log_output)
        handler.emit = lambda record: log_output.append(record.getMessage())
        logger.handlers = [handler]

        with LogErrors(logger):
            pass
        self.assertEqual(log_output, [])

        with LogErrors(logger):
            raise ValueError('Test error')
        self.assertEqual(log_output, ['Exception suppressed: Test error'])
