"""Plateforme de capteurs Iléo - Logique V1.0.0 restaurée."""
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

# Gestion compatibilité
try:
    from homeassistant.components.recorder.statistics import (
        async_import_statistics,
        StatisticMetaData,
        StatisticMeanType,
    )
except ImportError:
    from homeassistant.components.recorder.statistics import (
        async_import_statistics,
        StatisticMetaData,
    )
    StatisticMeanType = None

from homeassistant.components.recorder.models import StatisticData
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    import_history_energy = entry.options.get("import_history_energy", entry.data.get("import_history_energy", False))
    username = entry.data["username"]

    async_add_entities([
        IleoIndexSensor(coordinator, username, import_history_energy),
        IleoVolumeSensor(coordinator, username)
    ], True)

def _parse_date(date_str):
    if not date_str: return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

class IleoSensorBase(CoordinatorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._username = username
        self._attr_has_entity_name = True

class IleoIndexSensor(IleoSensorBase):
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
            # LOGIQUE V1.0.0 EXACTE
            # On utilise l'index trouvé dynamiquement par le coordinateur
            idx_col = self.coordinator.idx_index
            
            # Nettoyage simple V1
            clean_idx = ''.join(filter(str.isdigit, row[idx_col]))
            return int(clean_idx)
        except Exception as e:
            _LOGGER.error("Erreur lecture Index (V1 Logic): %s", e)
            return None

    @property
    def extra_state_attributes(self):
        row = self.coordinator.data
        if not row: return {}
        try:
            return {"date_releve": row[self.coordinator.idx_date]}
        except: return {}

    @callback
    def _handle_coordinator_update(self):
        super()._handle_coordinator_update()
        if self._import_history and self.hass:
            self.hass.async_create_task(self._inject_history())

    async def _inject_history(self):
        if not self.coordinator.historical_rows: return
        stats = []
        idx_date = self.coordinator.idx_date
        idx_col = self.coordinator.idx_index

        for row in self.coordinator.historical_rows:
            try:
                dt_naive = _parse_date(row[idx_date])
                if not dt_naive: continue
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                
                # Nettoyage V1
                clean_idx = ''.join(filter(str.isdigit, row[idx_col]))
                idx_val = int(clean_idx)
                
                stats.append(StatisticData(start=dt_utc, state=idx_val, sum=idx_val))
            except Exception: continue

        if stats:
            metadata = StatisticMetaData(
                has_mean=False, has_sum=True, name=self.name, source="recorder",
                statistic_id=self.entity_id, unit_of_measurement=UnitOfVolume.LITERS,
                unit_class="volume",
            )
            async_import_statistics(self.hass, metadata, stats)

class IleoVolumeSensor(IleoSensorBase):
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
            # LOGIQUE V1.0.0 EXACTE
            idx_col = self.coordinator.idx_vol
            val_str = row[idx_col].replace(',', '.').replace(' ', '')
            val_str = ''.join(c for c in val_str if c.isdigit() or c == '.' or c == '-')
            return float(val_str)
        except Exception as e:
            _LOGGER.error("Erreur lecture Volume (V1 Logic): %s", e)
            return None

    @callback
    def _handle_coordinator_update(self):
        super()._handle_coordinator_update()
        if self.hass:
            self.hass.async_create_task(self._inject_history())

    async def _inject_history(self):
        if not self.coordinator.historical_rows: return
        stats = []
        idx_date = self.coordinator.idx_date
        idx_col = self.coordinator.idx_vol

        for row in self.coordinator.historical_rows:
            try:
                dt_naive = _parse_date(row[idx_date])
                if not dt_naive: continue
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                
                # Nettoyage V1
                val_str = row[idx_col].replace(',', '.').replace(' ', '')
                val_str = ''.join(c for c in val_str if c.isdigit() or c == '.' or c == '-')
                
                stats.append(StatisticData(start=dt_utc, state=float(val_str)))
            except Exception: continue

        if stats:
            mean_type = StatisticMeanType.ARITHMETIC if StatisticMeanType else "geometric"
            metadata = StatisticMetaData(
                has_mean=True, has_sum=False, name=self.name, source="recorder",
                statistic_id=self.entity_id, unit_of_measurement=UnitOfVolume.LITERS,
                mean_type=mean_type,
                unit_class="volume",
            )
            async_import_statistics(self.hass, metadata, stats)