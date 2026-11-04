# Actualisation de `pully_parcelles.csv`

`actualiser_pully.py` recrée la base des parcelles de Pully depuis **GEO.vd** et **SIGIP**.
Il écrit un **nouveau** fichier `pully_parcelles_AAAA-MM-JJ_HHMM.csv`, avec les mêmes
76 colonnes et les mêmes clés JSON que la base actuelle. Il ne remplace jamais rien.

## Installation (une fois)

```bash
python -m pip install shapely
```

Python 3.10 ou ultérieur. Aucune autre dépendance.

## Utilisation

Placer les trois fichiers (`actualiser_pully.py`, `schema_pully_parcelles.json`,
`test_actualiser_pully.py`) dans un même dossier, puis :

```bash
# 1. Tester les règles de calcul hors ligne (aucun accès réseau)
python test_actualiser_pully.py ../pully_parcelles.csv

# 2. Vérifier que chaque source répond
python actualiser_pully.py --diagnostic

# 3. Produire une nouvelle base et la comparer à l'actuelle
python actualiser_pully.py --sortie versions --reference ../pully_parcelles.csv
```

## Fichiers produits dans `versions/`

| Fichier | Rôle |
|---|---|
| `pully_parcelles_AAAA-MM-JJ_HHMM.csv` | La nouvelle base, publiée seulement si tout a réussi |
| `pully_parcelles_…_comparaison.json` | Parcelles ajoutées, absentes, modifiées, et colonnes qui ont changé, avec des exemples avant/après |
| `etat_actualisation.json` | État lu par l'interface pour l'avancement et la notification |
| `actualisation.lock` | Présent seulement pendant un calcul : empêche deux lancements simultanés |

### Contrat avec l'interface (`etat_actualisation.json`)

```json
{
  "statut": "en_cours | termine | erreur",
  "etape": "Vérification des sources | Récupération | Contrôle | Calcul des attributs | Écriture",
  "debut_utc": "...", "fin_utc": "...",
  "fichier": "pully_parcelles_2026-11-06_0930.csv",
  "sources": {"batiments": {"objets": 4120, "verifie_utc": "..."}},
  "alertes": ["..."],
  "bilan": {"parcelles": 2672, "ajoutees": 0, "absentes": 0, "modifiees": 12},
  "erreur": null
}
```

- `en_cours` : l'interface continue d'utiliser l'ancienne base.
- `termine` : afficher la notification « Nouvelle base disponible » avec le `bilan`.
- `erreur` : afficher « Mise à jour non appliquée — vérification nécessaire » et le message.
  Aucune nouvelle base n'est créée, l'ancienne reste active.

Le passage d'une base à l'autre, l'archivage et la suppression sont gérés par l'application.

## Sources

| Données | Service |
|---|---|
| Parcelles (numéro, genre, surface RF, EGRID, contour) | GEO.vd `vd.bien_fond` (couche 272) |
| Bâtiments | GEO.vd `vd.batiment` (276) |
| Zones d'affectation | GEO.vd `vd.zone_affectation` (36) |
| Adresses | GEO.vd `vd.adresse` (241) |
| 13 couches `sigip_*` | WFS SIGIP `https://www.sigip.ch/mapserv_proxy` |

GEO.vd : `https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer`.
Les URL et numéros de couche sont regroupés en haut du script.

## Règles reproduites (vérifiées sur les 2 672 lignes de la base actuelle)

- Un objet est rattaché à une parcelle si son intersection est ≥ 0,1 m² (surfaces)
  ou s'il est dans la parcelle (points : `rcb_bat`, `rec_arch_p`, adresses).
- `surface_intersection_m2` est arrondie à 3 décimales. Les totaux `*_surface_intersection_m2`
  sont la surface de l'**union** des intersections, pour ne pas compter deux fois les chevauchements.
- Les liens HTML des champs SIGIP sont aussi stockés sous forme de liste dans `<champ>_urls`.
- Les notes : bâtiment existant = `rec_arch_s.note_detail`, site existant = `rec_arch_site.note_carto`,
  provisoires = `note_provisoire` des couches `pully_recensement_provisoire_*`.
- La zone dominante est celle qui a la plus grande intersection. Les agrégats RCB sont des sommes
  (logements, plancher) ou des maximums (niveaux, année).

## Points encore incertains

La base actuelle a été produite par Codex sans laisser son script. Ces points n'ont pas pu
être confirmés et apparaîtront dans le rapport de comparaison s'ils diffèrent :

1. **`surface_mo_m2`** : la source exacte n'a pas été trouvée. Si la couche parcelles ne fournit
   pas de surface MO, le script utilise la surface géométrique arrondie, qui correspond
   dans 89 % des cas.
2. **Zones d'affectation** : la base actuelle contient 4 champs que la couche publique 36 n'a pas
   (`REMARQUES_GEO`, `REMARQUES_TYPE`, `SHAPE.AREA`, `SHAPE.LEN`). Les deux derniers sont
   recalculés, les deux premiers restent vides.
3. **Adresses** : le script prend `vd.adresse`. La base a peut-être utilisé `pully_adresses` (SIGIP).
4. **Accès SIGIP** : le catalogue ASIT-VD indique un service réservé à la commune et à ses
   mandataires pour certaines données. `--diagnostic` montre immédiatement quelles couches répondent.
5. **L'ordre des objets** dans les listes JSON n'est pas reproductible. La comparaison n'en tient
   pas compte, sauf pour les notes.

Après le premier lancement réel, lire `…_comparaison.json`. Si une colonne diffère
pour presque toutes les parcelles, c'est une règle ou une source à ajuster, pas un vrai changement.
