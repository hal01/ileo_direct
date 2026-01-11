# Iléo Water Direct pour Home Assistant

Intégration personnalisée pour récupérer la consommation d'eau et l'historique depuis le site **Iléo (Mel-Iléo)**.

## Fonctionnalités
- Récupération de l'index du compteur (compatible Dashboard Énergie).
- Récupération de la consommation journalière (en Litres).
- **Historique complet** : Injection des données des 6 derniers mois dans les statistiques Home Assistant.

## Installation via HACS
1. Dans HACS, cliquez sur les 3 points en haut à droite > **Dépôts personnalisés**.
2. Ajoutez l'URL : `https://github.com/VOTRE_PSEUDO/ileo_direct`.
3. Catégorie : **Intégration**.
4. Cliquez sur **Installer**.

## Configuration (YAML)
Ajoutez ceci dans votre `configuration.yaml` :

```yaml
sensor:
  - platform: ileo_direct
    username: "votre_email@exemple.com"
    password: "votre_mot_de_passe"