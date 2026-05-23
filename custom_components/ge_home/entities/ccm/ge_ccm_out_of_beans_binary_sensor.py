import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.event import async_track_time_interval

from ...const import DOMAIN
from ...devices import ApplianceApi
from ..common import GeEntity

_LOGGER = logging.getLogger(__name__)

_POLL_INTERVAL = timedelta(seconds=120)


class GeCcmOutOfBeansBinarySensor(GeEntity, BinarySensorEntity):
    """Binary sensor for out-of-beans status, sourced from SmartHQ Digital Twin polling.

    There is no ERD code for this field — it is only available via the
    GET /v2/device/{deviceId} REST endpoint.  This entity schedules a
    periodic poll (every 2 minutes) and refreshes its state whenever the
    CcmApi receives updated DT state.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, api: ApplianceApi) -> None:
        GeEntity.__init__(self, api)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:  # type: ignore[override]
        return f"{DOMAIN}_{self.serial_or_mac}_ccm_out_of_beans"

    @property
    def name(self) -> str:  # type: ignore[override]
        return "Out of Beans"

    @property
    def is_on(self) -> bool:
        from ...devices.coffee_maker import CcmApi
        if isinstance(self.api, CcmApi):
            return self.api._dt_out_of_beans
        return False

    async def async_added_to_hass(self) -> None:
        await GeEntity.async_added_to_hass(self)
        from ...devices.coffee_maker import CcmApi
        if not isinstance(self.api, CcmApi):
            return
        api: CcmApi = self.api
        # Start polling timer once per CcmApi instance.
        if api._dt_state_refresh_unsub is None:
            api._dt_state_refresh_unsub = async_track_time_interval(
                self.hass,
                api._async_dt_state_refresh_callback,
                _POLL_INTERVAL,
            )
        # Kick off an immediate refresh so the entity has a real value quickly.
        self.hass.async_create_task(api.async_refresh_dt_state())

    async def async_will_remove_from_hass(self) -> None:
        await GeEntity.async_will_remove_from_hass(self)
        from ...devices.coffee_maker import CcmApi
        if not isinstance(self.api, CcmApi):
            return
        api: CcmApi = self.api
        if api._dt_state_refresh_unsub is not None:
            api._dt_state_refresh_unsub()
            api._dt_state_refresh_unsub = None
