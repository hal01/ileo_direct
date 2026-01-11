"""Constantes pour l'intégration Iléo."""
from datetime import timedelta

DOMAIN = "ileo_direct"
SCAN_INTERVAL = timedelta(hours=12)

# URLs
URL_LOGIN = "https://www.mel-ileo.fr/connexion.aspx"
URL_EXPORT_BASE = "https://www.mel-ileo.fr/espaceperso/mes-consommations.aspx"