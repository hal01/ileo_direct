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
5. **Coût de l'eau (facultatif)** : renseignez le **prix de l'eau en €/m³** et/ou une **entité de prix** (`input_number` ou capteur en €/m³). L'entité est prioritaire ; le prix fixe sert de repli si elle est indisponible. Avec un prix à 0 et sans entité, aucun coût n'est calculé. Ces réglages sont modifiables à tout moment via le bouton **Configurer**.

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
   * **Coûts** : si un prix est configuré, choisissez *« Utiliser une entité qui suit le coût total »* et sélectionnez la statistique **`Ileo Index Mode Ghost coût`** (`ileo_direct:ileo_index_mode_ghost_cout`). Le coût est calculé à chaque injection (volume × prix en vigueur à ce moment) et placé à la même date que la consommation.
4. **Méthode Alternative** : Utilisez `Ileo Compteur Eau (Index)`. La consommation sera alors enregistrée au moment de la synchronisation (souvent avec 2 jours de décalage). Ainsi, la consommation du Lundi etant récupérée le Mercredi, elle apparaitra le Mercredi.
5. Le premier relevé injecté n'est plus compté comme une consommation égale à l'index : la somme statistique part de 0. Pour une installation existante qui présente encore ce pic, il suffit de le corriger une fois dans **Outils de développement** > **Statistiques** (icône « Ajuster ») ; les injections suivantes restent continues.

En synthèse pour le choix du capteur du tableau énergie : 
   * Si la priorité c'est la consommation positionnée a la bonne date et avec un historique (et les coûts si un prix est configuré) ==> **`Ileo Index Mode Ghost`**.
   * Si la priorité c'est une conso globale sur une periode, enregistrée au jour de la synchronisation ==> **`Ileo Compteur Eau (Index)`**.

## 💡 Astuces Utiles

### Création de compteurs périodiques (Utility Meter)
Le capteur `Ileo Compteur Eau (Index)` étant de type `total_increasing`, il est parfait pour créer des compteurs mensuels ou annuels :
1. Allez dans **Paramètres** > **Appareils et services** > **Entrées**.
2. Cliquez sur **Créer une entrée** > **Compteur de services publics**.
3. Sélectionnez `sensor.ileo_compteur_eau_index` comme capteur d'entrée.
4. Définissez la période (Mensuelle, Hebdomadaire, etc.).

### Gestion de la base de données
Le capteur **Ghost** interroge systématiquement votre historique en base de données avant chaque mise à jour. Il n'injecte que les données "nouvelles" pour éviter les doublons, et poursuit la somme statistique à partir de la dernière valeur enregistrée (cumul des écarts d'index), ce qui évite tout pic dans le tableau Énergie.

Le coût, lui, est figé au prix en vigueur lors de l'injection : un changement de prix ne s'applique qu'aux relevés suivants, et activer un prix ne recalcule pas l'historique déjà importé.

---
