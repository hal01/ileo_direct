"""Config flow pour l'intégration Iléo."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_WATER_PRICE, CONF_WATER_PRICE_ENTITY
from .coordinator import IleoCoordinator

def _price_fields(price=0.0, price_entity=None):
    """Champs du coût de l'eau (prix fixe en €/m³ et/ou entité de prix)."""
    return {
        vol.Optional(CONF_WATER_PRICE, default=price): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=50, step=0.001, unit_of_measurement="€/m³",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            CONF_WATER_PRICE_ENTITY,
            description={"suggested_value": price_entity},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["input_number", "sensor"])
        ),
    }


class IleoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère le flux de configuration initial."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Lie le flux d'options à l'entrée de configuration."""
        # On passe config_entry au constructeur
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
            **_price_fields(),
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

    def __init__(self, config_entry):
        """Initialisation."""
        # On stocke l'entrée dans une variable AVEC UN UNDERSCORE (_config_entry)
        # pour ne pas entrer en conflit avec la propriété protégée de Home Assistant.
        self._config_entry = config_entry

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
                
                # Mise à jour des données en utilisant self._config_entry
                self.hass.config_entries.async_update_entry(
                    self._config_entry, 
                    data=user_input,
                    title=user_input[CONF_USERNAME]
                )
                
                # Rechargement
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
                return self.async_create_entry(title="", data={})
            except Exception:
                errors["base"] = "invalid_auth"

        # Lecture des valeurs actuelles via self._config_entry
        current_user = self._config_entry.data.get(CONF_USERNAME)
        current_pass = self._config_entry.data.get(CONF_PASSWORD)
        
        current_hist = self._config_entry.options.get(
            "import_history_energy", 
            self._config_entry.data.get("import_history_energy", False)
        )

        current_price = self._config_entry.options.get(
            CONF_WATER_PRICE,
            self._config_entry.data.get(CONF_WATER_PRICE, 0.0)
        )
        current_price_entity = self._config_entry.options.get(
            CONF_WATER_PRICE_ENTITY,
            self._config_entry.data.get(CONF_WATER_PRICE_ENTITY)
        )

        options_schema = vol.Schema({
            vol.Required(CONF_USERNAME, default=current_user): str,
            vol.Required(CONF_PASSWORD, default=current_pass): str,
            vol.Optional("import_history_energy", default=current_hist): bool,
            **_price_fields(current_price, current_price_entity),
        })

        return self.async_show_form(step_id="init", data_schema=options_schema, errors=errors)