# 💧 Iléo Water Direct pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![version](https://img.shields.io/github/v/release/hal01/ileo_direct)](https://github.com/hal01/ileo_direct/releases)


# Iléo Direct (MÉL) pour Home Assistant 🌊

Cette intégration personnalisée permet de récupérer vos données de consommation d'eau depuis le portail **Iléo** (Métropole Européenne de Lille) et de les intégrer nativement dans Home Assistant. Elle gère intelligemment le décalage de publication des données pour offrir un suivi historique précis ou au choix un index de compteur a intégrer au jour le jour.

## 🚀 Installation

### Option 1 : Via HACS (Recommandé)
1. Assurez-vous que [HACS](https://hacs.xyz/) est installé.
2. Allez dans **HACS** > **Intégrations**.
3. Cliquez sur les **trois points** en haut à droite et choisissez **Dépôts personnalisés**.
4. Copiez l'URL suivante : `https://github.com/hal01/ileo_direct`.
5. Sélectionnez la catégorie **Intégration** et cliquez sur **Ajouter**.
6. Cherchez **Iléo Direct** dans la liste, cliquez sur **Télécharger**, puis redémarrez Home Assistant.

### Option 2 : Installation Manuelle
1. Téléchargez le dossier `ileo_direct` depuis ce dépôt.
2. Copiez-le dans le répertoire `custom_components/` de votre instance Home Assistant.
3. Redémarrez Home Assistant.

---

## ⚙️ Configuration

1. Allez dans **Paramètres** > **Appareils et services** > **Ajouter une intégration**.
2. Recherchez **Iléo**.
3. Saisissez vos identifiants (Email et Mot de passe).
4. **Option Historique** : Lors de la première installation ou via le bouton "Modifier les identifiants", vous pouvez cocher la case **"Réécrire l'historique du Dashboard Énergie"**.
   * **Cochée** : Importe les 6 derniers mois de données (recommandé pour une première installation).
   * **Décochée** : Initialise le compteur à sa valeur actuelle sans importer le passé.

---

## 📊 Capteurs créés

L'intégration génère trois capteurs pour répondre à tous vos besoins :

| Nom de l'entité | ID de l'entité | État visible | Usage |
| :--- | :--- | :--- | :--- |
| **Ileo Compteur Eau (Index)** | `sensor.ileo_compteur_eau_index` | ✅ Litres | Suivi de l'index réel et création de compteurs périodiques. |
| **Ileo Consommation Eau (journalière)** | `sensor.ileo_consommation_eau_journaliere` | ✅ Litres | Affichage de la consommation du dernier relevé connu. |
| **Ileo Index Mode Ghost** | `sensor.ileo_index_mode_ghost` | ❌ Unknown | **Exclusif au Tableau de bord Énergie.** |

### Focus sur le Mode Ghost (valeurs uniquement visibles dans les statistiques long terme) 👻
Ce capteur est un "injecteur statistique pur". Son état court terme reste délibérément `Unknown` pour ne pas polluer votre base de données courante. Il travaille en arrière-plan pour injecter vos index directement dans la table des **statistiques à long terme** à la date exacte de consommation trouvée sur Iléo.

---

## ⚡ Configuration du Tableau de Bord Énergie

Pour un suivi précis, configurez votre consommation d'eau comme suit :

1. Allez dans **Paramètres** > **Tableaux de bord** > **Énergie**.
2. Dans la section **Consommation d'eau**, ajoutez une source.
3. **Méthode Recommandée** : Choisissez le capteur **`Ileo Index Mode Ghost`**.
   * Grâce à l'injection statistique, vos 200L consommés le lundi apparaîtront sur la colonne du lundi, même si Iléo ne publie l'info que le mercredi.
4. **Méthode Alternative** : Utilisez `Ileo Compteur Eau (Index)`. La consommation sera alors enregistrée au moment de la synchronisation (souvent avec 2 jours de décalage).
5. Après la mise a jour, il est recommandé d'utiliser l'outil statistiques présent dans le menu "outils de développement" pour corriger les valeurs abérantes ; c'est a dire souvent la première valeur intégrée qui donne une consommation en litre égale à l'index, alors que les suivantes sont basées sur une différence d'index.
6. Dans le cas d'ajout des couts, il faudra attendre au moins 2 jours pour voir des couts arriver.
---

## 💡 Astuces Utiles

### Création de compteurs périodiques (Utility Meter)
Le capteur `Ileo Compteur Eau (Index)` étant de type `total_increasing`, il est parfait pour créer des compteurs mensuels ou annuels :
1. Allez dans **Paramètres** > **Appareils et services** > **Entrées**.
2. Cliquez sur **Créer une entrée** > **Compteur de services publics**.
3. Sélectionnez `sensor.ileo_compteur_eau_index` comme capteur d'entrée.
4. Définissez la période (Mensuelle, Hebdomadaire, etc.).

### Gestion de la base de données
Le capteur **Ghost** interroge systématiquement votre historique en base de données avant chaque mise à jour. Il n'injecte que les données "nouvelles" pour éviter les doublons ou les pics erronés, tout en forçant la valeur de la somme égale à l'index pour une cohérence parfaite dans le tableau Énergie.

---
