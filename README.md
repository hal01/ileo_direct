# 💧 Iléo Water Direct pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/github/v/release/hal01/ileo_direct)](https://github.com/hal01/ileo_direct/releases)

Intégration personnalisée pour récupérer votre consommation d'eau depuis le fournisseur **Iléo (Mel-Iléo)** directement dans Home Assistant.

Cette intégration est spécialement conçue pour gérer le **décalage de publication des données** (J+2) inhérent à Iléo. Elle propose plusieurs modes de fonctionnement pour s'adapter à votre préférence d'affichage dans le Dashboard Énergie.

## ✨ Fonctionnalités Clés

* **Architecture Multi-Modes :** Choisissez entre une vue "Directe" (réception = consommation) ou une vue "Historique stricte" (injection rétroactive).
* **0% Doublon :** Gestion intelligente pour éviter que la consommation ne soit comptée deux fois.
* **Historique Profond :** Récupération et injection automatique des 6 derniers mois d'historique.
* **Capteurs Visuels dédiés :** Des capteurs simples (texte) pour vos cartes Lovelace qui affichent toujours la dernière info connue sans perturber les statistiques.

## 🚩 Pré-Requis

* Un compteur connecté ILEO.
* Un compte espace personnel ILEO actif.
* Vérifiez l'accès via : `https://www.mel-ileo.fr/espaceperso/mes-consommations.aspx`
* **Important :** Des données doivent déjà être présentes dans l'espace client.

## 🚀 Installation

### Via HACS (Recommandé)

1.  Ouvrez HACS > **Intégrations** > Menu (3 points) > **Dépôts personnalisés**.
2.  Ajoutez l'URL : `https://github.com/hal01/ileo_direct`.
3.  Catégorie : **Intégration**.
4.  Cliquez sur **Télécharger** puis redémarrez Home Assistant.

### Configuration

1.  Allez dans **Paramètres** > **Appareils et services**.
2.  Ajoutez l'intégration **Iléo Water Direct**.
3.  Entrez vos identifiants Iléo.

---

## 📊 Les Capteurs Disponibles

L'intégration crée désormais 4 entités distinctes pour séparer l'affichage visuel des calculs statistiques.

### 1. Pour votre Tableau de Bord (Cartes Lovelace)
Utilisez ces capteurs pour afficher les infos "Tuiles" sur votre accueil. Ils ne sont pas destinés au Dashboard Énergie.
* **`sensor.ileo_affichage_index`** : Affiche le dernier index connu.
* **`sensor.ileo_affichage_conso`** : Affiche le volume du dernier relevé.

### 2. Pour le Dashboard Énergie (Choisissez UNE seule option)
Iléo transmet les données avec ~2 jours de retard. Vous avez deux philosophies possibles :

#### Option A : La "Vérité Historique" (Recommandé pour les puristes) 👻
* **Capteur à choisir :** `sensor.ileo_source_mode_differe` (Mode Fantôme)
* **Fonctionnement :** Ce capteur reste à 0 toute la journée. Il n'enregistre rien "en direct".
* **Magie :** En arrière-plan, il injecte la consommation reçue directement à la date réelle du passé (ex: le 17).
* **Résultat :**
    * Votre graphique d'aujourd'hui sera vide (c'est normal, on ne connait pas encore la conso !).
    * Le graphique d'il y a 2 jours sera mis à jour avec la valeur exacte.
    * **Avantage :** Graphique temporellement parfait.

#### Option B : Le "Suivi Direct" (Recommandé pour le suivi budget) ⚡
* **Capteur à choisir :** `sensor.ileo_source_mode_direct`
* **Fonctionnement :** Dès qu'Iléo envoie une donnée (le 19), ce capteur se met à jour.
* **Résultat :**
    * Une barre de consommation apparaît sur la journée d'aujourd'hui (le 19).
    * **Avantage :** Vous voyez l'activité immédiatement.
    * **Inconvénient :** La date est techniquement fausse (c'est la conso du 17 affichée le 19), mais le total mensuel est correct.

---

## 🛠 Dépannage & Premier Lancement

### Le "Bug" du Premier Jour (Pic Négatif)
Lors de l'installation, Home Assistant peut générer une consommation négative énorme. C'est normal : il essaie de compenser le passage de "0" à "Votre Index actuel".

**Comment corriger (à faire une seule fois) :**
1.  Allez dans **Outils de développement** > Onglet **Statistiques**.
2.  Cherchez votre capteur source (ex: `ileo_source_mode_differe`).
3.  Cliquez sur l'icône **Corriger** (la petite rampe à droite).
4.  Repérez la ligne avec une valeur énorme ou négative à la date d'installation.
5.  Changez la valeur à **0** (ou supprimez la ligne).

### Les capteurs sont "Unknown"
Si vous venez de changer de version, redémarrez Home Assistant complètement. Attendez quelques minutes que la connexion à Iléo se fasse. Si le problème persiste, vérifiez les journaux (Logs).
