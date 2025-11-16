import logging
from collections.abc import Callable

from paho.mqtt.client import MQTT_ERR_SUCCESS, Client, MQTTMessageInfo, MQTTMessage

from ha_services.exceptions import InvalidStateValue
from ha_services.mqtt4homeassistant.components import BaseComponent
from ha_services.mqtt4homeassistant.data_classes import NO_STATE, ComponentConfig, ComponentState, StatePayload
from ha_services.mqtt4homeassistant.device import MqttDevice


logger = logging.getLogger(__name__)


def default_text_callback(*, client: Client, component: BaseComponent, old_state: str, new_state: str):
    logger.info(f'{component.name} state changed: {old_state!r} -> {new_state!r}')
    component.set_state(new_state)
    component.publish_state(client)


class Text(BaseComponent):
    """
    MQTT Text component for Home Assistant.
    https://www.home-assistant.io/integrations/text.mqtt/
    """

    def __init__(
        self,
        *,
        device: MqttDevice,
        name: str,
        uid: str,
        callback: Callable = default_text_callback,
        component: str = 'text',
        initial_state=NO_STATE,
        min_length: int = 0,
        max_length: int = 255,
    ):
        super().__init__(
            device=device,
            name=name,
            uid=uid,
            component=component,
            initial_state=initial_state,
        )

        self.callback = callback
        self.min_length = min_length
        self.max_length = max_length

        # Only set a default state if no initial_state was provided
        if initial_state is NO_STATE:
            self.set_state("NO TEXT PROVIDED")

        self.command_topic = f'{self.topic_prefix}/command'

    def _command_callback(self, client: Client, userdata, message: MQTTMessage):
        new_state = message.payload.decode()

        # Validate the incoming command before processing
        try:
            self.validate_state(new_state)
        except InvalidStateValue as e:
            logger.error(f"Invalid text command received for {self.uid}: {e}")
            return

        self.callback(client=client, component=self, old_state=self.state, new_state=new_state)

    def publish_config(self, client: Client) -> MQTTMessageInfo | None:
        info = super().publish_config(client)

        client.message_callback_add(self.command_topic, self._command_callback)
        result, _ = client.subscribe(self.command_topic)
        if result is not MQTT_ERR_SUCCESS:
            logger.error(f'Error subscribing {self.command_topic=}: {result=}')

        return info

    def validate_state(self, state: StatePayload):
        super().validate_state(state)

        if not isinstance(state, str):
            raise InvalidStateValue(component=self, error_msg=f'Text state must be string, got {type(state).__name__}')

        if len(state) < self.min_length:
            raise InvalidStateValue(component=self, error_msg=f'Text length {len(state)} is less than minimum {self.min_length}')

        if len(state) > self.max_length:
            raise InvalidStateValue(component=self, error_msg=f'Text length {len(state)} exceeds maximum {self.max_length}')

    def get_state(self) -> ComponentState:
        # Ensure we have a valid state before returning it
        if self.state is NO_STATE:
            raise ValueError(f"Component {self.uid} state is not set")

        return ComponentState(
            topic=f'{self.topic_prefix}/state',
            payload=str(self.state),  # Explicitly cast to string to match StatePayload type
        )

    def get_config(self) -> ComponentConfig:
        config_payload = {
            'component': self.component,
            'device': self.device.get_mqtt_payload(),
            'name': self.name,
            'unique_id': self.uid,
            'state_topic': f'{self.topic_prefix}/state',
            'json_attributes_topic': f'{self.topic_prefix}/attributes',
            'command_topic': self.command_topic,
            'platform': self.component,
            'mode': 'text',
        }

        # Add length constraints if they differ from defaults
        if self.min_length > 0:
            config_payload['min'] = self.min_length
        if self.max_length < 255:
            config_payload['max'] = self.max_length

        return ComponentConfig(
            topic=f'{self.topic_prefix}/config',
            payload=config_payload,
        )
