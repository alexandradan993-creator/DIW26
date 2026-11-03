# Deux pourcentages séparés et effet de la forme

Évolution issue du document « DIW Foncimo - Team 5 (1).pdf » et des précisions
utilisateur du 3 novembre 2026. Les deux indicateurs ont été demandés séparément.
Ce ne sont ni des scores pondérés ni des probabilités d'autorisation.

## Terrain restant après retrait — simulation

`part_terrain_apres_retrait_pct = 100 × aire après retrait / aire du contour`

Le contour est érodé de **6 m** en MN95, y compris autour des trous. Les parties
disjointes restent distinctes. Le calcul conserve leur nombre et l'aire de la
plus grande ; leur somme ne garantit pas de pouvoir placer un bâtiment unique.
Les angles concaves sont approchés avec 32 segments par quadrant.

Les 6 m sont une **hypothèse transmise par l'utilisateur**, pas une règle
vérifiée pour chaque zone. Aucun article précisant son champ n'est fourni.
La distance et sa source sont configurables dans `filtres.json`, section `forme`.
Un changement de distance exige de recalculer les formes : la classification
n'utilise pas de résultat produit avec une distance différente.

Pour un rectangle L × l et un retrait d :

`aire restante = max(0, L − 2d) × max(0, l − 2d)`

À surface égale de 1 600 m², après retrait de 6 m :

| Dimensions | Aire restante | Part restante |
|---|---:|---:|
| 40 × 40 m | 784 m² | 49 % |
| 20 × 80 m | 544 m² | 34 % |
| 10 × 160 m | 0 m² | 0 % |

C'est l'étroitesse et l'irrégularité qui comptent, pas une étiquette « rectangle ».
La compacité `4π × aire / périmètre²` (cercle proche de 1, carré π/4) et
l'allongement du rectangle englobant minimal sont descriptifs, sans score.

L'enveloppe ne tient pas compte des arbres, accès, pleine terre, droits de tiers,
reculs particuliers (routes, eaux, forêts) ou du bâti à conserver. Ne pas la
nommer « surface constructible ». Une enveloppe vide n'exclut pas automatiquement
une transformation, une surélévation ou un projet relevant d'autres distances.

## Marge d'emprise COS — simulation

```text
Maximum simulé = surface de référence approchée × COS configuré
Écart brut = maximum simulé − emprise cadastrale existante
marge_emprise_cos_pct = 100 × max(0, écart brut) / maximum simulé
```

Exemple : maximum de 300 m², emprise existante de 120 m² → **60 % de marge**,
soit 180 m² d'écart apparent. Le dénominateur est le plafond COS, pas le terrain.
Un écart négatif reste dans les données brutes ; le pourcentage est alors 0 %.
Un indicateur inconnu reste vide et n'est jamais remplacé par zéro.

Le COS de 0,20 n'est configuré que pour « Zone de moyenne densité », d'après
l'entretien, à confirmer dans les textes. Une zone incertaine ou des surfaces
incohérentes empêchent le calcul. Le CSV fournit des approximations cadastrales,
pas les surfaces de référence et emprises juridiquement validées.

Le PDF contient également un ratio en **surface de plancher** : il ne doit pas
être confondu avec ce calcul d'emprise au sol. Le COS seul ne permet pas de
calculer des logements supplémentaires ou le potentiel de surélévation.

## Combinaison : une borne en m², pas un droit acquis

Si le contour est sans alerte et le COS connu :

```text
plafond_emprise_cos_forme_simule_m2 = min(maximum COS, aire après retrait)
ecart_apparent_cos_forme_m2 = ce plafond − emprise cadastrale existante
```

Ces colonnes sont des bornes exploratoires. L'emplacement du bâti existant
n'est pas croisé avec l'enveloppe : aucune extension implantable n'est démontrée.
Les 61 contours à vérifier pour écart de surface n'alimentent pas cette combinaison.
On ne multiplie pas automatiquement l'aire érodée par le COS : la surface de
référence doit être définie par le règlement, sans double comptage des retraits.

## Limites du document et règles conservées

Les affirmations réglementaires du PDF restent à sourcer. Une exigence de 50 %
de pleine terre ne rend pas automatiquement constructibles les autres 50 %.
Le document contient plusieurs traitements de la note 3 : notre exclusion
commerciale confirmée reste 1–3, même provisoire. Les anciens points, seuils de
surface et l'énergie ne sont pas réactivés. Seuil actuel : **600 m² inclus**,
pente descriptive, aucun score global. Arbres, ISOS et réglementation détaillée
restent à compléter. Tous les dossiers gardent `statut_potentiel=non_etabli`.
Les indicateurs descriptifs ne changent pas seuls les statuts de filtrage.

## Exécuter et consulter

Depuis la racine avec un environnement Python actif :

```bash
python -m pip install -r scripts/requirements-parcelles.txt
python scripts/calculer_formes_parcelles.py
python code/classification.py --input pully_parcelles.csv --config code/filtres.json --pentes data/pentes_parcelles/pentes_parcelles.csv --formes data/formes_parcelles/formes_parcelles.csv
python -m unittest discover -s code -p "test_*.py" -v
```

Formes et enveloppes : `data/formes_parcelles/`. Classification et pourcentages
combinés : `code/resultats_classification/classification.csv` et son résumé,
locaux et ignorés par Git comme précédemment.

Le calcul géométrique et ses quatre tests exigent Shapely/pyproj ; la classification
reste en bibliothèque standard. Sans ces dépendances, les tests géométriques
sont explicitement sautés et ne doivent pas être annoncés réussis.

Pour Figma : afficher les deux libellés distincts avec leur dénominateur,
« Simulation », l'hypothèse et les alertes. Ne pas afficher « potentiel : X % ».
