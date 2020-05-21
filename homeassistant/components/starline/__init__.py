"""The StarLine component."""
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .account import StarlineAccount
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SCAN_OBD_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_OBD_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_SET_SCAN_INTERVAL,
    SERVICE_SET_SCAN_OBD_INTERVAL,
    SERVICE_UPDATE_OBD_STATE,
    SERVICE_UPDATE_STATE,
)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured StarLine."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the StarLine device from a config entry."""
    account = StarlineAccount(hass, config_entry)
    await account.update()
    await account.update_obd()
    if not account.api.available:
        raise ConfigEntryNotReady

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = account

    device_registry = await hass.helpers.device_registry.async_get_registry()
    for device in account.api.devices.values():
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id, **account.device_info(device)
        )

    for domain in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, domain)
        )

    async def async_set_scan_interval(call):
        """Service for set scan interval."""
        options = dict(config_entry.options)
        options[CONF_SCAN_INTERVAL] = call.data[CONF_SCAN_INTERVAL]
        options[CONF_SCAN_OBD_INTERVAL] = call.data[CONF_SCAN_OBD_INTERVAL]
        hass.config_entries.async_update_entry(entry=config_entry, options=options)

    hass.services.async_register(DOMAIN, SERVICE_UPDATE_STATE, account.update)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_OBD_STATE, account.update_obd)
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCAN_INTERVAL,
        async_set_scan_interval,
        schema=vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=10)
                )
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCAN_OBD_INTERVAL,
        async_set_scan_interval,
        schema=vol.Schema(
            {
                vol.Required(CONF_SCAN_OBD_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=100)
                )
            }
        ),
    )
    config_entry.add_update_listener(async_options_updated)
    await async_options_updated(hass, config_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for domain in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, domain)

    account: StarlineAccount = hass.data[DOMAIN][config_entry.entry_id]
    account.unload()
    return True


async def async_options_updated(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Triggered by config entry options updates."""
    account: StarlineAccount = hass.data[DOMAIN][config_entry.entry_id]
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_obd_interval = config_entry.options.get(
        CONF_SCAN_OBD_INTERVAL, DEFAULT_SCAN_OBD_INTERVAL
    )
    account.set_update_interval(CONF_SCAN_INTERVAL, scan_interval)
    account.set_update_interval(CONF_SCAN_OBD_INTERVAL, scan_obd_interval)
