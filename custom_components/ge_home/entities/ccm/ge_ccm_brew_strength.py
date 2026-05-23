import logging
from typing import List, Any, Optional

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import EntityCategory, STATE_UNAVAILABLE, STATE_UNKNOWN
from gehomesdk import ErdCode, ErdCcmBrewStrength
from ...devices import ApplianceApi
from ..common import GeErdSelect, OptionsConverter
from .ge_ccm_cached_value import GeCcmCachedValue

_LOGGER = logging.getLogger(__name__)

DEFAULT_BREW_STRENGTH = ErdCcmBrewStrength.GOLD

class GeCcmBrewStrengthOptionsConverter(OptionsConverter):
    def __init__(self):
        self._default = DEFAULT_BREW_STRENGTH

    @property
    def options(self) -> List[str]:
        return [i.stringify() for i in [ErdCcmBrewStrength.LIGHT, ErdCcmBrewStrength.MEDIUM, ErdCcmBrewStrength.BOLD, ErdCcmBrewStrength.GOLD]]

    def from_option_string(self, value: str) -> Any:
        try:
            return ErdCcmBrewStrength[value.upper()]
        except:
            _LOGGER.warning(f"Could not set brew strength to {value.upper()}")
            return self._default

    def to_option_string(self, value: ErdCcmBrewStrength) -> Optional[str]:
        try:
            return value.stringify()
        except:
            return self._default.stringify()

class GeCcmBrewStrengthSelect(GeErdSelect, GeCcmCachedValue, RestoreEntity):
    _attr_has_entity_name = True
    def __init__(self, api: ApplianceApi):
        GeErdSelect.__init__(self, api=api, erd_code=ErdCode.CCM_BREW_STRENGTH, erd_override="Brew Strength", converter=GeCcmBrewStrengthOptionsConverter(), entity_category=EntityCategory.CONFIG)
        GeCcmCachedValue.__init__(self)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if last_state.state in self.options:
                GeCcmCachedValue.set_value(self, last_state.state)

    @property
    def brew_strength(self) -> ErdCcmBrewStrength:
        return self._converter.from_option_string(self.current_option)

    async def async_select_option(self, option):
        GeCcmCachedValue.set_value(self, option)
        self.schedule_update_ha_state()
        # Immediately grey out / restore bloom and grind entities when
        # switching to or from Gold (which disables those parameters).
        from ...devices.coffee_maker import CcmApi
        if isinstance(self.api, CcmApi):
            self.api.schedule_brew_param_update()

    @property
    def current_option(self) -> str | None: # type: ignore
        return self.get_value(device_value=super().current_option) or DEFAULT_BREW_STRENGTH.stringify()