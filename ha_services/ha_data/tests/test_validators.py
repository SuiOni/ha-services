import unittest

from ha_services.ha_data.validators import ValidationError, validate_sensor


class ValidateSensorTestCase(unittest.TestCase):
    def test_happy_path(self):
        validate_sensor(device_class=None, state_class=None, unit_of_measurement=None)
        validate_sensor(device_class='battery', state_class='measurement', unit_of_measurement='%')

        with self.assertRaises(ValidationError):
            validate_sensor(device_class='invalid_class', state_class=None, unit_of_measurement=None)

        with self.assertRaises(ValidationError):
            validate_sensor(device_class='battery', state_class='invalid_state', unit_of_measurement=None)

        with self.assertRaises(ValidationError):
            validate_sensor(device_class='battery', state_class='measurement', unit_of_measurement='invalid_unit')
