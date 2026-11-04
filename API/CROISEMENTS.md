# Export ISOS cantonal et dangers naturels par EGRID

Premier livrable : export distinct à examiner avant toute connexion à l'interface.
Il n'active pas une base, ne recalcule pas encore la classification et ne remplace
ni le CSV parcellaire ni les annotations de l'expert.

## Sources à valider

- [Couche 404 — périmètres cantonaux fondés sur l'ISOS](https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer/404)
- [Couche 422 — carte synthétique des dangers naturels](https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer/422)

Ces références sont fournies par l'utilisateur. Le 4 novembre 2026, l'accès aux
deux URL a été refusé par le proxy de l'environnement : les schémas, les noms des
champs métier et la couverture d'étude **n'ont pas encore été vérifiés en direct**.
Cela ne démontre pas un refus du fournisseur. Il faut autoriser
`www.ogc.vd.ch` dans les paramètres réseau, puis contrôler les métadonnées.
L'autorisation a été ajoutée au brouillon, pas appliquée par le code.

La couche 404 est à traiter comme la source cantonale indiquée, sans l'assimiler
automatiquement à l'inventaire fédéral, à ses objectifs ou à une interdiction.
La présence d'un polygone de danger n'est pas une preuve de caractère bloquant.

## Exécuter depuis la racine du dépôt

Shapely 2.x est requis (le même environnement géographique que les autres scripts
peut être utilisé). Le nouveau mode utilise les contours ESRI MN95 déjà présents :
pas de téléchargement complet GEO.vd/SIGIP nécessaire pour cette étape.

```bash
python -m pip install -r scripts/requirements-parcelles.txt
python API/actualiser_pully.py --diagnostic-croisements
```

Le diagnostic affiche les champs réels, domaines codés, dates d'édition et
attributions. Vérifier le champ de nom/identité du site et celui de classe de
danger ; **ne pas supposer leur nom**. Les options suivantes permettent de fournir
les noms exacts après cette vérification : `--champ-site-isos NOM_DU_CHAMP` et
`--champ-classe-danger NOM_DU_CHAMP`.

```bash
python API/actualiser_pully.py --croisements --reference pully_parcelles.csv --contours data/parcelles/source_esri_lv95.json --sortie API/versions
```

Cette commande sans mapping produit les surfaces et les attributs bruts mais
signale `champ_metier_a_identifier` pour les intersections. Pour le livrable
compréhensible par l'expert, relancer avec les deux champs vérifiés. Une valeur
de classe manquante reste signalée ; aucun degré de danger n'est inventé.

Le dossier d'export versionné contient :

- `croisements.csv` : une ligne par EGRID de la référence, y compris les parcelles
  sans contour ou avec géométrie invalide ;
- `isos_source.json` et `dangers_source.json` : métadonnées et entités brutes du
  lot téléchargé autour des contours valides ;
- `provenance.json` : version technique d'export, dates de vérification/collecte,
  empreintes des entrées et des sources, mapping, bilan et alertes.

La référence peut être une nouvelle base datée générée par `actualiser_pully.py`.
Il faut alors fournir les contours correspondant à cette même collecte. Les
contours anciens ne sont pas rafraîchis par le mode `--croisements` : un nouvel
EGRID sans contour reste dans l'export, à vérifier. Un écart de surface >1 % est
signalé ; la même surface ne prouve pas l'absence de modification du contour.

## Interpréter l'export

`isos_json` et `dangers_json` contiennent :

- `surface_union_m2` et `part_parcelle_pct`, sans double comptage des recouvrements ;
- les `objets` avec attributs bruts, valeur métier, surface et pourcentage ;
- les `classes`, avec codes, libellés issus du domaine codé s'il existe et union
  surfacique par classe ;
- le statut de couverture et, lorsqu'il est documenté, son pourcentage.

Des classes différentes peuvent se chevaucher : leurs pourcentages ne sont pas
nécessairement additionnables. Le pourcentage global est celui de leur union.
Un simple contact de bord sans surface ne crée pas une intersection positive.
Le dénominateur est l'aire du contour, calculée en MN95, pas la surface RF.

| Situation | ISOS | Dangers |
|---|---|---|
| Intersection positive | `dans_perimetre` | `danger_identifie` |
| Aucune intersection, couverture d'étude complète attestée | `hors_perimetres_consultes` | `aucun_danger_identifie_dans_donnees_consultees` |
| Couverture inconnue, partielle ou extérieure, sans intersection | `a_verifier` | `a_verifier` |
| Contour absent/invalide | `a_verifier`, mesures inconnues | `a_verifier`, mesures inconnues |

Même en cas d'intersection positive, une couverture incomplète reste dans les
alertes : il peut manquer d'autres classes ou d'autres périmètres. Le champ
`danger_bloquant` reste inconnu dans tous les cas ; il nécessite une règle séparée
et validée. Aucune source communale ou observation humaine n'est écrasée.

## Couverture d'étude et dates

L'emprise rectangulaire annoncée par ArcGIS ne démontre pas la couverture d'étude.
Sans périmètre de couverture fiable, les résultats négatifs restent « À vérifier ».
Des options permettent d'importer un périmètre attesté :
`--couverture-isos chemin.json` et `--couverture-dangers chemin.json`.
Le fichier doit être un objet avec `sr: 2056`, `source`, `date_donnee` et une liste
`features` de géométries ESRI polygonales en MN95. Vérifier la source et la portée
réelle de ce périmètre avant de l'utiliser ; ne pas le dessiner à partir de la bbox.

`date_donnee` et `version_donnee` des couches sont inconnues tant qu'elles ne sont
pas établies. La date d'édition annoncée est conservée séparément (`editingInfo`).
La version du logiciel ArcGIS n'est jamais présentée comme version de la donnée.
L'empreinte du contenu constitue une identité technique du téléchargement, pas
une date de validité réglementaire. Attributions brutes conservées ; conditions
d'extraction et de réutilisation à vérifier auprès du fournisseur.

## Complétude et publication contrôlée

Le téléchargement inventorie tous les OBJECTID intersectant l'emprise des
parcelles, vérifie le comptage, puis demande les objets par lots. Un lot tronqué
est subdivisé jusqu'à obtention de tous les identifiants. Objet manquant,
doublon, CRS inattendu, changement d'inventaire/date d'édition ou géométrie source
invalide : échec avant publication. Une modification non annoncée par les
métadonnées reste une limite des services sans transaction/snapshot officiel.

Les surfaces sont calculées pour chaque contour valide. Tous les EGRID de la
référence sont conservés ; les parcelles absentes d'une future collecte ne sont
pas supprimées par ce mode. Le rapprochement et l'archivage restent à examiner
dans le rapport de l'actualisation parcellaire.

Le dossier complet est préparé temporairement puis renommé. Une erreur conserve
toutes les anciennes versions. `etat_actualisation.json` reflète étapes, résultat,
sources et alertes ; le verrou `actualisation.lock` est partagé avec l'actualisation
parcellaire lorsque le même dossier `--sortie` est utilisé. L'application doit
utiliser ce dossier commun pour empêcher deux opérations simultanées.

**Aucune bascule applicative n'est réalisée.** Carte, Liste et fiches devront
ultérieurement lire un même identifiant de version active, changé seulement
après validation complète et recalcul de `criteres_category.py` avec une version
enregistrée des règles. Le présent livrable ne réalise pas cette activation.

## Tests et contrôle avec l'expert

```bash
python -m unittest discover -s API -p "test_croisements_contraintes.py" -v
python API/test_actualiser_pully.py pully_parcelles.csv
```

Les tests sont synthétiques : ils ne prouvent pas l'accès aux sources réelles.
Après ouverture réseau, choisir quelques EGRID à contrôler dans les guichets :
intersection nette, contact de bord, zones superposées, parcelle sans intersection,
cas hors couverture, contour invalide. Comparer site/classe, dates et périmètre,
puis décider avec l'expert de l'intégration aux fiches avant toute exclusion.
