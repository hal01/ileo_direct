"""Plateforme de capteurs Iléo."""
import logging
from datetime import datetime, time
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    StatisticMetaData,
)
from homeassistant.components.recorder.models import StatisticData
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configuration des capteurs depuis l'entrée de config."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Récupération de l'option "Importer historique énergie"
    # On regarde dans 'options' en priorité (si modifié via le bouton Configurer), sinon dans 'data'
    import_history_energy = entry.options.get("import_history_energy", entry.data.get("import_history_energy", False))
    username = entry.data["username"]

    async_add_entities([
        IleoIndexSensor(coordinator, username, import_history_energy),
        IleoVolumeSensor(coordinator, username)
    ], True)


class IleoSensorBase(CoordinatorEntity):
    """Base pour les capteurs Iléo."""
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._username = username
        self._attr_has_entity_name = True

class IleoIndexSensor(IleoSensorBase):
    """Capteur 1 : INDEX."""
    
    def __init__(self, coordinator, username, import_history):
        super().__init__(coordinator, username)
        self._import_history = import_history
        self._attr_name = "Index Compteur"
        self._attr_unique_id = f"ileo_index_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        row = self.coordinator.data
        if not row: return None
        try:
            clean_idx = ''.join(filter(str.isdigit, row[self.coordinator.idx_index]))
            return int(clean_idx)
        except: return None

    @property
    def extra_state_attributes(self):
        row = self.coordinator.data
        if not row: return {}
        return {"date_releve": row[self.coordinator.idx_date]}

    @callback
    def _handle_coordinator_update(self):
        """Appelé quand le coordinateur a de nouvelles données."""
        # On met à jour l'état du capteur (Synchrone)
        super()._handle_coordinator_update()
        
        # On lance l'injection d'historique en tâche de fond (Asynchrone)
        if self._import_history:
            self.hass.async_create_task(self._inject_history())

    async def _inject_history(self):
        if not self.coordinator.historical_rows: return
        stats = []
        for row in self.coordinator.historical_rows:
            try:
                d_str = row[self.coordinator.idx_date]
                dt_naive = datetime.strptime(d_str, "%d/%m/%Y")
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                idx_val = int(''.join(filter(str.isdigit, row[self.coordinator.idx_index])))
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
    """Capteur 2 : VOLUME."""
    
    def __init__(self, coordinator, username):
        super().__init__(coordinator, username)
        self._attr_name = "Conso Jour"
        self._attr_unique_id = f"ileo_volume_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        row = self.coordinator.data
        if not row: return None
        try:
            vol_str = row[self.coordinator.idx_vol].replace(',', '.').replace(' ', '')
            vol_str = ''.join(c for c in vol_str if c.isdigit() or c == '.' or c == '-')
            return float(vol_str)
        except: return None

    @callback
    def _handle_coordinator_update(self):
        """Appelé quand le coordinateur a de nouvelles données."""
        super()._handle_coordinator_update()
        # Lancement asynchrone sécurisé
        self.hass.async_create_task(self._inject_history())

    async def _inject_history(self):
        """Toujours injecter l'historique pour le volume."""
        if not self.coordinator.historical_rows: return
        stats = []
        for row in self.coordinator.historical_rows:
            try:
                d_str = row[self.coordinator.idx_date]
                dt_naive = datetime.strptime(d_str, "%d/%m/%Y")
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                vol_str = row[self.coordinator.idx_vol].replace(',', '.').replace(' ', '')
                vol_str = ''.join(c for c in vol_str if c.isdigit() or c == '.' or c == '-')
                vol_val = float(vol_str)
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