# API — Actualisation de la base des parcelles de Pully

Ce dossier contient tout ce qu'il faut pour **reconstruire la base `pully_parcelles.csv`
depuis les sources officielles** (GEO.vd et SIGIP), sans jamais remplacer une base existante.
C'est la mécanique qui se trouvera derrière le bouton **« Actualiser les données »** de l'application.

**État au 4 novembre 2026 : fonctionnel.** Le script a été lancé avec succès contre les vrais
services (17 sources accessibles, 2 672 parcelles produites en environ 3 minutes).

> **Autre mode, séparé :** [export des croisements ISOS cantonaux et dangers](CROISEMENTS.md),
> via `--croisements`. Il utilise les couches 404/422 et les contours locaux, sans modifier
> les 76 colonnes de la base ni activer une version dans l'application.

---

## 1. Contenu du dossier

| Fichier | Rôle |
|---|---|
| `actualiser_pully.py` | **Le script d'actualisation.** Télécharge les données, rattache chaque objet à sa parcelle, calcule les colonnes et écrit une nouvelle base |
| `schema_pully_parcelles.json` | Le « moule » de la base : ordre des 76 colonnes, clés et types de chaque objet JSON. **Indispensable**, le script ne fonctionne pas sans |
| `test_actualiser_pully.py` | Tests hors ligne : vérifie que les règles de calcul reproduisent la base |
| `bases/pully_parcelles_2026-11-04_1614.csv` | **Première base produite par le script** (4 novembre 2026, 16 h 14) |
| `bases/pully_parcelles_2026-11-04_1614_comparaison.json` | Rapport de différences entre cette base et la base initiale |
| `croisements_contraintes.py`, `CROISEMENTS.md`, `test_croisements_contraintes.py` | Mode séparé ISOS / dangers (voir lien ci-dessus) |
| `.gitignore` | Empêche d'envoyer sur GitHub les bases générées dans `versions/` (environ 15 Mo chacune) |

La **base initiale** (produite par Codex le 2 novembre 2026) reste à la racine du dépôt :
`../pully_parcelles.csv`. Elle n'est pas modifiée.

---

## 2. Installation (une fois)

