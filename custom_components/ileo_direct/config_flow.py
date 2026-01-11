"""Config flow pour l'intégration Iléo."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import IleoCoordinator

class IleoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère le flux de configuration UI."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Gère l'étape initiale (saisie identifiants)."""
        errors = {}

        if user_input is not None:
            # On teste la connexion avant de valider
            valid = await self._test_credentials(
                user_input[CONF_USERNAME], 
                user_input[CONF_PASSWORD]
            )
            
            if valid:
                # Création de l'entrée config si tout est OK
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], 
                    data=user_input
                )
            else:
                errors["base"] = "invalid_auth"

        # Le schéma du formulaire
        data_schema = vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional("import_history_energy", default=False): bool,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def _test_credentials(self, username, password):
        """Teste si les identifiants fonctionnent."""
        session = async_get_clientsession(self.hass)
        coordinator = IleoCoordinator(self.hass, session, username, password)
        try:
            # On tente une mise à jour unique pour vérifier
            await coordinator._async_update_data()
            return True
        except Exception:
            return False