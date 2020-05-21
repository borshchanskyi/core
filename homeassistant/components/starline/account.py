"""StarLine Account."""
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from starline import StarlineApi, StarlineDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SCAN_OBD_INTERVAL,
    DATA_EXPIRES,
    DATA_SLID_TOKEN,
    DATA_SLNET_TOKEN,
    DATA_USER_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_OBD_INTERVAL,
    DOMAIN,
    LOGGER,
)


class StarlineAccount:
    """StarLine Account class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize StarLine account."""
        self._hass: HomeAssistant = hass
        self._config_entry: ConfigEntry = config_entry
        self._update_intervals: Dict[str, int] = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_SCAN_OBD_INTERVAL: DEFAULT_SCAN_OBD_INTERVAL,
        }
        self._unsubscribe_auto_updater: Dict[str, Optional[Callable]] = {
            CONF_SCAN_INTERVAL: None,
            CONF_SCAN_OBD_INTERVAL: None,
        }
        self._api: StarlineApi = StarlineApi(
            config_entry.data[DATA_USER_ID], config_entry.data[DATA_SLNET_TOKEN]
        )

    def _check_slnet_token(self) -> None:
        """Check SLNet token expiration and update if needed."""
        now = datetime.now().timestamp()
        slnet_token_expires = self._config_entry.data[DATA_EXPIRES]

        if now + self._update_intervals.get(CONF_SCAN_INTERVAL) > slnet_token_expires:
            self._update_slnet_token()

    def _update_slnet_token(self) -> None:
        """Update SLNet token."""
        slid_token = self._config_entry.data[DATA_SLID_TOKEN]

        try:
            slnet_token, slnet_token_expires, user_id = self._api.get_user_id(
                slid_token
            )
            self._api.set_slnet_token(slnet_token)
            self._api.set_user_id(user_id)
            self._hass.config_entries.async_update_entry(
                self._config_entry,
                data={
                    **self._config_entry.data,
                    DATA_SLNET_TOKEN: slnet_token,
                    DATA_EXPIRES: slnet_token_expires,
                    DATA_USER_ID: user_id,
                },
            )
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Error updating SLNet token: %s", err)

    def _update_data(self):
        """Update StarLine data."""
        self._check_slnet_token()
        self._api.update()

    def _update_obd_data(self):
        """Update StarLine OBD data."""
        self._check_slnet_token()
        self._api.update_obd()

    @property
    def api(self) -> StarlineApi:
        """Return the instance of the API."""
        return self._api

    async def update(self, unused=None):
        """Update StarLine data."""
        await self._hass.async_add_executor_job(self._update_data)

    async def update_obd(self, unused=None):
        """Update StarLine OBD data."""
        await self._hass.async_add_executor_job(self._update_obd_data)

    def set_update_interval(self, key: str, interval: int) -> None:
        """Set StarLine API update interval."""
        LOGGER.debug("Setting update interval: %ds", interval)
        if self._unsubscribe_auto_updater[key] is not None:
            self._unsubscribe_auto_updater[key]()
        method = self.update if key == CONF_SCAN_INTERVAL else self.update_obd
        delta = timedelta(seconds=interval)
        self._unsubscribe_auto_updater[key] = async_track_time_interval(
            self._hass, method, delta
        )

    def unload(self):
        """Unload StarLine API."""
        LOGGER.debug("Unloading StarLine API.")
        for key in self._unsubscribe_auto_updater:
            if self._unsubscribe_auto_updater[key] is not None:
                LOGGER.debug("Unload: %s", key)
                self._unsubscribe_auto_updater[key]()
                self._unsubscribe_auto_updater[key] = None

    @staticmethod
    def device_info(device: StarlineDevice) -> Dict[str, Any]:
        """Device information for entities."""
        return {
            "identifiers": {(DOMAIN, device.device_id)},
            "manufacturer": "StarLine",
            "name": device.name,
            "sw_version": device.fw_version,
            "model": device.typename,
        }

    @staticmethod
    def gps_attrs(device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for device tracker."""
        return {
            "updated": datetime.utcfromtimestamp(device.position["ts"]).isoformat(),
            "online": device.online,
        }

    @staticmethod
    def balance_attrs(device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for balance sensor."""
        return {
            "operator": device.balance.get("operator"),
            "state": device.balance.get("state"),
            "updated": device.balance.get("ts"),
        }

    @staticmethod
    def gsm_attrs(device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for GSM sensor."""
        return {
            "raw": device.gsm_level,
            "imei": device.imei,
            "phone": device.phone,
            "online": device.online,
        }

    @staticmethod
    def errors_attrs(device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for Errors sensor."""
        return {"errors": device.errors.get("errors")}

    @staticmethod
    def engine_attrs(device: StarlineDevice) -> Dict[str, Any]:
        """Attributes for engine switch."""
        return {
            "autostart": device.car_state.get("r_start"),
            "ignition": device.car_state.get("run"),
        }
