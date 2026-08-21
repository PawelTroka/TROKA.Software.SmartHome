"""Support for D-Link HNAP motion and water sensors."""

from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "D-Link Motion Sensor"
DEFAULT_USERNAME = "Admin"
DEFAULT_TIMEOUT = 35

SCAN_INTERVAL = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_TYPE): vol.In(["motion", "water"]),
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up a D-Link HNAP binary sensor."""
    from .dlink import (  # noqa: PLC0415
        ACTION_BASE_URL,
        HNAPClient,
        MotionSensor,
        NanoSOAPClient,
        WaterSensor,
    )

    soap = NanoSOAPClient(
        config[CONF_HOST],
        ACTION_BASE_URL,
        loop=hass.loop,
        session=async_get_clientsession(hass),
    )
    client = HNAPClient(
        soap,
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        loop=hass.loop,
    )

    if config[CONF_TYPE] == "motion":
        entity = DlinkMotionSensor(
            config[CONF_NAME], config[CONF_TIMEOUT], MotionSensor(client)
        )
    else:
        entity = DlinkWaterSensor(config[CONF_NAME], WaterSensor(client))

    async_add_entities([entity], update_before_add=True)


class DlinkBinarySensor(BinarySensorEntity):
    """Representation of a D-Link HNAP binary sensor."""

    _attr_should_poll = True

    def __init__(self, name, sensor, device_class):
        """Initialize a D-Link HNAP binary sensor."""
        self._attr_name = name
        self._attr_device_class = device_class
        self._sensor = sensor
        self._on = False
        self._available = False
        self._unavailable_logged = False

    @property
    def is_on(self):
        """Return whether the sensor is active."""
        return self._on

    @property
    def available(self):
        """Return whether the latest device poll succeeded."""
        return self._available

    def _mark_available(self):
        """Mark the sensor available after a successful poll."""
        if not self._available and self._unavailable_logged:
            _LOGGER.info("%s is available again", self._attr_name)
        self._available = True
        self._unavailable_logged = False

    def _mark_unavailable(self, error):
        """Mark the sensor unavailable and log once per outage."""
        self._available = False
        if not self._unavailable_logged:
            _LOGGER.error("%s is unavailable: %s", self._attr_name, error)
            self._unavailable_logged = True


class DlinkMotionSensor(DlinkBinarySensor):
    """Representation of a D-Link HNAP motion sensor."""

    def __init__(self, name, timeout, sensor):
        """Initialize a D-Link HNAP motion sensor."""
        super().__init__(name, sensor, BinarySensorDeviceClass.MOTION)
        self._timeout = timeout

    async def async_update(self):
        """Fetch the latest motion state."""
        try:
            last_trigger = await self._sensor.latest_trigger()
        except Exception as error:  # The device library has no typed errors.
            self._mark_unavailable(error)
            return

        self._mark_available()
        if last_trigger is None:
            self._on = False
            return

        self._on = datetime.now() <= last_trigger + timedelta(seconds=self._timeout)


class DlinkWaterSensor(DlinkBinarySensor):
    """Representation of a D-Link HNAP water sensor."""

    def __init__(self, name, sensor):
        """Initialize a D-Link HNAP water sensor."""
        super().__init__(name, sensor, BinarySensorDeviceClass.MOISTURE)

    async def async_update(self):
        """Fetch the latest water state."""
        try:
            self._on = await self._sensor.water_detected()
        except Exception as error:  # The device library has no typed errors.
            self._mark_unavailable(error)
            return

        self._mark_available()
