from __future__ import annotations

import json
import logging
import time

from collections.abc import Callable

from paho.mqtt.client import MQTT_ERR_SUCCESS, Client, MQTTMessageInfo, MQTTMessage

from ha_services.exceptions import InvalidStateValue
from ha_services.mqtt4homeassistant.components import BaseComponent
from ha_services.mqtt4homeassistant.data_classes import NO_STATE, ComponentConfig, ComponentState, StatePayload
from ha_services.mqtt4homeassistant.device import MqttDevice


logger = logging.getLogger(__name__)


def switch_light_callback(*, client: Client, component: 'Light', old_state: str, new_state: str):
    logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')
    component.set_state_switch(new_state)
    component.publish_state_switch(client)

def brightness_light_callback(*, client: Client, component: 'Light', old_state: int, new_state: int):
    logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')
    component.set_state_brightness(new_state)
    component.publish_state_brightness(client)

def rgbw_light_callback(*, client: Client, component: 'Light', old_state: list[int], new_state: list[int]):
    logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')
    component.set_state_rgbw(new_state)
    component.publish_state_rgbw(client)



class Light(BaseComponent):
    """
    MQTT Select component for Home Assistant.
    https://www.home-assistant.io/integrations/light.mqtt/
    """

    ON = 'ON'
    OFF = 'OFF'

    MAX_BRIGHTNESS = 255

    def __init__(
        self,
        *,
        device: MqttDevice,
        name: str,
        uid: str,
        callback_switch: Callable = switch_light_callback,
        callback_brightness: Callable = brightness_light_callback,
        callback_rgbw: Callable = rgbw_light_callback,
        component: str = 'light',
        initial_state=NO_STATE,  # set_state() must be called to set the value
        default_brightness: int = MAX_BRIGHTNESS,
        default_rgbw: list[int] = [MAX_BRIGHTNESS,MAX_BRIGHTNESS,MAX_BRIGHTNESS, MAX_BRIGHTNESS],
        default_switch: str = ON,
        min_brightness: int = 0,
        max_brightness: int = MAX_BRIGHTNESS,
    ):
        super().__init__(
            device=device,
            name=name,
            uid=uid,
            component=component,
            initial_state=initial_state,
        )

        self.callback_switch = callback_switch
        self.callback_brightness = callback_brightness
        self.callback_rgbw = callback_rgbw

        self.state2bool = {
            self.ON: True,
            self.OFF: False,
        }

        # Set brightness limits before calling set_state methods
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness

        self.set_state_switch(default_switch)
        self.set_state_brightness(default_brightness)
        self.set_state_rgbw(default_rgbw)

        self.command_topic = f'{self.topic_prefix}/command'
        self.state_topic = f'{self.topic_prefix}/state'

        self.switch_command_topic = f'{self.command_topic}/switch'
        self.switch_state_topic = f'{self.state_topic}/switch'

        self.brightness_command_topic = f'{self.command_topic}/brightness'
        self.brightness_state_topic = f'{self.state_topic}/brightness'

        self.rgbw_command_topic = f'{self.command_topic}/rgbw'
        self.rgbw_state_topic = f'{self.state_topic}/rgbw'



    def set_state(self, state: str):
        raise NotImplementedError('Use set_state_switch, set_state_rgbw, or set_state_brightness instead.')

    def publish_state(self, client: Client) -> MQTTMessageInfo | None:
        raise NotImplementedError('Use publish_state_switch, publish_state_rgbw, or publish_state_brightness instead.')

    def get_state(self) -> ComponentState:
        raise NotImplementedError('Use get_state_switch, get_state_rgbw, or get_state_brightness instead.')



    def validate_state_switch(self, state: str):
        super().validate_state(state)
        if state not in self.state2bool:
            raise InvalidStateValue(component=self, error_msg=f'{state=} not in {", ".join(self.state2bool.keys())}')

    def validate_state_rgbw(self, state: list[int]):
        # Skip super().validate_state() since RGBW state is a list, not a StatePayload
        assert len(state) == 4 and all(isinstance(i, int) and i >= 0 and i <= 255 for i in state), f'Receive invalid rgbw state: {state}'

    def validate_state_brightness(self, state: int):
        super().validate_state(state)
        assert state >= self.min_brightness and state <= self.max_brightness, f'Receive invalid brightness state: {state}'



    def get_state_switch(self) -> ComponentState:
        # e.g.: {'topic': 'homeassistant/switch/My-device/My-Relay/state', 'payload': 'ON'}
        return ComponentState(
            topic=self.switch_state_topic,
            payload=self.state_switch,
        )

    def get_state_rgbw(self) -> ComponentState:
        return ComponentState(
            topic=self.rgbw_state_topic,
            payload=','.join(map(str, self.state_rgbw))
        )

    def get_state_brightness(self) -> ComponentState:
        return ComponentState(
            topic=self.brightness_state_topic,
            payload=str(self.state_brightness)
        )


    def set_state_switch(self, state: str):
        self.validate_state_switch(state)
        logger.debug('Set state %r for %r', state, self.uid)
        self.state_switch = state

    def set_state_rgbw(self, state: list[int]):
        self.validate_state_rgbw(state)
        logger.debug('Set state %r for %r', state, self.uid)
        self.state_rgbw = state

    def set_state_brightness(self, state: int):
        self.validate_state_brightness(state)
        logger.debug('Set state %r for %r', state, self.uid)
        self.state_brightness = state


    def _command_switch_callback(self, client: Client, userdata, message: MQTTMessage):
        new_state = message.payload.decode()
        assert new_state in self.state2bool, f'Receive invalid state: {new_state}'
        self.callback_switch(client=client, component=self, old_state=self.state_switch, new_state=new_state)

    def _command_brightness_callback(self, client: Client, userdata, message: MQTTMessage):
        new_state = int(message.payload.decode())
        self.validate_state_brightness(new_state)
        self.callback_brightness(client=client, component=self, old_state=self.state_brightness, new_state=new_state)

    def _command_rgbw_callback(self, client: Client, userdata, message: MQTTMessage):
        payload = message.payload.decode()
        new_state = [int(x.strip()) for x in payload.split(',')]
        self.validate_state_rgbw(new_state)
        self.callback_rgbw(client=client, component=self, old_state=self.state_rgbw, new_state=new_state)


    def publish_state_switch(self, client: Client) -> MQTTMessageInfo | None:
        if self.state_switch is NO_STATE:
            logging.warning(f'Light {self.uid=} switch state is not set!')
            return None

        if self._next_publish > time.monotonic():
            logger.debug(f'Publishing {self.uid=}: throttled')
            return None

        state: ComponentState = self.get_state_switch()
        logger.debug(f'Publishing {self.uid=} state: {state}')
        info: MQTTMessageInfo = client.publish(
            topic=state.topic,
            payload=state.payload,
            qos=self.qos,
            retain=self.retain,
        )

        self._next_publish = time.monotonic() + self.throttle_sec

        logger.debug(f'Next {self.uid=} config publish: {self._next_publish} {self.throttle_sec=}')

        return info


    def publish_state_rgbw(self, client: Client) -> MQTTMessageInfo | None:
        if self.state_rgbw is NO_STATE:
            logging.warning(f'Light {self.uid=} rgbw state is not set!')
            return None

        if self._next_publish > time.monotonic():
            logger.debug(f'Publishing {self.uid=}: throttled')
            return None

        state: ComponentState = self.get_state_rgbw()
        logger.debug(f'Publishing {self.uid=} state: {state}')
        info: MQTTMessageInfo = client.publish(
            topic=state.topic,
            payload=state.payload,
            qos=self.qos,
            retain=self.retain,
        )

        self._next_publish = time.monotonic() + self.throttle_sec

        logger.debug(f'Next {self.uid=} config publish: {self._next_publish} {self.throttle_sec=}')

        return info

    def publish_state_brightness(self, client: Client) -> MQTTMessageInfo | None:
        if self.state_brightness is NO_STATE:
            logging.warning(f'Light {self.uid=} brightness state is not set!')
            return None

        if self._next_publish > time.monotonic():
            logger.debug(f'Publishing {self.uid=}: throttled')
            return None

        state: ComponentState = self.get_state_brightness()
        logger.debug(f'Publishing {self.uid=} state: {state}')
        info: MQTTMessageInfo = client.publish(
            topic=state.topic,
            payload=state.payload,
            qos=self.qos,
            retain=self.retain,
        )

        self._next_publish = time.monotonic() + self.throttle_sec

        logger.debug(f'Next {self.uid=} config publish: {self._next_publish} {self.throttle_sec=}')

        return info

    def validate_state(self, state: StatePayload):
        """
        raise InvalidStateValue if state is not valid
        """
        if state is NO_STATE:
            raise InvalidStateValue(component=self, error_msg=f'Set {self.uid=} {state=} is not allowed')


    def publish_config(self, client: Client) -> MQTTMessageInfo | None:
        info = super().publish_config(client)

        client.message_callback_add(self.switch_command_topic, self._command_switch_callback)
        client.message_callback_add(self.brightness_command_topic, self._command_brightness_callback)
        client.message_callback_add(self.rgbw_command_topic, self._command_rgbw_callback)

        result, _ = client.subscribe(f'{self.command_topic}/#')
        if result is not MQTT_ERR_SUCCESS:
            logger.error(f'Error subscribing {self.command_topic=}: {result=}')

        return info

    def publish(self, client: Client) -> tuple[MQTTMessageInfo | None, MQTTMessageInfo | None, MQTTMessageInfo | None, MQTTMessageInfo | None]:
        config_info = self.publish_config(client)
        state_info_switch = self.publish_state_switch(client)
        state_info_rgbw = self.publish_state_rgbw(client)
        state_info_brightness = self.publish_state_brightness(client)
        return config_info, state_info_switch, state_info_rgbw, state_info_brightness

    def get_config(self) -> ComponentConfig:
        return ComponentConfig(
            topic=f'{self.topic_prefix}/config',
            payload={
                'component': self.component,
                'device': self.device.get_mqtt_payload(),
                'name': self.name,
                'unique_id': self.uid,
                'state_topic': self.switch_state_topic,
                'command_topic': self.switch_command_topic,
                'json_attributes_topic': f'{self.topic_prefix}/attributes',
                'platform': self.component,
                'brightness_state_topic': self.brightness_state_topic,
                'brightness_command_topic': self.brightness_command_topic,
                'rgbw_state_topic': self.rgbw_state_topic,
                'rgbw_command_topic': self.rgbw_command_topic,
                'payload_off': "OFF",
                'payload_on': "ON",
                'brightness': True,
                'supported_color_modes': ["rgbw"]
                # 'state_value_template': '{{ value_json.state }}',
                # 'brightness_value_template': '{{ value_json.brightness }}',
                # 'rgb_value_template': '{{ value_json.rgb | join(",") }}'
            },
        )
