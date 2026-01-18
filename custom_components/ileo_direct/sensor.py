"""Plateforme de capteurs Iléo - Version V5 (Attributs & Renommage)."""
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

# Gestion compatibilité historique
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
    username = entry.data["username"]
    
    async_add_entities([
        IleoIndexSensorFinal(coordinator, username),
        IleoVolumeSensorFinal(coordinator, username)
    ], True)

def _parse_date(date_str):
    if not date_str: return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

class IleoSensorBase(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._username = username
        self._attr_has_entity_name = True

class IleoIndexSensorFinal(IleoSensorBase):
    def __init__(self, coordinator, username):
        super().__init__(coordinator, username)
        # RENOMMAGE DEMANDÉ
        self._attr_name = "Iléo Index Compteur"
        self._attr_unique_id = f"ileo_index_{username}_v5"
        
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self):
        row = self.coordinator.data
        if not row: return None
        try:
            # Colonne 3 (Index)
            if len(row) > 3:
                val = str(row[3])
                clean = ''.join(filter(str.isdigit, val))
                if clean:
                    return int(clean)
            return None
        except Exception:
            return None

    @property
    def extra_state_attributes(self):
        if self.coordinator.data and len(self.coordinator.data) > 0:
            return {"date_releve": self.coordinator.data[0]}
        return {}

    @callback
    def _handle_coordinator_update(self):
        super()._handle_coordinator_update()
        if self.hass:
            self.hass.async_create_task(self._inject_history())

    async def _inject_history(self):
        if not self.coordinator.historical_rows: return
        stats = []
        for row in self.coordinator.historical_rows:
            if len(row) < 4: continue
            try:
                dt_naive = _parse_date(row[0])
                if not dt_naive: continue
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                
                clean = ''.join(filter(str.isdigit, str(row[3])))
                idx_val = int(clean)
                
                stats.append(StatisticData(start=dt_utc, state=idx_val, sum=idx_val))
            except Exception: continue

        if stats:
            metadata = StatisticMetaData(
                has_mean=False, has_sum=True, name=self.name, source="recorder",
                statistic_id=self.entity_id, unit_of_measurement=UnitOfVolume.LITERS,
                unit_class="volume",
            )
            async_import_statistics(self.hass, metadata, stats)

class IleoVolumeSensorFinal(IleoSensorBase):
    def __init__(self, coordinator, username):
        super().__init__(coordinator, username)
        # RENOMMAGE DEMANDÉ
        self._attr_name = "Iléo Conso Dernier Jour"
        self._attr_unique_id = f"ileo_volume_{username}_v5"
        
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:water"

    @property
    def native_value(self):
        row = self.coordinator.data
        if not row: return None
        try:
            # Colonne 1 (Volume)
            if len(row) > 1:
                val = str(row[1]).replace(',', '.').strip()
                return float(val)
            return None
        except Exception:
            return None

    @property
    def extra_state_attributes(self):
        """AJOUT DES ATTRIBUTS : DATE et INDEX."""
        row = self.coordinator.data
        attrs = {}
        if row:
            # Ajout de la date (Col 0)
            if len(row) > 0:
                attrs["date_releve"] = row[0]
            
            # Ajout de l'index (Col 3) pour référence
            if len(row) > 3:
                try:
                    val = str(row[3])
                    clean = ''.join(filter(str.isdigit, val))
                    if clean:
                        attrs["index_compteur"] = int(clean)
                except Exception:
                    pass
        return attrs

    @callback
    def _handle_coordinator_update(self):
        super()._handle_coordinator_update()
        if self.hass:
            self.hass.async_create_task(self._inject_history())

    async def _inject_history(self):
        if not self.coordinator.historical_rows: return
        stats = []
        for row in self.coordinator.historical_rows:
            if len(row) < 2: continue
            try:
                dt_naive = _parse_date(row[0])
                if not dt_naive: continue
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                
                val = str(row[1]).replace(',', '.').strip()
                if val:
                    stats.append(StatisticData(start=dt_utc, state=float(val)))
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