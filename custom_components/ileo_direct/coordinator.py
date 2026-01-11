"""Coordinateur de données Iléo."""
import logging
import csv
import io
from datetime import datetime, timedelta
import aiohttp

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from .const import DOMAIN, SCAN_INTERVAL, URL_LOGIN, URL_EXPORT_BASE

_LOGGER = logging.getLogger(__name__)

class IleoCoordinator(DataUpdateCoordinator):
    """Gère la récupération des données CSV."""

    def __init__(self, hass, session, username, password):
        """Initialisation."""
        super().__init__(hass, _LOGGER, name="Ileo Coordinator", update_interval=SCAN_INTERVAL)
        self.session = session
        self.username = username
        self.password = password
        
        self.idx_date = 0
        self.idx_index = 3
        self.idx_vol = 2
        self.historical_rows = [] 

    async def _async_update_data(self):
        """Récupération des données."""
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
                raise UpdateFailed("Identifiants incorrects ou Erreur Site (HTML reçu)")

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
            
            # Recherche dynamique des colonnes
            self.idx_date = next((i for i, h in enumerate(headers) if "date" in h), 0)
            self.idx_index = next((i for i, h in enumerate(headers) if "index" in h or "relevé" in h), 3)
            self.idx_vol = next((i for i, h in enumerate(headers) if "volume" in h or "consommation" in h), 2)

            # Stockage
            self.historical_rows = rows[1:] 
            return rows[-1] # Renvoie la dernière ligne pour les capteurs

        except Exception as e:
            raise UpdateFailed(f"Erreur update: {e}")