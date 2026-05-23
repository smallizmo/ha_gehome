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


class GeCcmCleanBrewBasketBinarySensor(GeEntity, BinarySensorEntity):
    """Binary sensor for the 'Empty brew basket' reminder.

    The SmartHQ Digital Twin state field cleanBrewBasket is set to True
    after a brew cycle completes to prompt the user to empty and clean
    the brew basket.  There is no ERD code for this field — it is polled
    from GET /v2/device/{deviceId} on the same 2-minute timer used by
    the Out of Beans sensor.
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, api: ApplianceApi) -> None:
        GeEntity.__init__(self, api)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:  # type: ignore[override]
        return f"{DOMAIN}_{self.serial_or_mac}_ccm_clean_brew_basket"

    @property
    def name(self) -> str:  # type: ignore[override]
        return "Empty Brew Basket"

    @property
    def is_on(self) -> bool:
        from ...devices.coffee_maker import CcmApi
        if isinstance(self.api, CcmApi):
            return self.api._dt_clean_brew_basket
        return False

    async def async_added_to_hass(self) -> None:
        await GeEntity.async_added_to_hass(self)
        from ...devices.coffee_maker import CcmApi
        if not isinstance(self.api, CcmApi):
            return
        api: CcmApi = self.api
        # Reuse the shared polling timer started by GeCcmOutOfBeansBinarySensor.
        # If it hasn't been started yet, start it now.
        if api._dt_state_refresh_unsub is None:
            api._dt_state_refresh_unsub = async_track_time_interval(
                self.hass,
                api._async_dt_state_refresh_callback,
                _POLL_INTERVAL,
            )
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