- Python **3.10 ou plus** (sous Windows, la commande peut s'appeler `py` au lieu de `python`).
- Une seule bibliothèque externe :

```bash
python -m pip install shapely
```

---

## 3. Lancer une actualisation à la main

Toujours **depuis le dossier `API/`** :

```bash
cd API

# 1. Tests hors ligne (quelques secondes) : toutes les lignes doivent commencer par OK
python test_actualiser_pully.py

# 2. Vérifier que les 17 sources répondent : toutes les lignes doivent afficher [OK]
python actualiser_pully.py --diagnostic

# 3. Actualiser (environ 3 minutes) et comparer avec la base actuelle
python actualiser_pully.py --sortie versions --reference ../pully_parcelles.csv
```

À la fin, le dossier `API/versions/` contient :

| Fichier | Contenu |
|---|---|
| `pully_parcelles_AAAA-MM-JJ_HHMM.csv` | La nouvelle base (mêmes 76 colonnes que l'ancienne) |
| `pully_parcelles_…_comparaison.json` | Parcelles ajoutées, absentes, modifiées, colonne par colonne, avec exemples avant/après |
| `etat_actualisation.json` | L'état de l'opération, lu par l'interface |
| `actualisation.lock` | Présent **uniquement pendant** le calcul |

---

## 4. Comment fonctionne l'actualisation (pour l'interface)

### Le parcours vu par l'utilisateur

1. L'expert clique sur **« Actualiser les données »**.
2. Le script démarre **en arrière-plan**. L'application **continue d'utiliser l'ancienne base** :
   l'expert peut travailler normalement.
3. Quand le script a fini, une **notification** apparaît : « Nouvelle base disponible »,
   avec le bilan (par exemple « 2 672 parcelles, 1 095 parcelles modifiées »).
4. L'expert choisit de **basculer** sur la nouvelle base, ou de garder l'ancienne.
5. L'ancienne base n'est **jamais supprimée automatiquement** : elle passe dans les
   **bases archivées**. Seul l'expert peut supprimer une base archivée.

### Ce que fait le script, étape par étape

| Étape (champ `etape`) | Ce qui se passe |
|---|---|
| `Vérification des sources` | Teste les 17 sources. Si une seule ne répond pas, on s'arrête : erreur, aucune base créée |
| `Récupération` | Télécharge les parcelles, bâtiments, zones et adresses (GEO.vd), puis les 13 couches SIGIP |
| `Contrôle` | Vérifie les géométries, les champs reçus, les EGRID en double. Les anomalies vont dans `alertes` |
| `Calcul des attributs` | Rattache chaque objet à sa parcelle, calcule les surfaces, la zone dominante, les notes, les agrégats RCB |
| `Écriture` | Écrit la nouvelle base, puis le rapport de comparaison |

Les fichiers sont écrits d'abord sous un nom temporaire, puis renommés d'un coup.
L'interface ne peut donc jamais lire une base à moitié écrite.

### Le fichier `etat_actualisation.json` (le lien avec l'interface)

L'interface n'a besoin de lire **que ce fichier**. Il est mis à jour à chaque étape.

```json
{
  "statut": "en_cours | termine | erreur",
  "etape": "Vérification des sources | Récupération | Contrôle | Calcul des attributs | Écriture",
  "debut_utc": "2026-11-04T15:11:33+00:00",
  "fin_utc": "2026-11-04T15:14:40+00:00",
  "fichier": "pully_parcelles_2026-11-04_1614.csv",
  "sources": {"batiments": {"objets": 4120, "verifie_utc": "..."}},
  "alertes": ["..."],
  "bilan": {"parcelles": 2672, "ajoutees": 0, "absentes": 0, "modifiees": 1095},
  "erreur": null
}
```

| `statut` | Ce que l'interface affiche |
|---|---|
| `en_cours` | Indicateur « Actualisation en cours » avec `etape`. L'ancienne base reste utilisée |
| `termine` | Notification « Nouvelle base disponible » avec le `bilan` (`modifiees` = parcelles réellement modifiées) et le nom du `fichier` |
| `erreur` | « Mise à jour non appliquée — vérification nécessaire » et le texte de `erreur`. L'ancienne base reste active |

### Règles importantes

- **Un seul lancement à la fois.** Tant que `actualisation.lock` existe, un deuxième lancement
  est refusé (code de sortie 2). Si le script a été interrompu brutalement (PC éteint, terminal fermé),
  ce fichier peut rester : il faut alors le supprimer à la main avant de relancer.
- **Jamais de remplacement.** Chaque base a un nom daté. Le script ne touche à aucune autre base.
- **La comparaison se fait avec la base active.** Passer en `--reference` la base que l'expert
  utilise actuellement, pour que le bilan montre ce qui a changé depuis.

### Ce que l'application doit gérer elle-même

Le script produit les bases. **La bascule, l'archivage et la suppression sont à faire dans l'application** :

- garder quelque part le nom de la **base active** (par exemple dans un petit fichier `base_active.txt`) ;
- **basculer** = changer ce nom pour celui de la nouvelle base ;
- **bases archivées** = toutes les bases du dossier `versions/` sauf la base active ;
- **supprimer** = effacer le fichier, uniquement à la demande de l'expert.

### Brancher le bouton

Une maquette Figma **ne peut pas lancer de Python**. Pour un vrai bouton, il faut une interface
codée (page web) et un petit serveur à côté du script, par exemple en FastAPI, avec deux routes :

| Route | Rôle |
|---|---|
| `POST /actualisations` | Lance `python actualiser_pully.py --sortie versions --reference <base active>` en arrière-plan et répond tout de suite |
| `GET /actualisations/etat` | Renvoie le contenu de `versions/etat_actualisation.json` |

Le bouton appelle la première route, puis l'interface interroge la seconde toutes les quelques
secondes jusqu'à `termine` ou `erreur`.

---

## 5. Base initiale ou base générée : quelles différences ?

Comparaison entre la **base initiale** (`../pully_parcelles.csv`, Codex, 2 novembre 2026)
et la **base générée** (`bases/pully_parcelles_2026-11-04_1614.csv`, ce script, 4 novembre 2026).
Rapport complet : `bases/pully_parcelles_2026-11-04_1614_comparaison.json`.

Les deux bases ont **les mêmes 2 672 parcelles** (aucune ajoutée, aucune absente) et
**les mêmes 76 colonnes**. Les chiffres ci-dessous comptent les parcelles réellement différentes,
sans tenir compte des identifiants SIGIP renumérotés ni des décimales.

### Colonnes identiques (16)

`egrid`, `numero_parcelle`, `genre_parcelle`, `surface_rf_m2`, `url_rdppf`, `url_extrait_rdppf`,
`batiments_nombre`, `cos_source_zone_dominante`, `ius_source_zone_dominante`,
`taux_emprise_geometrique`, `statut_potentiel`, ainsi que les 5 colonnes vides dans les deux bases
(`decision_conti`, `motif_conti`, `type_bati_valide`, `surface_plancher_verifiee_m2`,
`pleine_terre_reglementaire_m2`).

### Colonnes différentes (60), par cause

**1. Attribut manquant ou source inconnue**

| Colonne | Parcelles | Explication |
|---|---:|---|
| `zones_affectation_json` | 713 | Le champ **`REMARQUES_GEO`** (ex. « Densité variable », « Erreur d'affectation ») n'existe pas dans la couche publique GEO.vd utilisée. Il reste vide. Champ informatif, non utilisé par le classement |
| `surface_mo_m2` | 309 | Source de la surface MO inconnue. Le script prend la surface géométrique arrondie |
| `adresses_json`, `adresses_nombre` | 26 | Quelques numéros d'entrée différents (« 4a », « 117.1 ») : la base initiale combinait sans doute une autre source d'adresses |

Le champ `REMARQUES_TYPE` est aussi absent de la couche publique, mais il était vide dans la base initiale.

**2. Contours légèrement différents (41 colonnes)**

Les contours des parcelles diffèrent de quelques m², surtout pour les routes et les bords courbes
(ex. DP 62 : 3 423,3 → 3 420,6 m²). Par effet domino, des **micro-intersections** juste au-dessus
ou en dessous du seuil de 0,1 m² apparaissent ou disparaissent.

| Colonnes | Parcelles |
|---|---:|
| `surface_geometrique_m2` / `surface_hors_emprise_batiments_m2` | 171 / 183 |
| `batiments_json`, `batiments_surface_intersection_m2`, `emprise_batie_m2` | 22–23 |
| `zones_affectation_nombre` | 197 |
| `zone_dominante`, `zone_dominante_statut`, `zone_dominante_part_surface` | 1 |
| SIGIP surfaces vertes (`_json` / `_nombre` / surface) | 311 / 124 / 194 |
| SIGIP zone réservée | 204 / 78 / 138 |
| SIGIP plans d'affectation (`pga`) | 203 / 28 |
| SIGIP surfaces dures | 171 / 61 / 116 |
| SIGIP forêts | 44 / 21 / 22 |
| SIGIP eaux | 47 / 35 / 20 |
| SIGIP sites recensés / sites provisoires / jardins historiques | 46 / 40 / 31 |
| SIGIP bâtiments recensés / provisoires / objets ponctuels | 5 / 4 / 2 |

**3. Vraies mises à jour des données (9 colonnes)**

Le registre des bâtiments (RCB) a été mis à jour entre le 2 et le 4 novembre : dates de modification,
statut « autorisé » → « existant », années de transformation. C'est exactement ce que l'actualisation
doit détecter.

| Colonnes | Parcelles |
|---|---:|
| `sigip_rcb_bat_json` / `sigip_rcb_bat_nombre` | 48 / 19 |
| `rcb_*` (logements, niveaux, année, plancher) | 8–19 |

**4. Notes patrimoniales (8 colonnes), conséquence de la cause 2**

| Colonnes | Parcelles |
|---|---:|
| `notes_site_existante_json` / `presence_note_1_3_site_existante` | 16 / 14 |
| `notes_site_provisoire_json` / `presence_note_1_3_site_provisoire` | 13 / 8 |
| `notes_batiment_existante_json` / `presence_…` | 2 / 1 |
| `notes_batiment_provisoire_json` / `presence_…` | 1 / 1 |

### Impact sur le classement (`code/classification.py`)

| Statut | Base initiale | Base générée |
|---|---:|---:|
| Exclue | 1 345 | 1 334 |
| Retenue | 1 201 | 1 212 |
| À vérifier | 126 | 126 |

**17 parcelles changent de statut, toutes du domaine public (routes, chemins). Aucune parcelle privée n'est touchée.**
Elles recevaient ou perdent une note de site patrimonial voisin via un chevauchement de **0,10 à 0,28 m²**.
Ces rattachements sont des artefacts de géométrie, présents dans les deux bases.

---

## 6. Règles de construction de la base

Retrouvées en analysant la base initiale et vérifiées sur ses 2 672 lignes (`test_actualiser_pully.py`).

- Un objet surfacique est rattaché à une parcelle si l'intersection est **≥ 0,1 m²**.
  Un objet ponctuel (`rcb_bat`, `rec_arch_p`, adresses) est rattaché s'il est **dans** la parcelle.
- `surface_intersection_m2` est arrondie à 3 décimales. Les totaux `*_surface_intersection_m2`
  sont la surface de l'**union** des intersections (sans double compte des chevauchements).
- Les liens HTML des champs SIGIP sont aussi stockés en liste dans `<champ>_urls`.
- Notes : bâtiment existant = `rec_arch_s.note_detail`, site existant = `rec_arch_site.note_carto`,
  provisoires = `note_provisoire` des couches `pully_recensement_provisoire_*`.
  `presence_note_1_3_*` = au moins une note entre 1 et 3.
- Zone dominante = zone de plus grande intersection. Agrégats RCB : sommes (logements, plancher),
  maximums (niveaux, année).
- Les types de chaque valeur (nombre entier, décimal, texte, date) sont imposés par
  `schema_pully_parcelles.json`, car SIGIP renvoie certains nombres sous forme de texte.

### Sources

| Données | Service |
|---|---|
| Parcelles (numéro, genre, surface RF, EGRID, contour) | GEO.vd `vd.bien_fond` (couche 272) |
| Bâtiments | GEO.vd `vd.batiment` (276) |
| Zones d'affectation | GEO.vd `vd.zone_affectation` (36) |
| Adresses | GEO.vd `vd.adresse` (241) |
| 13 couches `sigip_*` | WFS SIGIP `https://www.sigip.ch/mapserv_proxy` |

GEO.vd : `https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer`.
Les URL et numéros de couche sont regroupés en haut de `actualiser_pully.py`.

---

## 7. Points ouverts

**Décisions à prendre**

1. **Faire de la base générée la nouvelle référence ?** Recommandé : toutes les actualisations
   suivantes se compareront alors à une base produite par ce même script, et le bilan ne montrera
   que de vrais changements. La base initiale serait conservée en archive.
2. **Seuil de rattachement des couches patrimoniales.** Le passer de 0,1 m² à 1 m² supprimerait
   les 17 faux rattachements sur les routes sans toucher aux vraies notes. Pas encore appliqué.

**Limites connues**

- `REMARQUES_GEO` et la surface MO : source exacte inconnue (le script d'extraction de Codex n'a pas été conservé).
- **Accès SIGIP** : aujourd'hui public pour les 13 couches utilisées, mais le catalogue ASIT-VD
  indique un accès restreint pour certaines données. Si une couche devient inaccessible, `--diagnostic` le montre.
- **Droits SIGIP** : les conditions de viageo.ch limitent l'usage au projet désigné, sans commercialisation,
  avec la mention « Copyrights géodonnées Ville de Pully ». À clarifier avec la Ville de Pully pour un usage commercial.
- **Changement d'EGRID** : une parcelle divisée ou fusionnée change d'EGRID. Les notes de l'expert
  ne suivent pas automatiquement : le rapport liste les parcelles ajoutées et absentes.
- **Pentes et formes** (`data/pentes_parcelles`, `data/formes_parcelles`) ne sont pas recalculées
  par ce script : relancer `scripts/calculer_pentes_parcelles.py` et `scripts/calculer_formes_parcelles.py`
  si de nouvelles parcelles apparaissent.
- **Pas encore fait** : le serveur du bouton, le déclenchement automatique (mensuel), la gestion
  de la base active et des archives dans l'application, la source de la propriété communale.
