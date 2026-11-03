# Prospection immobilière à Pully

**Nouvelle version :** [classification configurable à partir de 600 m²](code/CLASSIFICATION.md).
Elle distingue filtres connus, simulations COS et informations à vérifier,
sans score ni critère énergétique. Le pipeline historique ci-dessous reste disponible.

Les [pentes par parcelle](data/pentes_parcelles/README.md) sont calculées séparément,
avec les alertes de qualité ; elles ne modifient pas encore la présélection.

Voir [les critères de prospection](CRITERES_PROSPECTION.md) pour la synthèse de
l'entretien avec l'expert, les exclusions souhaitées et les points à confirmer.

Les données de terrain et la couche de pente à 2 m sont dans
[`data/`](data/README.md), avec leur provenance et les références ISOS disponibles.
Elles ne sont pas encore utilisées par le pipeline de présélection.

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
python code/prospection.py --input pully_parcelles.csv --output code/resultats --config code/criteres.json
```

Sur un système où Python s'appelle `python3`, remplacer `python` par `python3`.
Exécuter un seul pipeline à la fois par dossier de sortie.

## PyCharm

Ouvrir le dossier `DIW26` comme projet et sélectionner un interpréteur Python
3.10 ou ultérieur (un environnement virtuel local est facultatif).
Dans une configuration **Python**, renseigner :

- Script : `$PROJECT_DIR$/code/prospection.py`
- Paramètres : `--input pully_parcelles.csv --output code/resultats --config code/criteres.json`
- Répertoire de travail : `$PROJECT_DIR$`

La commande précédente fonctionne aussi dans le terminal PyCharm ouvert à la racine.

## Tests et résultats

Depuis la racine :

```bash
python -m unittest discover -s code -p "test_*.py" -v
```

Ouvrir dans `code/resultats/` :

- `resume.json` : effectifs, seuils et empreinte SHA-256 de la source ;
- `audit_parcelles.csv` : toutes les parcelles, notamment la parcelle 607 ;
- `candidates_a_approfondir.csv` : candidates et explications ;
- `anomalies_a_verifier.csv` : dossiers nécessitant une clarification ;
- `exclusions_patrimoine.csv` : exclusions patrimoniales ;
- `hors_cible_exploratoire.csv` : parcelles hors des seuils actuels.

Les colonnes terminées par `_json` contiennent des listes de preuves, motifs ou
vérifications. Les seuils exploratoires restent dans `code/criteres.json` :
1 000 m² minimum, 20 % d'emprise cadastrale maximum et trois logements maximum.
Une note patrimoniale 1, 2 ou 3, même provisoire, reste prioritaire.

Voir [la documentation du prototype](code/README.md) pour les règles
et limites détaillées. La revue documentaire des 15 parcelles n'est pas une
validation commerciale de Conti. Les statuts calculés ne sont pas des labels
d'entraînement ; les décisions humaines restent distinctes.

ISOS, pente, accès, enveloppe après retraits et règles des plans spéciaux restent
à intégrer. L'emprise cadastrale ne remplace pas l'emprise réglementaire.
