from homeassistant.components.number import NumberMode
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import EntityCategory, STATE_UNAVAILABLE, STATE_UNKNOWN
from gehomesdk import ErdCode

from ...const import DOMAIN
from ...devices import ApplianceApi
from ..common import GeErdNumber
from .ge_ccm_cached_value import GeCcmCachedValue

DEFAULT_MUG_OZ = 10


class GeCcmBrewMugOzNumber(GeErdNumber, GeCcmCachedValue, RestoreEntity):
    """Number entity for mug brew volume in fluid ounces."""

    _attr_has_entity_name = True

    def __init__(self, api: ApplianceApi):
        GeErdNumber.__init__(
            self,
            api=api,
            # CCM_UNKNOWN9007 is never pushed by the device, so native_value
            # always returns None and the cached value takes effect.
            erd_code=ErdCode.CCM_UNKNOWN9007,
            erd_override="Mug Size",
            min_value=6,
            max_value=24,
            step_value=2,
            mode=NumberMode.BOX,
            uom_override="oz",
            entity_category=EntityCategory.CONFIG,
        )
        GeCcmCachedValue.__init__(self)

    @property
    def unique_id(self) -> str:  # type: ignore[override]
        return f"{DOMAIN}_{self.serial_or_mac}_ccm_brew_mug_oz"

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
        return int(self.get_value(device_value=super().native_value) or DEFAULT_MUG_OZ)
