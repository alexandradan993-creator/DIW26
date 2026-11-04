# DIW26 — filtre 3 couleurs avec alerte de voisinage forestier

## Objet

Ce correctif remplace **uniquement** `code/criteres_category.py`. Il conserve les champs détaillés d'origine : domaine cadastral, DP communal/cantonal, emprise bâtie (m² et %), surfaces vertes/dures, intersections forêt/eaux (Oui/Non, m², %), pente, critères explicatifs et trois couleurs.

**Règle forestière ajoutée :** une parcelle passe de `vert` à `jaune` si elle touche, ou se trouve à **1 m maximum**, d'une **autre parcelle dont le CSV signale une intersection positive avec la forêt**. Les exclusions existantes `rouge` gardent la priorité. Les parcelles intersectant elles-mêmes la forêt restaient déjà jaunes (sauf rouge).

**ATTENTION :** il s'agit d'un **indice de voisinage d'une parcelle contenant de la forêt**, pas d'une preuve que la forêt borde elle-même la parcelle. Les contours cadastraux ne donnent PAS les limites des surfaces forestières à l'intérieur de chaque parcelle. `distance_parcelle_forestiere_m` est la distance **entre deux parcelles cadastrales**, jamais la distance à la lisière. Le vrai champ `distance_lisiere_foret_m` reste vide en l'absence de géométrie de la forêt. `bordure_foret_confirmee` reste inconnu.

## Où copier les fichiers

Depuis cette archive, mettre les fichiers dans le dépôt `DIW26` :

- `code/criteres_category.py` → remplacer l'ancien fichier.
- `code/criteres.json` → comparer avec le fichier courant (seuil validé 600 m² et emprise 20 %).
- `tests/test_csv_indicators.py` et `tests/test_forest_neighbor.py` → tests.
- `data/parcelles_3_couleurs_voisinage_foret.csv` → sortie calculée utilisable par le frontend.

**Ne pas remplacer** `code/classification.py`.

Le script exploite le fichier **déjà présent dans votre dépôt** `data/parcelles/contours.geojson` (2 653 contours issus du fichier transmis), ainsi que `pully_parcelles.csv` et `data/pentes_parcelles/pentes_parcelles.csv`.

## Installer les dépendances géographiques

```powershell
python -m pip install "shapely>=2" "pyproj>=3"
```

Sans le GeoJSON `data/parcelles/contours.geojson`, les intersections de forêt continuent de produire l'alerte jaune, mais le voisinage ne peut pas être calculé. La commande s'exécute tout de même sans voisinage.

## Recalculer toutes les parcelles

Depuis la racine de DIW26 :

```powershell
python code/criteres_category.py --input pully_parcelles.csv --config code/criteres.json --pentes data/pentes_parcelles/pentes_parcelles.csv --contours data/parcelles/contours.geojson --tolerance-voisin-m 1 --output data/parcelles_3_couleurs_voisinage_foret.csv
```

Tester :

```powershell
python -m unittest discover -s tests -p "test_*forest_neighbor.py" -v
python -m unittest discover -s tests -p "test_csv_indicators.py" -v
```

## Résultats vérifiés sur les données fournies

- 2 672 parcelles : **1 938 rouges, 488 jaunes, 246 vertes**.
- Par rapport à l'ancienne règle « intersection forêt uniquement » : **20 vertes → jaunes** par voisinage cadastral.
- **150** parcelles avec intersection forestière CSV positive.
- **244** parcelles identifiées comme voisines d'une parcelle intersectant la forêt (parmi toutes les couleurs, pas toutes nouvellement jaunes).
- **18** parcelles sans contour correspondant : voisinage non vérifiable.

## Colonnes à afficher sur le site

- `statut_filtrage_criteres` : `rouge` / `jaune` / `vert`.
- `domaine_cadastral`, `domaine_public_communal`, `domaine_public_cantonal`.
- `emprise_batie_m2`, `emprise_batie_pct`, `surface_m2`.
- `intersection_foret`, `surface_intersection_foret_m2`, `part_intersection_foret_pct`.
- `voisine_parcelle_avec_foret` : `Oui`, `Non détectée`, `Sans objet`, ou `Inconnu`.
- `distance_parcelle_forestiere_m`, `egrid_voisin_forestier` : **distance à la PARCELLE voisine identifiée**, pas à la forêt.
- `bordure_foret_confirmee` : inconnu sans couche forestière.
- `intersection_eaux`, `surface_intersection_eaux_m2`, `part_intersection_eaux_pct`.
- `filtres`, `alertes`, `filtres_echoues` : explication de classification.

Pour colorer la carte, le frontend doit lire `statut_filtrage_criteres` dans ce CSV et joindre par **`egrid`** aux polygones. L'ancienne logique à quatre couleurs de `services/interactive_filter_service.py` ne se mettra pas à jour seule.

## Git

```powershell
git add code/criteres_category.py code/criteres.json tests/test_csv_indicators.py tests/test_forest_neighbor.py data/parcelles_3_couleurs_voisinage_foret.csv
git commit -m "Add cautious forest-neighbor warnings to three-color screening"
git push
```

Ce code ne déclare **ni une distance légale à la forêt**, ni un droit de construire, ni la propriété juridique d'un terrain.
