import logging
from collections.abc import Callable

from paho.mqtt.client import MQTT_ERR_SUCCESS, Client, MQTTMessage  # removed MQTTMessageInfo

from ha_services.exceptions import InvalidStateValue
from ha_services.mqtt4homeassistant.components import BaseComponent
from ha_services.mqtt4homeassistant.data_classes import NO_STATE, ComponentConfig, ComponentState, StatePayload
from ha_services.mqtt4homeassistant.device import MqttDevice


logger = logging.getLogger(__name__)


def default_switch_callback(*, client: Client, component: BaseComponent, old_state: str, new_state: str):
    logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')
    component.set_state(new_state)
    component.publish_state(client)


class Switch(BaseComponent):
    """
    MQTT Switch component for Home Assistant.
    https://www.home-assistant.io/integrations/switch.mqtt/
    """

    ON = 'ON'
    OFF = 'OFF'

    def __init__(
        self,
        *,
        device: MqttDevice,
        name: str,
        uid: str,
        callback: Callable = default_switch_callback,
        component: str = 'switch',
        initial_state=NO_STATE,  # set_state() must be called to set the value
    ):
        super().__init__(
            device=device,
            name=name,
            uid=uid,
            component=component,
            initial_state=initial_state,
        )

        self.callback = callback

        self.state2bool = {
            self.ON: True,
            self.OFF: False,
        }
        self.command_topic = f'{self.topic_prefix}/command'
        # _callbacks_registered flag now handled by BaseComponent

    def _command_callback(self, client: Client, userdata, message: MQTTMessage):
        new_state = message.payload.decode()
        assert new_state in self.state2bool, f'Receive invalid state: {new_state}'
        self.callback(client=client, component=self, old_state=self.state, new_state=new_state)

    def _register_callbacks(self, client: Client):  # override BaseComponent hook
        client.message_callback_add(self.command_topic, self._command_callback)
        result, _ = client.subscribe(self.command_topic)
        if result is not MQTT_ERR_SUCCESS:
            logger.error(f'Error subscribing {self.command_topic=}: {result=}')
        else:
            logger.debug(f'Subscribed once to {self.command_topic}')

    def validate_state(self, state: StatePayload):  # type: ignore[override]
        super().validate_state(state)
        if state is NO_STATE:
            raise InvalidStateValue(component=self, error_msg='NO_STATE is not a valid published state')
        if state not in self.state2bool:
            raise InvalidStateValue(component=self, error_msg=f'{state=} not in {", ".join(self.state2bool.keys())}')

    def get_state(self) -> ComponentState:
        # e.g.: {'topic': 'homeassistant/switch/My-device/My-Relay/state', 'payload': 'ON'}
        assert self.state is not NO_STATE, 'State must be set before get_state() is called'
        from typing import cast
        state_payload = cast(StatePayload, self.state)
        return ComponentState(
            topic=f'{self.topic_prefix}/state',
            payload=state_payload,
        )

    def get_config(self) -> ComponentConfig:
        return ComponentConfig(
            topic=f'{self.topic_prefix}/config',
            payload={
                'component': self.component,
                'device': self.device.get_mqtt_payload(),
                'name': self.name,
                'unique_id': self.uid,
                'payload_off': self.OFF,
                'payload_on': self.ON,
                'state_topic': f'{self.topic_prefix}/state',
                'json_attributes_topic': f'{self.topic_prefix}/attributes',
                'command_topic': self.command_topic,
                'platform': self.component,
            },
        )
