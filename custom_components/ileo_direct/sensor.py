"""Plateforme de capteurs Iléo - Version Finale (Clean & Silent)."""
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
from homeassistant.components.recorder import get_instance

_LOGGER = logging.getLogger(__name__)

# Imports statistiques sécurisés
try:
    from homeassistant.components.recorder.statistics import (
        async_import_statistics,
        get_last_statistics,
        StatisticMetaData,
    )
except ImportError:
    async_import_statistics = None
    get_last_statistics = None
    StatisticMetaData = None

from homeassistant.components.recorder.models import StatisticData
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Configuration des capteurs Iléo."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    username = entry.data["username"]
    
    import_all_history = entry.options.get(
        "import_history_energy", 
        entry.data.get("import_history_energy", False)
    )
    
    entities = [
        IleoCompteurIndex(coordinator, username),
        IleoConsommationJournaliere(coordinator, username),
        IleoIndexModeGhost(coordinator, username, import_all_history)
    ]
    
    async_add_entities(entities, False)

def _extract_data(row):
    """Extraction et nettoyage des données CSV."""
    if not row or len(row) < 4: return None, None, None
    try:
        dt = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(row[0], fmt)
                break
            except ValueError: continue
        if not dt: return None, None, None
        conso = float(str(row[1]).replace(',', '.').strip())
        index = int(''.join(filter(str.isdigit, str(row[3]))))
        return dt, conso, index
    except: return None, None, None

# ==============================================================================
# SENSORS CLASSIQUES
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
        self._attr_icon = "mdi:faucet"

    @property
    def native_value(self):
        _, _, index = _extract_data(self.coordinator.data)
        return index
        
    @property
    def extra_state_attributes(self):
        dt, conso, _ = _extract_data(self.coordinator.data)
        return {"date_du_releve": dt.strftime("%d/%m/%Y"), "conso_jour": conso} if dt else {}

class IleoConsommationJournaliere(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Ileo Consommation Eau (journalière)"
        self._attr_unique_id = f"ileo_conso_jour_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:faucet"

    @property
    def native_value(self):
        _, conso, _ = _extract_data(self.coordinator.data)
        return conso

    @property
    def extra_state_attributes(self):
        dt, _, index = _extract_data(self.coordinator.data)
        return {"date_du_releve": dt.strftime("%d/%m/%Y"), "index": index} if dt else {}

# ==============================================================================
# GHOST SENSOR (Production)
# ==============================================================================
class IleoIndexModeGhost(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username, import_all_history):
        super().__init__(coordinator)
        self._import_all_history = import_all_history
        self._attr_has_entity_name = True
        self._attr_name = "Ileo Index Mode Ghost"
        self._attr_unique_id = f"ileo_mode_ghost_{username}" 
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        
        # Configuration standard conforme pour l'eau
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:faucet-clock"

    @property
    def native_value(self): return None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.hass.async_create_task(self._inject_history_logic())

    @callback
    def _handle_coordinator_update(self):
        super()._handle_coordinator_update()
        if self.hass: self.hass.async_create_task(self._inject_history_logic())

    async def _inject_history_logic(self):
        if not self.coordinator.historical_rows: return
            
        clean_history = []
        for row in self.coordinator.historical_rows:
            dt_obj, _, idx = _extract_data(row)
            if dt_obj and idx is not None:
                clean_history.append({'date': dt_obj, 'val': idx})
        clean_history.sort(key=lambda x: x['date'])
        
        if not clean_history: return

        # Vérif DB
        last_stats_date = None
        stat_id = self.entity_id
        try:
            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, stat_id, True, {"start"}
            )
            if last_stat and stat_id in last_stat and last_stat[stat_id]:
                start_ts = last_stat[stat_id][0]["start"]
                last_stats_date = dt_util.utc_from_timestamp(start_ts) if isinstance(start_ts, (int, float)) else dt_util.as_utc(start_ts)
        except Exception:
            pass # On ignore les erreurs de lecture silencieusement

        # Filtrage
        rows_to_process = []
        if last_stats_date is None:
            # Base vide : on regarde l'option
            rows_to_process = clean_history if self._import_all_history else [clean_history[-1]]
        else:
            # Base existante : on ajoute le delta
            for item in clean_history:
                item_utc = dt_util.as_utc(datetime.combine(item['date'].date(), time(12, 0)))
                if item_utc > last_stats_date:
                    rows_to_process.append(item)

        if not rows_to_process: return

        # Injection
        stats_to_inject = []
        for item in rows_to_process:
            dt_utc = dt_util.as_utc(datetime.combine(item['date'].date(), time(12, 0)))
            stats_to_inject.append(StatisticData(start=dt_utc, state=item['val'], sum=item['val']))

        if stats_to_inject:
            _LOGGER.info(f"Ghost Injection: {len(stats_to_inject)} relevés insérés. Dernier index: {stats_to_inject[-1]['state']} L")
            
            # Métadonnées standards (sans hack mean_type)
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=self.name,
                source="recorder",
                statistic_id=self.entity_id,
                unit_of_measurement=UnitOfVolume.LITERS,
                unit_class="volume",
            )
            
            try:
                async_import_statistics(self.hass, metadata, stats_to_inject)
            except Exception as e:
                _LOGGER.error(f"Erreur Injection Ghost: {e}")