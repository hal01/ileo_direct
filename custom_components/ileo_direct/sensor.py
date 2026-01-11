import logging
import csv
import io
from datetime import datetime, timedelta, time
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    UnitOfVolume,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

# Pour l'injection d'historique
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    StatisticMetaData,
)
from homeassistant.components.recorder.models import StatisticData

_LOGGER = logging.getLogger(__name__)

# --- CONFIGURATION UTILISATEUR ---
# Mettre à True SEULEMENT si vous voulez réécrire l'historique du tableau Énergie
# Attention : Cela peut écraser ou doubler des données existantes si les dates correspondent.
IMPORT_INDEX_HISTORY = False 

# Intervalle de mise à jour (12h)
SCAN_INTERVAL = timedelta(hours=12)

URL_LOGIN = "https://www.mel-ileo.fr/connexion.aspx"
URL_EXPORT_BASE = "https://www.mel-ileo.fr/espaceperso/mes-consommations.aspx"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Configuration de la plateforme."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    session = async_get_clientsession(hass)

    coordinator = IleoCoordinator(hass, session, username, password)
    await coordinator.async_refresh()

    async_add_entities([
        IleoIndexSensor(coordinator, username),
        IleoVolumeSensor(coordinator, username)
    ], True)


class IleoCoordinator(DataUpdateCoordinator):
    """Gère la récupération des données CSV."""

    def __init__(self, hass, session, username, password):
        super().__init__(hass, _LOGGER, name="Ileo Coordinator", update_interval=SCAN_INTERVAL)
        self.session = session
        self.username = username
        self.password = password
        self.historical_rows = [] 

    async def _async_update_data(self):
        try:
            # 1. Login
            payload = {
                "email": self.username,
                "password": self.password,
                "connexion": "1",
                "valider": "je me connecte"
            }
            async with self.session.post(URL_LOGIN, data=payload) as resp:
                if resp.status not in [200, 302]:
                    raise UpdateFailed(f"Erreur connexion: {resp.status}")
                await resp.text()

            # 2. Download CSV (6 mois)
            now = datetime.now()
            start_date = now - timedelta(days=180)
            fmt_url = "%d/%m/%Y"
            
            params = {
                "ex": "1",
                "dateDebut": start_date.strftime(fmt_url),
                "dateFin": now.strftime(fmt_url)
            }

            async with self.session.get(URL_EXPORT_BASE, params=params) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Erreur téléchargement: {resp.status}")
                content = await resp.text(encoding='ISO-8859-1')

            if not content or "html" in content.lower():
                raise UpdateFailed("Format CSV invalide (HTML reçu)")

            # 3. Parsing
            f = io.StringIO(content)
            try:
                dialect = csv.Sniffer().sniff(content[:1024])
                reader = csv.reader(f, dialect)
            except csv.Error:
                f.seek(0)
                reader = csv.reader(f, delimiter=';')

            rows = list(reader)
            if len(rows) < 2:
                raise UpdateFailed("CSV vide")

            headers = [h.lower() for h in rows[0]]
            
            self.idx_date = next((i for i, h in enumerate(headers) if "date" in h), 0)
            self.idx_index = next((i for i, h in enumerate(headers) if "index" in h or "relevé" in h), 3)
            self.idx_vol = next((i for i, h in enumerate(headers) if "volume" in h or "consommation" in h), 2)

            self.historical_rows = rows[1:] 
            return rows[-1]

        except Exception as e:
            raise UpdateFailed(f"Erreur update: {e}")


class IleoSensorBase(SensorEntity):
    def __init__(self, coordinator, username):
        self._coordinator = coordinator
        self._username = username
        self._attr_has_entity_name = True

    @property
    def available(self):
        return self._coordinator.last_update_success

    async def async_added_to_hass(self):
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        await self._coordinator.async_request_refresh()


class IleoIndexSensor(IleoSensorBase):
    """Capteur 1 : INDEX (Total Increasing)."""
    
    def __init__(self, coordinator, username):
        super().__init__(coordinator, username)
        self._attr_name = "Eau Iléo Index"
        self._attr_unique_id = f"ileo_index_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        row = self._coordinator.data
        if not row: return None
        try:
            clean_idx = ''.join(filter(str.isdigit, row[self._coordinator.idx_index]))
            return int(clean_idx)
        except: return None

    @property
    def extra_state_attributes(self):
        row = self._coordinator.data
        if not row: return {}
        return {"date_releve": row[self._coordinator.idx_date]}

    async def async_update(self):
        await super().async_update()
        # Option désactivée par défaut pour ne pas casser votre tableau Energie existant
        if IMPORT_INDEX_HISTORY:
            await self._inject_history()

    async def _inject_history(self):
        if not self._coordinator.historical_rows: return
        stats = []
        for row in self._coordinator.historical_rows:
            try:
                d_str = row[self._coordinator.idx_date]
                dt_naive = datetime.strptime(d_str, "%d/%m/%Y")
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                idx_val = int(''.join(filter(str.isdigit, row[self._coordinator.idx_index])))
                stats.append(StatisticData(start=dt_utc, state=idx_val, sum=idx_val))
            except: continue

        if stats:
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=self.name,
                source="recorder",
                statistic_id=self.entity_id,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
            async_import_statistics(self.hass, metadata, stats)


class IleoVolumeSensor(IleoSensorBase):
    """Capteur 2 : VOLUME (Measurement) avec Historique injecté."""
    
    def __init__(self, coordinator, username):
        super().__init__(coordinator, username)
        self._attr_name = "Eau Iléo Conso Jour"
        self._attr_unique_id = f"ileo_volume_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        # Measurement permet d'avoir des graphiques min/max/moyenne
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:water-opacity"

    @property
    def native_value(self):
        row = self._coordinator.data
        if not row: return None
        try:
            return self._parse_volume(row[self._coordinator.idx_vol])
        except: return None

    @property
    def extra_state_attributes(self):
        row = self._coordinator.data
        if not row: return {}
        try:
            clean_idx = ''.join(filter(str.isdigit, row[self._coordinator.idx_index]))
            return {
                "index_compteur": int(clean_idx),
                "date_releve": row[self._coordinator.idx_date]
            }
        except: return {}

    def _parse_volume(self, val_str):
        val_str = val_str.replace(',', '.').replace(' ', '')
        val_str = ''.join(c for c in val_str if c.isdigit() or c == '.' or c == '-')
        return float(val_str)

    async def async_update(self):
        """À chaque mise à jour, on injecte aussi l'historique des volumes."""
        await super().async_update()
        await self._inject_history()

    async def _inject_history(self):
        """Injecte l'historique de consommation journalière."""
        if not self._coordinator.historical_rows: return
        
        stats = []
        for row in self._coordinator.historical_rows:
            try:
                # Date
                d_str = row[self._coordinator.idx_date]
                dt_naive = datetime.strptime(d_str, "%d/%m/%Y")
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))

                # Volume
                vol_val = self._parse_volume(row[self._coordinator.idx_vol])

                # Pour 'measurement', on fournit le state (pas de sum)
                stats.append(StatisticData(start=dt_utc, state=vol_val))
            except: continue

        if stats:
            metadata = StatisticMetaData(
                has_mean=True,
                has_sum=False,
                name=self.name,
                source="recorder",
                statistic_id=self.entity_id,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
            async_import_statistics(self.hass, metadata, stats)
            _LOGGER.debug(f"Historique Volume injecté sur {self.entity_id} ({len(stats)} jours)")