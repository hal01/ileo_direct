# 💧 Iléo Water Direct pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/github/v/release/hal01/ileo_direct)](https://github.com/hal01/ileo_direct/releases)

Intégration personnalisée pour récupérer votre consommation d'eau depuis le fournisseur **Iléo (Mel-Iléo)** directement dans Home Assistant.

Cette intégration se connecte à votre espace client, récupère votre index et votre consommation journalière, et injecte l'historique dans les statistiques de Home Assistant.

## ✨ Fonctionnalités

* **100% Interface Graphique :** Configuration facile via le menu "Appareils et services" (Config Flow).
* **Dashboard Énergie :** Compatible nativement avec le tableau de bord Énergie (Total Increasing).
* **Historique Profond :** Récupère les 6 derniers mois d'historique (CSV) et les injecte dans les statistiques.
* **Double Capteur :**
    * `sensor.index_compteur` : Pour le suivi total.
    * `sensor.conso_jour` : Pour l'analyse quotidienne (en Litres).

## 🚩 Pré-Requis

* Etre équipé d'un **compteur connecté** ILEO 😁!
* Avoir un compte et un **espace personnel ILEO** créé et accessible avec identifiants et mots de passe.
     ==> vérifier que l'on accède via : `https://www.mel-ileo.fr/espaceperso/mes-consommations.aspx`
* S'assurer que des données sont **déjà présentes** dans l'espace consommation ! 

## 🚀 Installation

### Via HACS (Recommandé)

1.  Ouvrez HACS dans Home Assistant.
2.  Allez dans **Intégrations** > Menu (3 points) > **Dépôts personnalisés**.
3.  Ajoutez l'URL de ce dépôt : `https://github.com/hal01/ileo_direct`.
4.  Catégorie : **Intégration**.
5.  Cliquez sur **Télécharger**.
6.  **Redémarrez Home Assistant**.

### Installation Manuelle

1.  Téléchargez la dernière version.
2.  Copiez le dossier `custom_components/ileo_direct` dans votre dossier `/config/custom_components/`.
3.  Redémarrez Home Assistant.

## ⚙️ Configuration

Plus besoin d'éditer des fichiers YAML !

1.  Allez dans **Paramètres** > **Appareils et services**.
2.  Cliquez sur **+ Ajouter une intégration**.
3.  Recherchez **Iléo Water Direct**.
4.  Remplissez le formulaire :
    * **Email** : Votre identifiant Iléo.
    * **Mot de passe** : Votre mot de passe.
    * **Réécrire l'historique** (Optionnel) : Cochez cette case *uniquement* si vous configurez votre Dashboard Énergie pour la première fois et souhaitez importer les 6 mois passés. *Attention : si vous avez déjà des données, cela peut créer des doublons.*

## 📊 Utilisation

### Dashboard Énergie
1.  Allez dans **Paramètres** > **Tableaux de bord** > **Énergie**.
2.  Dans la section **Consommation d'eau**, cliquez sur "Ajouter une source".
3.  Sélectionnez le capteur : `sensor.index_compteur` (ou nom similaire).

### Carte Graphique (Lovelace)
Pour visualiser votre consommation journalière historique :

```yaml
type: statistics-graph
title: Consommation Eau (6 mois)
days_to_show: 180
period: day
chart_type: bar
stat_type: mean
entities:
  - sensor.conso_jour
