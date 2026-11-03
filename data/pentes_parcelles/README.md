# Pentes par parcelle — Pully

Calcul exploratoire du 3 novembre 2026, joint par EGRID aux 2 672 lignes du CSV.
Il ne modifie pas les règles ni les statuts de prospection.

## Fichiers à consulter

- **`pentes_parcelles.csv`** : une ligne par parcelle, statistiques et alertes.
- **`resume.json`** : effectifs, exemple 607, méthode et empreintes des entrées
  et du CSV produit.

Le CSV est encodé en UTF-8 avec BOM, séparateur virgule, décimales avec un point.
`alertes_json` contient une liste JSON. Une case statistique vide est inconnue,
pas égale à zéro. Les résultats sont suivis dans Git pour partager cette analyse.

## Résultats et limites

| Statut technique | Nombre | Interprétation |
|---|---:|---|
| `calcule` | 2 591 | Statistiques disponibles, aucune alerte technique des contrôles exécutés |
| `calcule_a_verifier` | 61 | Statistiques disponibles mais écart de surface ou couverture incomplète |
| `non_calculable` | 20 | Aucune statistique exploitable avec les données et la méthode actuelles |

Parmi les 20 non calculables : 19 contours invalides et la parcelle **7469**,
qui ne contient aucun pixel sélectionné à 2 m malgré un contour valide. Sa forme
étroite et sa position par rapport à la grille peuvent expliquer cette absence ;
la taille seule ne détermine pas l'échantillonnage. Ne pas lui attribuer 0 % de pente.

Sur les 61 écarts de surface supérieurs à 1 % identifiés dans l'audit cadastral,
60 ont des pentes calculées et 7469 n'est pas calculable. Le dernier dossier
calculé à vérifier est **DP 5590** : environ **30,36 %** de son contour est dans
l'emprise du raster, avec 995 pixels NoData parmi les pixels sélectionnés dans
cette emprise. Ses statistiques décrivent uniquement les pixels valides couverts.
Les catégories d'alertes peuvent se cumuler : ne pas additionner leurs effectifs
pour compter les parcelles.

Le statut `calcule` ne valide ni la précision cadastrale ni le projet immobilier.
Les contours viennent d'un service de représentation à contenu réduit ; le
terrain swissALTI3D date de 2019/2021 selon les secteurs. Les pentes maximales
peuvent refléter un talus ou un mur et être sensibles aux artefacts : elles ne
doivent pas devenir seules un filtre d'exclusion.

## Indicateurs et unités

- `pente_moyenne_*`, `pente_mediane_*`, `pente_p90_*`, `pente_max_*` : statistiques
  calculées sur les pixels valides de la parcelle. Le P90 est le 90e percentile.
- Suffixe `_degres` : angle en degrés.
- Suffixe `_pct` : pente en pourcentage, `100 × tan(angle)`.
  Les statistiques en pourcentage sont calculées après conversion de chaque
  pixel ; la moyenne en pourcentage n'est pas la conversion de l'angle moyen.
- `part_pixels_pente_inf_10pct` : pourcentage des pixels valides avec pente < 10 %.
- `part_pixels_pente_10_a_25pct` : pourcentage avec pente entre 10 et 25 % inclus.
- `part_pixels_pente_sup_25pct` : pourcentage avec pente > 25 %.

Ces trois parts totalisent 100 % lorsqu'il existe des pixels valides. Ce sont
des fréquences de pixels, **pas des surfaces constructibles**, ni des fractions
exactes de la superficie cadastrale. Les seuils 10/25 % sont descriptifs, issus
des hypothèses du groupe ; ils ne sont pas validés comme filtres commerciaux.

- `couverture_emprise_raster_pct` : fraction géométrique de la parcelle à
  l'intérieur du rectangle du raster ; ne tient pas compte du NoData.
- `pixels_interieurs` : pixels sélectionnés par rasterisation dans le contour
  et dans l'emprise du raster.
- `pixels_valides` et `pixels_nodata` : séparation des pixels sélectionnés.
- `part_pixels_valides_pct` : proportion valide parmi les pixels sélectionnés,
  distincte de la couverture géométrique de toute la parcelle.
- `ecart_surface_relatif` : fraction héritée de l'audit cadastral, pas pourcentage.

Les trous des polygones sont exclus. La sélection utilise `all_touched=False`
(règle des centres de pixels pour les surfaces), sans pondération surfacique
des cellules coupées par une limite. Les NoData et valeurs non finies sont
exclus des statistiques. Aucun contour n'est réparé automatiquement.

### Exemple : parcelle 607

483 pixels valides ; couverture du rectangle de raster : 100 %.

| Mesure | Résultat arrondi |
|---|---:|
| Pente médiane | 22,84 % / 12,86° |
| Pente moyenne | 27,06 % / 14,45° |
| Pente maximale locale | 155,73 % / 57,29° |
| Pixels avec pente < 10 % | 20,91 % |
| Pixels entre 10 et 25 % | 33,33 % |
| Pixels avec pente > 25 % | 45,76 % |

Une pente supérieure à 100 % est possible : 100 % correspond à 45°.
Ces valeurs décrivent le terrain et ne changent pas le dossier de vérification
des logements de la parcelle 607.

## Relancer et tester

Depuis la racine du dépôt, avec un environnement Python virtuel actif :

```bash
python -m pip install -r scripts/requirements-geo.txt -r scripts/requirements-parcelles.txt
python scripts/calculer_pentes_parcelles.py
python -m unittest discover -s tests -p "test_pentes_parcelles.py" -v
```

Le calcul est local et ne requiert pas de téléchargement. Il remplace le CSV
et le résumé dans ce dossier. Les quatre tests synthétiques vérifient les
unités, les NoData, les trous, la couverture partielle et les parcelles sans pixel.
Les huit tests métier restent exécutables séparément :

```bash
python -m unittest discover -s prototype_pully -p "test_*.py" -v
```
