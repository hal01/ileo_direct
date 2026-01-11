"""Initialisation de l'intégration Iléo."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import IleoCoordinator

PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Configuration via YAML (obsolète mais requise par HA)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configuration via l'interface UI."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    
    # On initialise le coordinateur
    session = async_get_clientsession(hass)
    coordinator = IleoCoordinator(hass, session, username, password)

    # Première récupération de données immédiate
    await coordinator.async_config_entry_first_refresh()

    # On stocke le coordinateur pour que sensor.py puisse l'utiliser
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # On lance la plateforme sensor
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Suppression de l'intégration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok