# Premier pipeline Python de prospection à Pully

Python 3.10 ou ultérieur. Le programme fonctionne hors ligne avec la bibliothèque standard.

## Lancer

Depuis le dossier `code`, avec le fichier principal déjà extrait dans le dossier parent.

```bash
python prospection.py --input ../pully_parcelles.csv --output resultats --config criteres.json
```

Si vous décompressez le prototype ailleurs, remplacez `../pully_parcelles.csv` par le chemin du CSV principal de 2 672 parcelles. Les CSV de l’échantillon de 15 parcelles ont un autre schéma. Utiliser le CSV principal fourni dans l’archive de données.

## Fichiers produits

| Fichier | Contenu |
|---|---|
| `audit_parcelles.csv` | Toutes les parcelles, leur statut, les raisons et les contrôles restants |
| `exclusions_patrimoine.csv` | Au moins une note de 1 à 3 sur un bâtiment, un objet ou un site, même provisoire |
| `anomalies_a_verifier.csv` | Notes inconnues, JSON incomplet, incohérences de surfaces ou de rattachement RCB, couverture de zone incertaine |
| `hors_cible_exploratoire.csv` | Données contrôlables mais seuils exploratoires non satisfaits |
| `candidates_a_approfondir.csv` | Parcelles satisfaisant les filtres sur les données fournies |
| `resume.json` | Effectifs, seuils appliqués et empreinte du fichier source |

Les explications et preuves sont stockées dans des colonnes JSON. Exemple de lecture en Python.

```python
import csv
import json

with open("resultats/candidates_a_approfondir.csv", encoding="utf-8-sig", newline="") as stream:
    for row in csv.DictReader(stream):
        print(row["numero_parcelle"], json.loads(row["motifs_json"]))
```

## Ordre des décisions

1. Exclusion patrimoniale dès qu’une note 1, 2 ou 3 est détectée. Une note provisoire 4 ne remplace aucune autre note. Les notes des sites et des objets ponctuels sont contrôlées lorsqu’elles figurent dans le fichier.
2. Mise en vérification lorsqu’une donnée nécessaire est incertaine. Une note 0, une note illisible et un statut RCB divergent déclenchent cette étape. Une absence de note dans les couches reste visible dans la sortie et appelle une confirmation officielle.
3. Application des seuils exploratoires du fichier `criteres.json`.
4. Présélection des candidates, ordonnée par emprise croissante puis superficie décroissante. Cet ordre repose sur les deux indicateurs disponibles. Aucun score appris n’est calculé.

## Seuils choisis pour cette première version

| Paramètre | Valeur initiale | Sens |
|---|---|---|
| `surface_min_m2` | 1000 | Superficie géométrique minimale |
| `emprise_max` | 0.20 | Emprise cadastrale / superficie géométrique maximale |
| `logements_max` | 3 | Nombre maximal de logements renseignés selon le rattachement parcellaire déclaré au RCB |

Ces seuils expriment une première cible de prospection et sont modifiables. Le maximum de trois logements reprend la cible d’habitat individuel ou de petite taille évoquée dans le projet. Les dépendances sans logement sont conservées dans les données de bâti. Une parcelle dépourvue de logement renseigné reste hors de cette cible.

Le taux d’emprise calculé utilise les contours cadastraux. Les règles de calcul du RCATC, les exceptions et les plans spéciaux doivent être examinés séparément avant toute comparaison réglementaire.

Le code reprend également un seuil de contrôle géographique de 99 % pour la couverture de la zone dominante. Ce seuil technique sert à isoler les parcelles dont l’affectation demande un contrôle plus précis. Il ne résout pas les contacts minimes entre plans ni les divergences entre SIGIP et RDPPF.

## Contrôles de qualité

Les EGRID doivent être présents et uniques. Les quatre groupes de notes, bâtiments et sites, existants et provisoires, doivent figurer dans le schéma. Les listes JSON manquantes ou illisibles sont signalées. Les booléens du CSV sont lus explicitement pour traiter correctement la chaîne `False`.

Le nombre de logements est recalculé depuis les objets RCB en vérifiant leur parcelle déclarée et les EGID. Un bâtiment déclaré sur une parcelle voisine déclenche une vérification et ses logements sont écartés du total recalculé. Cette règle traite le cas observé sur la parcelle 607. L’implantation cadastrale et les adresses restent à contrôler dans un tel cas.

Les valeurs manquantes restent distinctes de zéro. Les fichiers de sortie sont préparés dans un dossier temporaire avant remplacement. Le résumé d’exécution est publié en dernier. Exécuter un seul processus par dossier de sortie.

## Critères restant à intégrer

Chaque parcelle conserve une liste de vérifications, avec ISOS, pente, accès, distances, hauteur, plans spéciaux, pleine terre, sous-sol, arbres, contraintes environnementales et avis de Conti. Le programme décrit les observations de la base extraite le 2 novembre 2026. La collecte en direct et la validation réglementaire détaillée feront l’objet d’étapes suivantes.

Les données historiques de permis et les décisions finales de Conti restent à obtenir. Les statuts du programme sont des résultats de règles exploratoires. Conserver les annotations humaines dans des champs distincts pour constituer les futures données d’entraînement. Les champs `decision_conti` et `motif_conti` du fichier source sont reportés sans être remplis automatiquement.

## Vérifier les régressions

```bash
python -m unittest discover -s . -p "test_*.py" -v
```

Les tests couvrent notamment les notes provisoires 3, les notes des sites, le cas 3 existant / 4 provisoire, les booléens CSV, les notes invalides et les rattachements de bâtiments voisins.
