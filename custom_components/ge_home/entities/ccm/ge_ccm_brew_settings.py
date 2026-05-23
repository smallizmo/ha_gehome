import logging
import traceback
from gehomesdk import ErdCode
from ...devices import ApplianceApi
from ..common import GeErdButton

_LOGGER = logging.getLogger(__name__)

class GeCcmBrewSettingsButton(GeErdButton):
    _attr_has_entity_name = True
    def __init__(self, api: ApplianceApi):
        super().__init__(api, erd_code=ErdCode.CCM_BREW_SETTINGS, erd_override="Start Brew")

    async def async_press(self) -> None:
        """Handle the button press."""

        from ...devices import CcmApi

        if isinstance(self.api, CcmApi):
            try:
                await self.api.start_brewing()
            except Exception:
                _LOGGER.error("start_brewing failed:\n%s", traceback.format_exc())
                raise