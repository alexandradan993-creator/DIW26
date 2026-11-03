# Données géographiques autour de Pully

## Terrain et pente disponibles

- `terrain/altitude_2m.tif` : mosaïque du terrain nu swissALTI3D, altitude en mètres.
- `terrain/pente_degres_2m.tif` : pente calculée en degrés, de 0° à moins de 90°.
- `terrain/catalogue_selection.json` : métadonnées et URL des 48 tuiles sources,
  avec leurs empreintes officielles SHA-256 (multihash).
- `terrain/provenance.json` : emprise, millésimes, méthode, versions et empreintes
  des fichiers produits.
- `terrain/collection.json` : métadonnées officielles de la collection.

Source : **swissALTI3D © swisstopo**, téléchargée le 3 novembre 2026 depuis
https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d.
Les tuiles retenues sont les dernières disponibles par carré dans la sélection,
aux millésimes 2019 ou 2021 ; la date de téléchargement n'est pas celle des mesures.

Résolution : 2 m. Coordonnées horizontales : MN95 / EPSG:2056 ; altitudes LN02
(EPSG:5728). Le rectangle de travail est [2538000, 1149000, 2544000, 1157000]
en MN95, soit 6 × 8 km. Il inclut des secteurs voisins et du lac.
Ce n'est pas un découpage aux limites communales. Sans les géométries des
2 672 parcelles, leur couverture exhaustive ne peut pas être certifiée.

La pente utilise les différences centrées des altitudes sur la mosaïque :
`atan(sqrt((dz/dx)^2 + (dz/dy)^2))`, converti en degrés. Le pourcentage serait
`100 * tan(angle)` ; les valeurs du fichier ne sont pas des pourcentages.
Le bord externe et les voisinages NoData sont masqués (`-9999`). Les différences
de millésimes et de précision peuvent créer des artefacts, notamment aux raccords.
Une pente à 2 m reste un indicateur exploratoire, pas une étude géotechnique.

Les GeoTIFF s'ouvrent dans QGIS. Le pipeline de prospection n'utilise pas encore
ces rasters : aucun seuil, statut ni résultat de présélection n'est modifié.

Pour reproduire les rasters depuis la racine du dépôt, dans un environnement
Python séparé du pipeline (accès HTTPS à `data.geo.admin.ch` nécessaire) :

```bash
python -m venv .venv-geo
# Linux/macOS : source .venv-geo/bin/activate
# Windows PowerShell : .venv-geo\Scripts\Activate.ps1
python -m pip install -r scripts/requirements-geo.txt
python scripts/preparer_terrain.py
```

Les sources sont téléchargées dans un dossier temporaire, contrôlées par SHA-256,
puis assemblées. Le script remplace les deux rasters locaux ; leurs empreintes
de publication sont conservées dans `provenance.json`. La compression peut varier
avec les versions de GDAL : comparer aussi les pixels et les géoréférencements.

## ISOS : références récupérées, périmètres non déterminés

Source : **© OFC, Berne**, inventaire fédéral courant téléchargé via
https://data.geo.admin.ch/api/stac/v0.9/collections/ch.bak.bundesinventar-schuetzenswerte-ortsbilder.
Le fichier national INTERLIS `ISOS_V2_20260915.xtf` ne contient pas d'entrée
nommée Pully. Les références voisines Lausanne (4397), Lutry (4461), Châtelard
(4452) et Savuit (4469) sont documentées dans :

- `isos/sites_voisins.geojson` : **points de localisation**, en WGS84 ;
- `isos/extrait_sites_voisins.xml` : extrait des quatre fiches sources, MN95 ;
- `isos/etat_couverture.json` : provenance, empreinte de l'archive, liens PDF
  et état explicitement incomplet ;
- `isos/collection.json` : métadonnées et conditions d'utilisation indiquées
  par le fournisseur.

Les anciens relevés ISOS I sont uniquement disponibles en PDF selon le catalogue.
Seuls les PDF font foi ; les géodonnées ont un caractère informatif. Les points
ne permettent aucune intersection parcellaire et ne prouvent pas l'absence de
protection à Pully. Les plans, objectifs de sauvegarde, éventuels périmètres
voisins et inventaires cantonaux restent à examiner. Le téléchargement des PDF
depuis `api.isos.bak.admin.ch` a été refusé par le proxy réseau (403).

La collection ISOS indique `proprietary` et renvoie aux conditions
https://opendata.swiss/en/terms-of-use/#terms_by_ask. Ne pas assimiler ces données
à une licence ouverte ; les conditions de réutilisation, en particulier
commerciale, restent à clarifier auprès de l'OFC. Les métadonnées de collection
swissALTI3D sont également conservées sans réécrire leur champ de licence ;
consulter les conditions actuelles de swisstopo pour toute redistribution ou
réutilisation. Les mentions de source sont conservées dans les fichiers.
