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