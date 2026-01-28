"""Plateforme de capteurs Iléo - Version V19 (Fix Device Class Conflict)."""
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

# Gestion Recorder et Statistiques
from homeassistant.components.recorder import get_instance
try:
    from homeassistant.components.recorder.statistics import (
        async_import_statistics,
        get_last_statistics,
        StatisticMetaData,
        StatisticMeanType,
    )
except ImportError:
    from homeassistant.components.recorder.statistics import (
        async_import_statistics,
        get_last_statistics,
        StatisticMetaData,
    )
    StatisticMeanType = None

from homeassistant.components.recorder.models import StatisticData
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configuration des capteurs Iléo via l'intégration."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    username = entry.data["username"]
    
    import_all_history = entry.options.get(
        "import_history_energy", 
        entry.data.get("import_history_energy", False)
    )
    
    async_add_entities([
        IleoCompteurIndex(coordinator, username),
        IleoConsommationJournaliere(coordinator, username),
        IleoIndexModeGhost(coordinator, username, import_all_history)
    ], True)

def _extract_data(row):
    """Extraction et nettoyage des données CSV."""
    if not row or len(row) < 4:
        return None, None, None
    try:
        dt = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(row[0], fmt)
                break
            except ValueError:
                continue
        if not dt: return None, None, None
        conso_str = str(row[1]).replace(',', '.').strip()
        conso = float(conso_str)
        idx_clean = ''.join(filter(str.isdigit, str(row[3])))
        index = int(idx_clean)
        return dt, conso, index
    except Exception:
        return None, None, None

# ==============================================================================
# 1. SENSOR : Ileo Compteur Eau (Index)
# ==============================================================================
class IleoCompteurIndex(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Ileo Compteur Eau (Index)"
        self._attr_unique_id = f"ileo_compteur_index_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self):
        _, _, index = _extract_data(self.coordinator.data)
        return index

    @property
    def extra_state_attributes(self):
        dt, conso, _ = _extract_data(self.coordinator.data)
        if dt:
            return {"date_du_releve": dt.strftime("%d/%m/%Y"), "conso_jour": conso}
        return {}

# ==============================================================================
# 2. SENSOR : Ileo Consommation Eau (journalière)
# ==============================================================================
class IleoConsommationJournaliere(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Ileo Consommation Eau (journalière)"
        self._attr_unique_id = f"ileo_conso_jour_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        # CORRECTION : Passage de MEASUREMENT à TOTAL pour compatibilité WATER
        self._attr_state_class = SensorStateClass.TOTAL 
        self._attr_icon = "mdi:water"

    @property
    def native_value(self):
        _, conso, _ = _extract_data(self.coordinator.data)
        return conso

    @property
    def extra_state_attributes(self):
        dt, _, index = _extract_data(self.coordinator.data)
        if dt:
            return {"date_du_releve": dt.strftime("%d/%m/%Y"), "index": index}
        return {}

# ==============================================================================
# 3. SENSOR : Ileo Index Mode Ghost (Injecteur)
# ==============================================================================
class IleoIndexModeGhost(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username, import_all_history):
        super().__init__(coordinator)
        self._import_all_history = import_all_history
        self._attr_has_entity_name = True
        self._attr_name = "Ileo Index Mode Ghost"
        self._attr_unique_id = f"ileo_mode_ghost_{username}" 
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:ghost"

    @property
    def native_value(self):
        return None

    @callback
    def _handle_coordinator_update(self):
        super()._handle_coordinator_update()
        if self.hass:
            self.hass.async_create_task(self._inject_history_logic())

    async def _inject_history_logic(self):
        if not self.coordinator.historical_rows: return
        
        clean_history = []
        for row in self.coordinator.historical_rows:
            dt_obj, _, idx = _extract_data(row)
            if dt_obj and idx is not None:
                clean_history.append({'date': dt_obj, 'val': idx})
        clean_history.sort(key=lambda x: x['date'])
        if not clean_history: return

        last_stats_date = None
        stat_id = self.entity_id

        try:
            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, stat_id, True, {"start"}
            )
            if last_stat and stat_id in last_stat and last_stat[stat_id]:
                start_ts = last_stat[stat_id][0]["start"]
                last_stats_date = dt_util.utc_from_timestamp(start_ts) if isinstance(start_ts, (int, float)) else dt_util.as_utc(start_ts)
        except Exception as e:
            _LOGGER.warning(f"Ghost: Erreur lecture DB : {e}")
            return

        rows_to_process = []
        if last_stats_date is None:
            rows_to_process = clean_history if self._import_all_history else [clean_history[-1]]
        else:
            for item in clean_history:
                item_utc = dt_util.as_utc(datetime.combine(item['date'].date(), time(12, 0)))
                if item_utc > last_stats_date:
                    rows_to_process.append(item)

        if not rows_to_process: return

        stats_to_inject = []
        for item in rows_to_process:
            dt_utc = dt_util.as_utc(datetime.combine(item['date'].date(), time(12, 0)))
            stats_to_inject.append(StatisticData(start=dt_utc, state=item['val'], sum=item['val']))

        if stats_to_inject:
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=self.name,
                source="recorder",
                statistic_id=self.entity_id,
                unit_of_measurement=UnitOfVolume.LITERS,
                unit_class="volume",
            )
            # Protection contre le warning mean_type
            async_import_statistics(self.hass, metadata, stats_to_inject, mean_type=None)