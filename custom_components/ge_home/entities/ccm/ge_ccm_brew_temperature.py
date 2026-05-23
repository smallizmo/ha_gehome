from homeassistant.components.number import NumberMode
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import EntityCategory, STATE_UNAVAILABLE, STATE_UNKNOWN
from gehomesdk import ErdCode

from ...devices import ApplianceApi
from ..common import GeErdNumber
from .ge_ccm_cached_value import GeCcmCachedValue

DEFAULT_MIN_TEMP = 185
DEFAULT_MAX_TEMP = 205
DEFAULT_BREW_TEMP = 200

class GeCcmBrewTemperatureNumber(GeErdNumber, GeCcmCachedValue, RestoreEntity):
    _attr_has_entity_name = True
    def __init__(self, api: ApplianceApi):
        try:
            min_temp, max_temp, _ = api.appliance.get_erd_value(ErdCode.CCM_BREW_TEMPERATURE_RANGE)
        except:
            min_temp = DEFAULT_MIN_TEMP
            max_temp = DEFAULT_MAX_TEMP

        GeErdNumber.__init__(self, api=api, erd_code=ErdCode.CCM_BREW_TEMPERATURE, erd_override="Brew Temp", min_value=min_temp, max_value=max_temp, mode=NumberMode.SLIDER, entity_category=EntityCategory.CONFIG)
        GeCcmCachedValue.__init__(self)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                GeCcmCachedValue.set_value(self, float(last_state.state))
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value):
        GeCcmCachedValue.set_value(self, value)
        self.schedule_update_ha_state()

    @property
    def native_value(self) -> int: # type: ignore
        return int(self.get_value(device_value=super().native_value) or DEFAULT_BREW_TEMP)
