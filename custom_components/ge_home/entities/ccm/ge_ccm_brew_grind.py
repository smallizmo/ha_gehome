from homeassistant.components.number import NumberMode
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import EntityCategory, STATE_UNAVAILABLE, STATE_UNKNOWN
from gehomesdk import ErdCode

from ...const import DOMAIN
from ...devices import ApplianceApi
from ..common import GeErdNumber
from .ge_ccm_cached_value import GeCcmCachedValue

DEFAULT_GRIND_DELTA = 0


class GeCcmBrewGrindTimeDeltaNumber(GeErdNumber, GeCcmCachedValue, RestoreEntity):
    """Grind time adjustment in seconds relative to the machine default (-2 to +3).

    Disabled when Gold strength is selected — Gold uses the SCAA preset
    with fixed brew parameters.  CCM_UNKNOWN900A is never pushed by the
    device so native_value always returns None and the cached value applies.
    """

    _attr_has_entity_name = True

    def __init__(self, api: ApplianceApi):
        GeErdNumber.__init__(
            self,
            api=api,
            erd_code=ErdCode.CCM_UNKNOWN900A,
            erd_override="Grind Time",
            min_value=-2,
            max_value=3,
            step_value=1,
            mode=NumberMode.BOX,
            uom_override="s",
            entity_category=EntityCategory.CONFIG,
        )
        GeCcmCachedValue.__init__(self)

    @property
    def unique_id(self) -> str:  # type: ignore[override]
        return f"{DOMAIN}_{self.serial_or_mac}_ccm_brew_grind_time_delta"

    @property
    def available(self) -> bool:  # type: ignore[override]
        if not super().available:
            return False
        from ...devices.coffee_maker import CcmApi
        if isinstance(self.api, CcmApi) and self.api.is_gold_strength:
            return False
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                GeCcmCachedValue.set_value(self, float(last_state.state))
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        GeCcmCachedValue.set_value(self, value)
        self.schedule_update_ha_state()

    @property
    def native_value(self) -> int:  # type: ignore[override]
        return int(self.get_value(device_value=super().native_value) or DEFAULT_GRIND_DELTA)
