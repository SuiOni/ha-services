import abc
import json
import logging
import time
import typing
from functools import cache

from frozendict import frozendict
from paho.mqtt.client import Client, MQTTMessageInfo

import ha_services
from ha_services.exceptions import InvalidStateValue
from ha_services.mqtt4homeassistant.data_classes import NO_STATE, ComponentConfig, ComponentState, StatePayload
from ha_services.mqtt4homeassistant.utilities.assertments import assert_uid


if typing.TYPE_CHECKING:
    from ha_services.mqtt4homeassistant.device import MqttDevice


logger = logging.getLogger(__name__)


@cache
def get_origin_data() -> dict:
    return {
        'name': 'ha-services',
        'sw_version': ha_services.__version__,
        'support_url': 'https://pypi.org/project/ha_services/',
    }


class BaseComponent(abc.ABC):
    def __init__(
        self,
        *,
        device: 'MqttDevice',
        name: str,
        uid: str,
        component: str,
        initial_state=NO_STATE,  # set_state() must be called to set the value
        qos: int = 0,
        retain: bool = False,
    ):
        self.device = device

        self.name = name

        assert_uid(uid)
        self.uid = f'{self.device.uid}-{uid}'

        assert component
        self.component = component
        self.device.register_component(component=self)

        # e.g.: 'homeassistant/sensor/My-device/Chip-Temperature'
        self.topic_prefix = f'{self.device.topic_prefix}/{self.component}/{self.device.uid}/{self.uid}'

        self._config_kwargs_cache = None
        self._next_config_publish = 0

        self.state = initial_state
        self.qos = qos
        self.retain = retain

    def _get_config_kwargs(self) -> dict:
        if self._config_kwargs_cache is None:
            config: ComponentConfig = self.get_config()
            payload = config.payload
            payload['origin'] = get_origin_data()
            payload = json.dumps(config.payload, ensure_ascii=False, sort_keys=True)
            self._config_kwargs_cache = frozendict(
                {
                    'topic': config.topic,
                    'payload': payload,
                    'qos': config.qos,
                    'retain': config.retain,
                }
            )
        return self._config_kwargs_cache

    def publish_config(self, client: Client) -> MQTTMessageInfo | None:
        if self._next_config_publish > time.monotonic():
            logger.debug(f'Publishing {self.uid=} config: throttled')
            return None

        config_kwargs = self._get_config_kwargs()
        logger.info(f'Publishing {self.uid=} config: {config_kwargs}')
        info: MQTTMessageInfo = client.publish(**config_kwargs)

        self._next_config_publish = time.monotonic() + self.device.config_throttle_sec
        logger.debug(
            f'Next {self.uid=} config publish: {self._next_config_publish} {self.device.config_throttle_sec=}'
        )

        return info

    def publish_state(self, client: Client) -> MQTTMessageInfo | None:
        if self.state is NO_STATE:
            logging.warning(f'Sensor {self.uid=} state is not set!')
            return None

        state: ComponentState = self.get_state()
        logger.debug(f'Publishing {self.uid=} state: {state}')
        info: MQTTMessageInfo = client.publish(
            topic=state.topic,
            payload=state.payload,
            qos=self.qos,
            retain=self.retain,
        )
        return info

    def publish(self, client: Client) -> tuple[MQTTMessageInfo | None, MQTTMessageInfo | None]:
        config_info = self.publish_config(client)
        state_info = self.publish_state(client)
        return config_info, state_info

    @abc.abstractmethod
    def validate_state(self, state: StatePayload):
        """
        raise InvalidStateValue if state is not valid
        """
        if state is NO_STATE:
            raise InvalidStateValue(component=self, error_msg=f'Set {self.uid=} {state=} is not allowed')

    def set_state(self, state: str):
        self.validate_state(state)
        logger.debug('Set state %r for %r', state, self.uid)
        self.state = state

    @abc.abstractmethod
    def get_state(self) -> ComponentState:
        pass

    @abc.abstractmethod
    def get_config(self) -> ComponentConfig:
        pass

    def __str__(self):
        return f'{self.__class__.__name__}({self.uid=})'

    def __repr__(self):
        return f'<{self} {id(self)}>'
