import logging
import platform
import statistics
import typing

import psutil
from paho.mqtt.client import Client

from ha_services.mqtt4homeassistant.components.sensor import Sensor
from ha_services.mqtt4homeassistant.utilities.string_utils import slugify


if typing.TYPE_CHECKING:
    from ha_services.mqtt4homeassistant.device import MqttDevice


logger = logging.getLogger(__name__)


def _get_temperatures() -> dict:
    """Get temperature sensors data, return empty dict if not available."""
    if platform.system() != 'Linux':
        logger.debug('Temperature sensors not available on %s', platform.system())
        return {}

    try:
        return psutil.sensors_temperatures()  # type: ignore[attr-defined]
    except AttributeError:
        logger.debug('psutil.sensors_temperatures() not available')
        return {}


def median_temperatures(temperatures: dict) -> dict:
    result = {}
    for sensor, temps in temperatures.items():
        currents = [temp.current for temp in temps]
        result[sensor] = statistics.median(currents)
    return result


def get_median_temperatures() -> dict:
    temperatures = _get_temperatures()
    return median_temperatures(temperatures)


class TemperaturesSensors:
    def __init__(self, device: 'MqttDevice'):
        self.device = device

        self.sensors = {}

        temperatures = _get_temperatures()
        for name in temperatures.keys():
            logger.info('Creating temperature sensor: %r', name)
            sensor = Sensor(
                device=self.device,
                name=f'Temperature {name}',
                uid=slugify(f'temperature_{name}'),
                device_class='temperature',
                state_class='measurement',
                unit_of_measurement='°C',
                suggested_display_precision=0,
            )
            self.sensors[name] = sensor

    def publish(self, client: Client) -> None:
        temperatures = get_median_temperatures()
        for name, median_temperature in temperatures.items():
            sensor = self.sensors[name]
            sensor.set_state(median_temperature)
            sensor.publish(client)
