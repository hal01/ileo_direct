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
        async_add_external_statistics,
        get_last_statistics,
        StatisticMetaData,
    )
except ImportError:
    async_import_statistics = None
    async_add_external_statistics = None
    get_last_statistics = None
    StatisticMetaData = None

# HA 2026.11 : le champ has_mean est remplacé par mean_type (cf. issue #7)
try:
    from homeassistant.components.recorder.models import StatisticMeanType
except ImportError:
    StatisticMeanType = None

from homeassistant.components.recorder.models import StatisticData
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_WATER_PRICE, CONF_WATER_PRICE_ENTITY


def _no_mean_kwargs():
    """Champ 'pas de moyenne' compatible avec les anciennes et nouvelles versions de HA."""
    if StatisticMeanType is not None:
        return {"mean_type": StatisticMeanType.NONE}
    return {"has_mean": False}


def _entry_value(entry, key, default=None):
    """Lit une valeur dans les options, puis dans les données de l'entrée."""
    return entry.options.get(key, entry.data.get(key, default))


async def async_setup_entry(hass, entry, async_add_entities):
    """Configuration des capteurs Iléo."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    username = entry.data["username"]

    import_all_history = _entry_value(entry, "import_history_energy", False)
    price = _entry_value(entry, CONF_WATER_PRICE, 0) or 0
    price_entity = _entry_value(entry, CONF_WATER_PRICE_ENTITY) or None

    entities = [
        IleoCompteurIndex(coordinator, username),
        IleoConsommationJournaliere(coordinator, username),
        IleoIndexModeGhost(coordinator, username, import_all_history, price, price_entity)
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
    def __init__(self, coordinator, username, import_all_history, price=0, price_entity=None):
        super().__init__(coordinator)
        self._import_all_history = import_all_history
        self._price = float(price or 0)          # €/m³, 0 = coût désactivé
        self._price_entity = price_entity        # entité donnant le prix en €/m³ (prioritaire)
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

    @property
    def cost_statistic_id(self):
        """Statistique externe du coût, propre à cette entité (ex. ileo_direct:ileo_index_mode_ghost_cout)."""
        return f"{DOMAIN}:{self.entity_id.split('.', 1)[1]}_cout"

    @property
    def extra_state_attributes(self):
        if not self._cost_enabled():
            return {}
        return {"statistique_cout": self.cost_statistic_id}

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

        # Vérif DB : on lit aussi state et sum du dernier point pour continuer le cumul
        last_stats_date = None
        last_state = None
        last_sum = None
        stat_id = self.entity_id
        try:
            last_stat = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, stat_id, True, {"start", "state", "sum"}
            )
            if last_stat and stat_id in last_stat and last_stat[stat_id]:
                row = last_stat[stat_id][0]
                start_ts = row["start"]
                last_stats_date = dt_util.utc_from_timestamp(start_ts) if isinstance(start_ts, (int, float)) else dt_util.as_utc(start_ts)
                last_state = row.get("state")
                last_sum = row.get("sum")
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

        # Injection : sum = cumul des écarts d'index, en partant de 0 sur une base vide.
        # Avec sum = index, le Tableau Énergie comptait tout l'index comme consommation
        # au premier point. Sur une base existante, on repart du dernier sum enregistré,
        # ce qui reste continu même pour les historiques créés avec sum = index.
        if last_stats_date is None or last_state is None or last_sum is None:
            prev_state, running_sum = rows_to_process[0]['val'], 0.0
        else:
            prev_state, running_sum = last_state, last_sum

        sum_before = running_sum
        stats_to_inject = []
        for item in rows_to_process:
            dt_utc = dt_util.as_utc(datetime.combine(item['date'].date(), time(12, 0)))
            delta = max(0, item['val'] - prev_state)  # un index qui recule n'est pas compté
            running_sum += delta
            prev_state = item['val']
            stats_to_inject.append(StatisticData(start=dt_utc, state=item['val'], sum=running_sum))

        if stats_to_inject:
            _LOGGER.info(f"Ghost Injection: {len(stats_to_inject)} relevés insérés. Dernier index: {stats_to_inject[-1]['state']} L")

            # Métadonnées standards (mean_type compatible HA 2026.11)
            metadata = StatisticMetaData(
                **_no_mean_kwargs(),
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
                return

            if self._cost_enabled():
                await self._inject_cost(stats_to_inject, sum_before)

    # --------------------------------------------------------------------------
    # Coût : le Ghost n'ayant pas d'état, le capteur de coût automatique du
    # Tableau Énergie reste "unknown". On injecte donc une statistique externe
    # de coût, à la même date que la consommation.
    # --------------------------------------------------------------------------
    def _cost_enabled(self):
        return bool(self._price_entity) or self._price > 0

    def _price_m3(self):
        """Prix en €/m³ : entité si configurée et disponible, sinon prix fixe."""
        if self._price_entity:
            st = self.hass.states.get(self._price_entity)
            try:
                return float(st.state)
            except (AttributeError, TypeError, ValueError):
                if self._price > 0:
                    _LOGGER.warning(f"{self._price_entity} indisponible, prix fixe utilisé ({self._price} €/m³)")
                    return self._price
                _LOGGER.warning(f"{self._price_entity} indisponible, coût non calculé pour ces relevés")
                return None
        return self._price

    async def _inject_cost(self, stats_to_inject, sum_before):
        """Cumule le coût (volume × prix au moment de l'injection)."""
        if async_add_external_statistics is None: return
        price = self._price_m3()
        if price is None: return

        cost_id = self.cost_statistic_id
        cost_sum = 0.0
        try:
            last_cost = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, cost_id, True, {"sum"}
            )
            if last_cost and last_cost.get(cost_id):
                cost_sum = last_cost[cost_id][0].get("sum") or 0.0
        except Exception:
            pass

        prev = sum_before
        cost_rows = []
        for s in stats_to_inject:
            cost_sum += (s["sum"] - prev) / 1000 * price
            prev = s["sum"]
            cost_rows.append(StatisticData(start=s["start"], state=round(cost_sum, 4), sum=round(cost_sum, 4)))

        metadata = StatisticMetaData(
            **_no_mean_kwargs(),
            has_sum=True,
            name=f"{self.name} coût",
            source=DOMAIN,
            statistic_id=cost_id,
            unit_of_measurement="EUR",
            unit_class=None,
        )
        try:
            async_add_external_statistics(self.hass, metadata, cost_rows)
            _LOGGER.info(f"Coût eau: {len(cost_rows)} relevés, cumul {cost_sum:.2f} € (prix {price} €/m³)")
        except Exception as e:
            _LOGGER.error(f"Erreur injection coût eau: {e}")
