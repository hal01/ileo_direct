"""Plateforme de capteurs Iléo - Version V9 (Smart Bridge)."""
import logging
from datetime import datetime, time, timedelta
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
    RestoreEntity,
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
        IleoVisuelIndex(coordinator, username),
        IleoVisuelConso(coordinator, username),
        IleoSourceLive(coordinator, username),
        # Le nouveau capteur intelligent
        IleoSourceSmartGhost(coordinator, username)
    ], True)

def _parse_date(date_str):
    if not date_str: return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

# ... [Les classes IleoVisuelIndex, IleoVisuelConso et IleoSourceLive sont identiques à la V8] ...
# Pour simplifier la lecture, je ne remets que les classes modifiées ci-dessous.
# Copiez tout le bloc ci-dessous qui inclut les anciennes classes pour être sûr.

class IleoVisuelIndex(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Iléo Affichage Index"
        self._attr_unique_id = f"ileo_visuel_index_{username}"
        self._attr_icon = "mdi:counter"
    @property
    def native_value(self):
        row = self.coordinator.data
        if row and len(row) > 3:
            return ''.join(filter(str.isdigit, str(row[3])))
        return "Attente"
    @property
    def extra_state_attributes(self):
        attrs = {}
        if self.coordinator.data: attrs["date_donnee_ileo"] = self.coordinator.data[0]
        attrs["derniere_verification"] = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
        return attrs

class IleoVisuelConso(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Iléo Affichage Conso"
        self._attr_unique_id = f"ileo_visuel_conso_{username}"
        self._attr_icon = "mdi:water"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
    @property
    def native_value(self):
        row = self.coordinator.data
        if row and len(row) > 1: return str(row[1]).replace(',', '.').strip()
        return "Attente"

class IleoSourceLive(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Iléo Source (Mode Direct)"
        self._attr_unique_id = f"ileo_source_live_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:water-pump"
    @property
    def native_value(self):
        row = self.coordinator.data
        if not row: return None
        try:
            if len(row) > 3:
                clean = ''.join(filter(str.isdigit, str(row[3])))
                if clean: return int(clean)
            return None
        except Exception: return None

# ==============================================================================
# LE CAPTEUR INTELLIGENT V9
# ==============================================================================

class IleoSourceSmartGhost(CoordinatorEntity, RestoreEntity, SensorEntity):
    """
    Mode Différé V9 (Smart Bridge) :
    1. Met à jour son état au DERNIER INDEX CONNU (évite la chute future).
    2. Injecte l'historique à la date réelle.
    3. REMPLIT LE VIDE (Gap Fill) entre la date réelle et aujourd'hui avec le même index.
       -> Cela crée un 'plateau' parfait : Conso le jour J, puis 0 conso jusqu'à aujourd'hui.
    """
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Iléo Source (Mode Différé)"
        # On garde le même ID pour écraser la V7/V8
        self._attr_unique_id = f"ileo_source_ghost_{username}" 
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:ghost"

    @property
    def native_value(self):
        """Renvoie TOUJOURS le dernier index connu (le plus récent)."""
        row = self.coordinator.data
        if not row: return None
        try:
            if len(row) > 3:
                clean = ''.join(filter(str.isdigit, str(row[3])))
                if clean: return int(clean)
            return None
        except Exception: return None

    @callback
    def _handle_coordinator_update(self):
        super()._handle_coordinator_update()
        if self.hass:
            self.hass.async_create_task(self._inject_history_with_bridge())

    async def _inject_history_with_bridge(self):
        if not self.coordinator.historical_rows: return
        stats = []
        
        last_injected_date = None
        last_injected_val = None

        # 1. Injection classique (depuis le CSV)
        for row in self.coordinator.historical_rows:
            if len(row) < 4: continue
            try:
                dt_naive = _parse_date(row[0])
                if not dt_naive: continue
                dt_utc = dt_util.as_utc(datetime.combine(dt_naive.date(), time(12, 0)))
                
                clean = ''.join(filter(str.isdigit, str(row[3])))
                idx_val = int(clean)
                
                stats.append(StatisticData(start=dt_utc, state=idx_val, sum=idx_val))
                
                # On mémorise la donnée la plus récente trouvée dans le CSV
                if last_injected_date is None or dt_naive > last_injected_date:
                    last_injected_date = dt_naive
                    last_injected_val = idx_val
                    
            except Exception: continue

        # 2. Le PONT (Bridge) : Remplissage du vide jusqu'à hier
        # Si la dernière donnée date du 19 et qu'on est le 21, on doit injecter le 20.
        if last_injected_date and last_injected_val is not None:
            today = datetime.now()
            # On commence au lendemain de la dernière donnée CSV
            cursor_date = last_injected_date + timedelta(days=1)
            
            while cursor_date.date() < today.date():
                dt_utc = dt_util.as_utc(datetime.combine(cursor_date.date(), time(12, 0)))
                # On injecte la DERNIERE valeur connue (création du plateau)
                stats.append(StatisticData(start=dt_utc, state=last_injected_val, sum=last_injected_val))
                cursor_date += timedelta(days=1)

        if stats:
            metadata = StatisticMetaData(
                has_mean=False, has_sum=True, name=self.name, source="recorder",
                statistic_id=self.entity_id, unit_of_measurement=UnitOfVolume.LITERS,
                unit_class="volume",
            )
            async_import_statistics(self.hass, metadata, stats)
            _LOGGER.debug(f"Injection V9 terminée (Dernier CSV: {last_injected_date}, Pont jusqu'à: {cursor_date})")