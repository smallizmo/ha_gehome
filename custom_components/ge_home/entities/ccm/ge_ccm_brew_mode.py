import logging
from typing import List, Optional

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory, STATE_UNAVAILABLE, STATE_UNKNOWN
from propcache.api import cached_property

from ...const import DOMAIN
from ...devices import ApplianceApi
from ..common.ge_entity import GeEntity
from .ge_ccm_cached_value import GeCcmCachedValue

_LOGGER = logging.getLogger(__name__)

BREW_MODE_CARAFE = "Carafe"
BREW_MODE_MUG = "Mug"
DEFAULT_BREW_MODE = BREW_MODE_CARAFE


class GeCcmBrewModeSelect(GeEntity, SelectEntity, GeCcmCachedValue, RestoreEntity):
    """Select entity for coffee maker brew mode (Carafe or Mug)."""

    _attr_has_entity_name = True

    def __init__(self, api: ApplianceApi):
        GeEntity.__init__(self, api)
        GeCcmCachedValue.__init__(self)
        self._attr_entity_category = EntityCategory.CONFIG

    @cached_property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.serial_or_mac}_ccm_brew_mode"

    @cached_property
    def name(self) -> str:
        return "Brew Mode"

    @cached_property
    def options(self) -> List[str]:
        return [BREW_MODE_CARAFE, BREW_MODE_MUG]

    @property
    def current_option(self) -> str:
        return self.get_value(device_value=None) or DEFAULT_BREW_MODE

    @property
    def brew_mode(self) -> str:
        """Return the current brew mode as lowercase ('carafe' or 'mug')."""
        return self.current_option.lower()

    async def async_added_to_hass(self) -> None:
        await GeEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if last_state.state in self.options:
                GeCcmCachedValue.set_value(self, last_state.state)

    async def async_select_option(self, option: str) -> None:
        """Handle the mode selection."""
        GeCcmCachedValue.set_value(self, option)
        self.schedule_update_ha_state()

    def _get_icon(self) -> Optional[str]:
        return "mdi:coffee-maker"
