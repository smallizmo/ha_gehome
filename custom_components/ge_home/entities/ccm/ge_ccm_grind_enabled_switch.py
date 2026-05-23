import logging

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN

from ...const import DOMAIN
from ...devices import ApplianceApi
from ..common import GeEntity

_LOGGER = logging.getLogger(__name__)


class GeCcmGrindEnabledSwitch(GeEntity, SwitchEntity, RestoreEntity):
    """Switch to enable or disable the built-in grinder for the next brew.

    When switched off, the brew command is sent with useGrinder=False so the
    machine skips grinding and brews directly from pre-ground coffee loaded
    into the brew basket.

    NOTE: 'useGrinder' is the inferred SmartHQ DT API field name based on the
    camelCase convention used by other coffeebrewer.v2 command parameters
    (grindTimeDelta, bloomDwellTimeSeconds, etc.).  If the machine ignores the
    parameter, test with 'grindEnabled' or 'skipGrinder' instead.
    """

    _attr_has_entity_name = True

    def __init__(self, api: ApplianceApi) -> None:
        GeEntity.__init__(self, api)
        self._attr_entity_category = EntityCategory.CONFIG
        self._is_on: bool = True  # grinder on by default

    @property
    def unique_id(self) -> str:  # type: ignore[override]
        return f"{DOMAIN}_{self.serial_or_mac}_ccm_grind_enabled"

    @property
    def name(self) -> str:  # type: ignore[override]
        return "Use Grinder"

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        await GeEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._is_on = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs) -> None:  # type: ignore[override]
        self._is_on = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:  # type: ignore[override]
        self._is_on = False
        self.schedule_update_ha_state()
