"""Constantes pour l'intégration Iléo."""
from datetime import timedelta

DOMAIN = "ileo_direct"
SCAN_INTERVAL = timedelta(hours=12)

# URLs
URL_LOGIN = "https://www.mel-ileo.fr/connexion.aspx"
URL_EXPORT_BASE = "https://www.mel-ileo.fr/espaceperso/mes-consommations.aspx"

# Options du coût de l'eau (capteur Ghost)
CONF_WATER_PRICE = "water_price"               # prix fixe en €/m³ (0 = désactivé)
CONF_WATER_PRICE_ENTITY = "water_price_entity" # entité donnant le prix en €/m³ (prioritaire)
