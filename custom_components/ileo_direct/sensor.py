"""Plateforme de capteurs Iléo - Version ULTIME (Multi-Modes)."""
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
        # 1. Capteurs VISUELS (Pour l'affichage Dashboard uniquement)
        IleoVisuelIndex(coordinator, username),
        IleoVisuelConso(coordinator, username),
        
        # 2. Capteurs SOURCES ENERGIE (Au choix de l'utilisateur)
        IleoSourceLive(coordinator, username),   # Option A : Mode Direct
        IleoSourceGhost(coordinator, username)   # Option B : Mode Différé (Injection)
    ], True)

def _parse_date(date_str):
    if not date_str: return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

# ==============================================================================
# 1. CAPTEURS VISUELS (Simples afficheurs de texte, pas de stats)
# ==============================================================================

class IleoVisuelIndex(CoordinatorEntity, SensorEntity):
    """Affiche l'index tel quel pour le Dashboard."""
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
        if self.coordinator.data:
            return {"date_releve": self.coordinator.data[0]}
        return {}

class IleoVisuelConso(CoordinatorEntity, SensorEntity):
    """Affiche la conso du relevé pour le Dashboard."""
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
        if row and len(row) > 1:
            val = str(row[1]).replace(',', '.').strip()
            return val
        return "Attente"
    
    @property
    def extra_state_attributes(self):
        if self.coordinator.data:
            return {"date_releve": self.coordinator.data[0]}
        return {}


# ==============================================================================
# 2. CAPTEURS SOURCES POUR LE TABLEAU ENERGIE
# ==============================================================================

class IleoSourceLive(CoordinatorEntity, SensorEntity):
    """
    OPTION 1 : MODE DIRECT
    - Valeur : Vrai index.
    - Comportement : Change quand on reçoit la donnée (le 19).
    - Injection Historique : NON (pour éviter les doublons).
    - Résultat : La conso s'affiche le jour de la réception (le 19).
    """
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

    # PAS d'injection d'historique ici !


class IleoSourceGhost(CoordinatorEntity, SensorEntity):
    """
    OPTION 2 : MODE DIFFÉRÉ (FANTÔME)
    - Valeur : Toujours 0.
    - Comportement : Ne bouge jamais en direct (pas de conso le 19).
    - Injection Historique : OUI.
    - Résultat : La conso s'affiche rétroactivement à la date réelle (le 17).
    """
    def __init__(self, coordinator, username):
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = "Iléo Source (Mode Différé)"
        self._attr_unique_id = f"ileo_source_ghost_{username}"
        self._attr_native_unit_of_measurement = UnitOfVolume.LITERS
        self._attr_device_class = SensorDeviceClass.WATER
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:ghost"

    @property
    def native_value(self):
        return 0 # Reste à 0 pour être invisible "aujourd'hui"

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
