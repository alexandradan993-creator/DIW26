# Contours parcellaires de Pully

Extraction du 3 novembre 2026 depuis **CadastralWebMap — Mensuration Officielle
Suisse, cantons**, couche `ch.kantone.cadastralwebmap-farbe`, API fédérale :
https://api3.geo.admin.ch/rest/services/api/MapServer/ch.kantone.cadastralwebmap-farbe.

La fiche officielle du service indique un état d'actualité au **2 novembre 2026**.
Elle précise qu'il s'agit d'un service de représentation dont le contenu est
réduit par rapport aux données complètes de la mensuration officielle.
Ces contours servent aux analyses exploratoires et ne remplacent pas un extrait
officiel, une vérification foncière ou la géométrie complète de la MO.
La documentation du service ne constitue pas une licence de réutilisation :
consulter les conditions des fournisseurs avant toute réutilisation commerciale.

## Résultat des contrôles

| Contrôle | Résultat |
|---|---:|
| EGRID attendus dans le CSV | 2 672 |
| EGRID retrouvés exactement dans le service | 2 672 |
| Objet unique par EGRID | 2 672 |
| Géométries valides exportées en GeoJSON | 2 653 |
| Géométries invalides conservées uniquement dans la source et l'audit | 19 |
| Numéros divergents parmi les contours valides | 0 |
| Contours valides dont l'écart de surface dépasse 1 % du CSV | 61 |

Les 19 géométries invalides concernent 14 domaines publics communaux et 5
parcelles privées : **7393, 7097, 2211, 1114 et 445**. Elles ont notamment des
auto-intersections. Elles ne sont pas réparées automatiquement et ne figurent
pas dans `contours.geojson`.

Les 61 écarts supérieurs à 1 % doivent être examinés avant d'utiliser la surface
du contour pour un calcul de potentiel. Le plus important concerne la parcelle
**390** : environ 29 820,77 m² dans le CSV contre 25 022,83 m² dans le service
(-16,09 %). Une recherche exacte par EGRID donne le même contour que l'extraction
spatiale : l'écart ne provient pas du découpage des requêtes. La cause reste à
établir auprès de la source ; aucune correction du CSV n'a été appliquée.
Le seuil de 1 % est un seuil technique de contrôle, pas une règle réglementaire.

La parcelle **607** est appariée exactement : 1 954,48 m² pour le contour contre
1 955,17 m² dans le CSV, soit environ -0,036 %. Le traitement des logements et
les règles de prospection restent inchangés.

Parmi les 2 653 contours valides, **seul DP 5590** déborde du rectangle des
rasters terrain actuels. Il faudra signaler cette couverture partielle lors de
l'extraction des pentes. Ce contrôle porte sur l'emprise rectangulaire des rasters,
pas sur la présence de pixels valides à l'intérieur de chaque parcelle.

## Fichiers

- `contours.geojson` : Polygon/MultiPolygon valides, coordonnées WGS84
  (longitude, latitude), EGRID, numéro source et service, surfaces et écarts.
  Compatible avec QGIS et les cartes web ; les surfaces sont calculées en MN95.
- `source_esri_lv95.json` : réponse source pour les 2 672 objets retenus, anneaux
  ESRI en **MN95 / EPSG:2056**, y compris les géométries invalides.
- `audit_correspondances.json` : une entrée par EGRID, avec résultat du contrôle,
  surfaces, écart relatif (fraction, pas pourcentage) et emprise MN95.
- `resume.json` : résumé de l'extraction et listes des anomalies.
  Le champ `non_apparies` inclut ici les EGRID retrouvés mais non exportés pour
  défaut géométrique ; il ne signifie pas que ces EGRID sont absents du service.
- `schema_service.json` et `metadata_service.html` : schéma et documentation
  officiels consultés lors de l'extraction.
- `provenance.json` : empreintes des fichiers et contrôles complémentaires.

## Reproduire l'extraction

Depuis la racine du dépôt, avec Python et un environnement virtuel actif :

```bash
python -m pip install -r scripts/requirements-parcelles.txt
python scripts/recuperer_parcelles.py
```

Accès HTTPS à `api3.geo.admin.ch` nécessaire. Le script utilise quatre requêtes
concurrentes au maximum. Toute réponse contenant 200 objets est considérée comme
potentiellement tronquée et son rectangle est subdivisé. Les EGRID manquants
sont recherchés exactement, sans rapprochement approximatif par numéro.
La source étant vivante, une nouvelle exécution peut produire des différences.

Les anneaux sources sont assemblés en préservant trous et parties disjointes,
puis validés avant conversion en WGS84. Une géométrie invalide reste signalée.
L'extraction ne calcule pas encore les pentes par parcelle, les reculs ou le
potentiel et ne change aucun statut du pipeline.
