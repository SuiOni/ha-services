from ha_services.ha_data.data_sensors import HA_SENSOR_DATA


HA_SENSOR_MAP = {sensor['device_class']: sensor for sensor in HA_SENSOR_DATA}


class ValidationError(ValueError):
    pass


def validate_sensor(*, device_class: str | None, state_class: str | None, unit_of_measurement: str | None) -> None:
    """
    Validate if the given device_class, state_class and unit_of_measurement are valid according to HA_SENSOR_DATA.
    """

    if device_class is None:
        return

    try:
        ha_data = HA_SENSOR_MAP[device_class]
    except KeyError as err:
        raise ValidationError(
            f'Invalid: {device_class=} ! Valid options: {",".join(sorted(HA_SENSOR_MAP.keys()))}'
        ) from err

    if state_class is not None and state_class not in ha_data['state_classes']:
        raise ValidationError(f'Invalid: {state_class=} for {device_class=}. Valid options: {ha_data["state_classes"]}')

    if unit_of_measurement is not None and unit_of_measurement not in ha_data['units']:
        raise ValidationError(f'Invalid: {unit_of_measurement=} for {device_class=}. Valid options: {ha_data["units"]}')
