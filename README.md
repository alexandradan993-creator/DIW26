# Prospection immobilière à Pully

Voir [les deux pourcentages et la forme](code/FORME_ET_POURCENTAGES.md) pour la
marge COS et la part du terrain après retrait simulé de 6 m.

**Seuil actuel validé avec l'expert : 600 m² minimum, borne incluse.**
La [classification configurable](code/CLASSIFICATION.md) utilise `code/filtres.json`.
Elle distingue filtres connus, simulations COS et informations à vérifier,
sans score ni critère énergétique. Les 1 000 m² de l'ancien prototype sont
uniquement historiques et ne sont pas le seuil de cette classification.

Les [pentes par parcelle](data/pentes_parcelles/README.md) sont calculées séparément,
avec les alertes de qualité ; elles ne modifient pas encore la présélection.

Voir [les critères de prospection](CRITERES_PROSPECTION.md) pour la synthèse de
l'entretien avec l'expert, les exclusions souhaitées et les points à confirmer.

Les données de terrain et la couche de pente à 2 m sont dans
[`data/`](data/README.md), avec leur provenance et les références ISOS disponibles.
Les statistiques de pente sont jointes à titre descriptif ; elles ne filtrent pas.

Prototype Python de présélection explicable de parcelles, importé depuis
`prototype_pully_python.zip`. Python 3.10 ou ultérieur suffit ; aucune dépendance
externe ni connexion réseau n'est nécessaire.

L'outil repère des dossiers à approfondir et expose leurs signaux et vérifications
restantes. Il ne certifie pas la constructibilité et n'estime pas la valeur.

## Relancer depuis la racine du dépôt

Le CSV complet de 2 672 parcelles est inclus dans le dépôt : `pully_parcelles.csv`.
Les résultats générés restent locaux et ignorés par Git.
Les sorties fournies dans l'archive servent de référence,
les sorties locales ci-dessous sont recalculées par le script.

```bash
python code/classification.py --input pully_parcelles.csv --config code/filtres.json --pentes data/pentes_parcelles/pentes_parcelles.csv --formes data/formes_parcelles/formes_parcelles.csv --output code/resultats_classification
```

Sur un système où Python s'appelle `python3`, remplacer `python` par `python3`.
Exécuter un seul pipeline à la fois par dossier de sortie.

## PyCharm

Ouvrir le dossier `DIW26` comme projet et sélectionner un interpréteur Python
3.10 ou ultérieur (un environnement virtuel local est facultatif).
Dans une configuration **Python**, renseigner :

- Script : `$PROJECT_DIR$/code/classification.py`
- Paramètres : `--input pully_parcelles.csv --config code/filtres.json --pentes data/pentes_parcelles/pentes_parcelles.csv --formes data/formes_parcelles/formes_parcelles.csv --output code/resultats_classification`
- Répertoire de travail : `$PROJECT_DIR$`

La commande précédente fonctionne aussi dans le terminal PyCharm ouvert à la racine.

## Tests et résultats

Depuis la racine :

```bash
python -m unittest discover -s code -p "test_*.py" -v
```

Ouvrir dans `code/resultats_classification/` :

- `resume.json` : effectifs, seuils et empreinte SHA-256 de la source ;
- `classification.csv` : toutes les parcelles avec statuts, motifs et inconnues ;
- `retenues_a_examiner.csv` : celles qui satisfont les filtres connus activés,
  sans potentiel constructible établi.

Les colonnes terminées par `_json` contiennent des listes de preuves, motifs ou
vérifications. La configuration actuelle est `code/filtres.json` : **600 m² inclus**
et exclusion patrimoniale 1, 2 ou 3, même provisoire. Le COS et le retrait de 6 m
restent des simulations à confirmer ; aucun score global n'est appliqué.

## Prototype historique à 1 000 m² — référence uniquement

`code/prospection.py` et `code/criteres.json` conservent l'ancienne configuration
(1 000 m², 20 % d'emprise, trois logements). Ces seuils ne s'appliquent pas à la
classification actuelle. Pour reproduire exclusivement cette référence :

```bash
python code/prospection.py --input pully_parcelles.csv --output code/resultats --config code/criteres.json
```

Voir [la documentation du prototype](code/README.md) pour les règles
et limites détaillées. La revue documentaire des 15 parcelles n'est pas une
validation commerciale de Conti. Les statuts calculés ne sont pas des labels
d'entraînement ; les décisions humaines restent distinctes.

ISOS, propriété communale, arbres, accès et réglementation détaillée restent à
compléter. Les pentes et enveloppes simulées sont déjà calculées séparément.
L'emprise cadastrale ne remplace pas l'emprise réglementaire.
