import logging
from typing import List

from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity
from gehomesdk import (
    GeAppliance,
    ErdCode,
    ErdApplianceType,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .base import ApplianceApi
from ..entities import (
    GeCcmPotNotPresentBinarySensor,
    GeErdSensor,
    GeErdBinarySensor,
    GeErdButton,
    GeCcmBrewStrengthSelect,
    GeCcmBrewTemperatureNumber,
    GeCcmBrewCupsNumber,
    GeCcmBrewMugOzNumber,
    GeCcmBrewModeSelect,
    GeCcmBrewBloomTimeNumber,
    GeCcmBrewGrindTimeDeltaNumber,
    GeCcmBrewSettingsButton,
    GeCcmOutOfBeansBinarySensor,
    GeCcmGrindEnabledSwitch,
    GeCcmCleanBrewBasketBinarySensor,
)

_LOGGER = logging.getLogger(__name__)


class CcmApi(ApplianceApi):
    """API class for Cafe Coffee Maker objects"""
    APPLIANCE_TYPE = ErdApplianceType.CAFE_COFFEE_MAKER

    def __init__(self, coordinator: DataUpdateCoordinator, appliance: GeAppliance):
        super().__init__(coordinator, appliance)

        self._brew_strengh_entity = GeCcmBrewStrengthSelect(self)
        self._brew_temperature_entity = GeCcmBrewTemperatureNumber(self)
        self._brew_mode_entity = GeCcmBrewModeSelect(self)
        self._brew_carafe_cups_entity = GeCcmBrewCupsNumber(self)
        self._brew_mug_oz_entity = GeCcmBrewMugOzNumber(self)
        self._brew_bloom_entity = GeCcmBrewBloomTimeNumber(self)
        self._brew_grind_entity = GeCcmBrewGrindTimeDeltaNumber(self)
        self._grind_enabled_entity = GeCcmGrindEnabledSwitch(self)
        self._out_of_beans_entity = GeCcmOutOfBeansBinarySensor(self)
        self._clean_brew_basket_entity = GeCcmCleanBrewBasketBinarySensor(self)
        self._dt_device_id: str | None = None  # cached Digital Twin SHA-256 device ID
        self._dt_out_of_beans: bool = False    # cached from DT API polling
        self._dt_clean_brew_basket: bool = False  # cached from DT API polling
        self._dt_state_refresh_unsub = None    # cancellation token for polling timer

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        ccm_entities = [
            GeErdBinarySensor(self, ErdCode.CCM_IS_BREWING, erd_override="Brewing", entity_category=EntityCategory.DIAGNOSTIC),
            GeErdBinarySensor(self, ErdCode.CCM_IS_DESCALING, erd_override="Descaling", entity_category=EntityCategory.DIAGNOSTIC),
            GeCcmBrewSettingsButton(self),
            GeErdButton(self, ErdCode.CCM_CANCEL_DESCALING, erd_override="Cancel Descaling", entity_category=EntityCategory.CONFIG),
            GeErdButton(self, ErdCode.CCM_START_DESCALING, erd_override="Start Descaling", entity_category=EntityCategory.CONFIG),
            GeErdButton(self, ErdCode.CCM_CANCEL_BREWING, erd_override="Cancel Brew"),
            self._brew_strengh_entity,
            self._brew_temperature_entity,
            self._brew_mode_entity,
            self._brew_carafe_cups_entity,
            self._brew_mug_oz_entity,
            self._brew_bloom_entity,
            self._brew_grind_entity,
            GeErdSensor(self, ErdCode.CCM_CURRENT_WATER_TEMPERATURE, erd_override="Water Temp", entity_category=EntityCategory.DIAGNOSTIC),
            GeErdBinarySensor(self, ErdCode.CCM_OUT_OF_WATER, erd_override="Out of Water", device_class_override="problem", entity_category=EntityCategory.DIAGNOSTIC),
            GeCcmPotNotPresentBinarySensor(self, ErdCode.CCM_POT_PRESENT, erd_override="Carafe Missing", device_class_override="problem", entity_category=EntityCategory.DIAGNOSTIC),
            self._out_of_beans_entity,
            self._clean_brew_basket_entity,
            self._grind_enabled_entity,
        ]

        # All CCM entities use has_entity_name so HA prepends the device name
        # automatically — no serial/MAC prefix in the entity name itself.
        for entity in ccm_entities:
            entity._attr_has_entity_name = True

        entities = base_entities + ccm_entities
        return entities

    def build_entities_list(self) -> None:
        """Build entity list, always including brew settings controls."""
        super().build_entities_list()
        for entity in [
            self._brew_strengh_entity,
            self._brew_temperature_entity,
            self._brew_mode_entity,
            self._brew_carafe_cups_entity,
            self._brew_mug_oz_entity,
            self._brew_bloom_entity,
            self._brew_grind_entity,
            self._grind_enabled_entity,
            self._out_of_beans_entity,
            self._clean_brew_basket_entity,
        ]:
            if entity.unique_id is not None and entity.unique_id not in self._entities:
                self._entities[entity.unique_id] = entity

    @property
    def is_gold_strength(self) -> bool:
        """Return True when the SCAA Gold Cup preset is selected.

        Gold uses fixed brew parameters — bloom and grind adjustment are
        not applicable and should be disabled in the UI.
        """
        from gehomesdk import ErdCcmBrewStrength
        return self._brew_strengh_entity.brew_strength == ErdCcmBrewStrength.GOLD

    def schedule_brew_param_update(self) -> None:
        """Push a state refresh to entities whose availability depends on strength.

        Called by GeCcmBrewStrengthSelect when the user changes strength so that
        bloom / grind entities grey out or activate immediately.
        """
        for entity in [self._brew_bloom_entity, self._brew_grind_entity]:
            if entity.added:
                entity.schedule_update_ha_state()

    @property
    def grind_enabled(self) -> bool:
        """Return True when the built-in grinder should be used for the next brew."""
        return self._grind_enabled_entity.is_on

    async def async_refresh_dt_state(self) -> None:
        """Poll the SmartHQ Digital Twin API and update cached state values.

        Currently updates: outOfBeans.
        Called on a 2-minute timer started by GeCcmOutOfBeansBinarySensor once
        it is added to HA, and also immediately on entity add for a fast first read.
        """
        import aiohttp

        token = self.appliance.client._access_token
        if not token:
            return

        dt_base = "https://client.mysmarthq.com"
        try:
            async with aiohttp.ClientSession() as session:
                if not self._dt_device_id:
                    self._dt_device_id = await self._get_dt_device_id(session, token, dt_base)
                device_id = self._dt_device_id
                if not device_id:
                    return

                async with session.get(
                    f"{dt_base}/v2/device/{device_id}",
                    headers={"Authorization": f"Bearer {token}"},
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("async_refresh_dt_state: GET /v2/device returned %s", resp.status)
                        return
                    data = await resp.json()
        except Exception as exc:
            _LOGGER.error("async_refresh_dt_state: request failed: %s", exc)
            return

        for svc in data.get("services", []):
            if svc.get("serviceType") == "cloud.smarthq.service.coffeebrewer.v2":
                state = svc.get("state", {})

                new_out_of_beans: bool = bool(state.get("outOfBeans", False))
                if new_out_of_beans != self._dt_out_of_beans:
                    self._dt_out_of_beans = new_out_of_beans
                    _LOGGER.debug("async_refresh_dt_state: outOfBeans=%s", new_out_of_beans)
                    if self._out_of_beans_entity.added:
                        self._out_of_beans_entity.schedule_update_ha_state()

                new_clean_brew_basket: bool = bool(state.get("cleanBrewBasket", False))
                if new_clean_brew_basket != self._dt_clean_brew_basket:
                    self._dt_clean_brew_basket = new_clean_brew_basket
                    _LOGGER.debug("async_refresh_dt_state: cleanBrewBasket=%s", new_clean_brew_basket)
                    if self._clean_brew_basket_entity.added:
                        self._clean_brew_basket_entity.schedule_update_ha_state()
                break

    async def _async_dt_state_refresh_callback(self, _now=None) -> None:
        """Timer callback wrapper for async_refresh_dt_state."""
        await self.async_refresh_dt_state()

    # SmartHQ Digital Twin API strength encoding is 0-indexed, whereas the
    # ERD protocol is 1-indexed.  Map ErdCcmBrewStrength → DT API integer.
    # ERD:    LIGHT=1  MEDIUM=2  BOLD=3  GOLD=4
    # DT API: LIGHT=0  MEDIUM=1  BOLD=2  GOLD=3
    _DT_STRENGTH = {
        "LIGHT": 0,
        "MEDIUM": 1,
        "BOLD": 2,
        "GOLD": 3,
    }

    async def start_brewing(self) -> None:
        """Trigger a brew via the SmartHQ Digital Twin API.

        Uses POST https://client.mysmarthq.com/v2/command with
        commandType cloud.smarthq.command.coffeebrewer.v2.start.
        The old api.brillion.geappliances.com /control endpoint only returns
        "invalid command specified" for this appliance generation.
        """
        import aiohttp

        mode = self._brew_mode_entity.brew_mode  # "carafe" or "mug"
        strength = self._brew_strengh_entity.brew_strength
        temperature = self._brew_temperature_entity.native_value
        dt_strength = self._DT_STRENGTH.get(strength.name, strength.value - 1)
        bloom_time = self._brew_bloom_entity.native_value if not self.is_gold_strength else None
        grind_delta = self._brew_grind_entity.native_value if not self.is_gold_strength else None

        if mode == "carafe":
            volume_value = self._brew_carafe_cups_entity.native_value
            volume_field = "volumeCarafe"
            volume_units = "cloud.smarthq.type.volumeunits.cups"
        else:  # mug
            volume_value = self._brew_mug_oz_entity.native_value
            volume_field = "volumeSingle"
            volume_units = "cloud.smarthq.type.volumeunits.fluidounces"

        _LOGGER.debug(
            "start_brewing: mode=%s volume=%s %s strength=%s (ERD=%s DT=%s) temp=%s bloom=%s grind_delta=%s",
            mode, volume_value, volume_field, strength.name, strength.value, dt_strength, temperature,
            bloom_time, grind_delta,
        )

        token = self.appliance.client._access_token
        if not token:
            _LOGGER.error("start_brewing: no access token available")
            return

        dt_base = "https://client.mysmarthq.com"

        async with aiohttp.ClientSession() as session:
            # Step 1: resolve SHA-256 deviceId from the Digital Twin device list.
            # The DT API uses a hash ID, not the Brillion MAC address.
            # Result is cached after the first successful lookup.
            if not self._dt_device_id:
                self._dt_device_id = await self._get_dt_device_id(session, token, dt_base)
            device_id = self._dt_device_id
            if not device_id:
                _LOGGER.error("start_brewing: could not resolve Digital Twin device ID")
                return

            # Step 2: send the brew command.
            command: dict = {
                "commandType": "cloud.smarthq.command.coffeebrewer.v2.start",
                "temperatureFahrenheit": float(temperature),
                "strength": dt_strength,
                "volumeUnits": volume_units,
            }
            command[volume_field] = float(volume_value)
            if not self.is_gold_strength:
                if bloom_time:
                    command["bloomDwellTimeSeconds"] = bloom_time
                if grind_delta:
                    command["grindTimeDelta"] = grind_delta
            if not self.grind_enabled:
                # Skip the built-in grinder (pre-ground coffee in basket).
                # Field name 'useGrinder' follows SmartHQ camelCase convention;
                # verify against actual API response if machine ignores this.
                command["useGrinder"] = False
            payload = {
                "kind": "service#command",
                "deviceId": device_id,
                "serviceType": "cloud.smarthq.service.coffeebrewer.v2",
                "domainType": "cloud.smarthq.domain.coffeebrewer",
                "serviceDeviceType": "cloud.smarthq.device.coffeebrewer",
                "command": command,
            }
            _LOGGER.debug("start_brewing: POST /v2/command %s", payload)

            async with session.post(
                f"{dt_base}/v2/command",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                body = await resp.json()
                if resp.status == 200 and body.get("success"):
                    _LOGGER.info(
                        "start_brewing: brew started (correlationId=%s)",
                        body.get("correlationId"),
                    )
                else:
                    _LOGGER.error(
                        "start_brewing: command failed HTTP %s: %s",
                        resp.status, body,
                    )

    async def _get_dt_device_id(
        self, session: "aiohttp.ClientSession", token: str, dt_base: str
    ) -> str | None:
        """Return the SmartHQ Digital Twin SHA-256 deviceId for this appliance.

        Matches on deviceType coffeebrewer and the appliance MAC address.
        The DT API device list does not always expose macAddress, so the first
        coffeebrewer device is used as a fallback when MAC is absent.
        """
        mac = self.appliance.mac_addr.upper()
        try:
            async with session.get(
                f"{dt_base}/v2/device",
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("_get_dt_device_id: GET /v2/device returned %s", resp.status)
                    return None
                data = await resp.json()
        except Exception as exc:
            _LOGGER.error("_get_dt_device_id: request failed: %s", exc)
            return None

        first_brewer: str | None = None
        for dev in data.get("devices", []):
            if dev.get("deviceType") != "cloud.smarthq.device.coffeebrewer":
                continue
            # Prefer exact MAC match.
            if dev.get("macAddress", "").upper() == mac:
                return dev["deviceId"]
            if first_brewer is None:
                first_brewer = dev["deviceId"]

        if first_brewer:
            _LOGGER.debug(
                "_get_dt_device_id: no MAC match, falling back to first brewer %s",
                first_brewer,
            )
        return first_brewer