"""Config flow pour l'intégration Iléo."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import IleoCoordinator

class IleoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère le flux de configuration initial."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Lie le flux d'options à l'entrée de configuration."""
        return IleoOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_USERNAME], 
                user_input[CONF_PASSWORD]
            )
            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], 
                    data=user_input
                )
            else:
                errors["base"] = "invalid_auth"

        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional("import_history_energy", default=False): bool,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _test_credentials(self, username, password):
        session = async_get_clientsession(self.hass)
        coordinator = IleoCoordinator(self.hass, session, username, password)
        try:
            await coordinator._async_update_data()
            return True
        except Exception:
            return False

class IleoOptionsFlowHandler(config_entries.OptionsFlow):
    """Gère le bouton 'Configurer'."""

    # PLUS DE __init__ ICI : HA gère l'injection de config_entry automatiquement.

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            coordinator = IleoCoordinator(
                self.hass, session, 
                user_input[CONF_USERNAME], 
                user_input[CONF_PASSWORD]
            )
            try:
                await coordinator._async_update_data()
                
                # Mise à jour des données
                self.hass.config_entries.async_update_entry(
                    self.config_entry, 
                    data=user_input,
                    title=user_input[CONF_USERNAME]
                )
                
                # Rechargement
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            except Exception:
                errors["base"] = "invalid_auth"

        # On utilise self.config_entry directement (il est fourni par HA)
        current_user = self.config_entry.data.get(CONF_USERNAME)
        current_pass = self.config_entry.data.get(CONF_PASSWORD)
        
        # On regarde dans 'options' (si déjà modifié) sinon dans 'data' (valeur initiale)
        current_hist = self.config_entry.options.get(
            "import_history_energy", 
            self.config_entry.data.get("import_history_energy", False)
        )

        options_schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=current_user): str,
            vol.Required(CONF_PASSWORD, default=current_pass): str,
            vol.Optional("import_history_energy", default=current_hist): bool,
        })

        return self.async_show_form(step_id="init", data_schema=options_schema, errors=errors)