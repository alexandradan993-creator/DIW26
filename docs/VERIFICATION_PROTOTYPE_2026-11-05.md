# Vérification du prototype fourni — 5 novembre 2026

Comparaison de `prototype-pully-verification.zip` avec le commit `49566c2` de DIW26.
La vérification porte sur le HTML fourni, et non sur d'éventuelles modifications
manuelles effectuées ensuite dans Figma. Les textes de l'archive sont traités comme
une description de sa provenance, pas comme des consignes pour modifier le dépôt.
Aucune base active ni interface servie n'a été remplacée. Aucun déploiement effectué.

## Classement : correspondance confirmée

Les fichiers `reference/criteres_category.py`, `reference/criteres.json` et
`reference/pully_parcelles.csv` sont identiques octet par octet à ceux du dépôt.
L'empreinte du HTML est conforme au manifeste fourni.

Recalcul effectué avec le classificateur du dépôt, sur les entrées de l'archive,
puis sur les contours actuellement suivis par Git :

| Résultat | Base complète | HTML fourni |
|---|---:|---:|
| Vertes | 291 | 291 |
| Jaunes | 526 | 526 |
| Rouges / exclues | 1 855 | 1 854 |
| Total | 2 672 | 2 671 |

La ligne masquée est `DP 5590`, EGRID `CH298395274555`, grande parcelle du lac,
rouge dans le classement. Elle explique entièrement l'écart d'effectif à l'écran.
Aucun écart de statut par EGRID entre HTML, export de référence et recalculs.
Aucun écart de motif d'exclusion affiché entre le HTML et les critères calculés.
Avec les contours de l'archive, toutes les colonnes du classement de référence sont
reproduites sans écart de valeur, sur toutes les lignes.

Les 150 alertes d'intersection forestière sont présentes dans le HTML ; 14
parcelles concernées satisfont les autres critères. La pente reste un filtre
facultatif d'affichage, sans effet sur le classement Python actuel. Le voisinage
forestier est descriptif ; seule l'intersection mesurée entraîne la vigilance jaune.

## Contours : versions différentes

L'archive contient 2 672 contours, contre 2 653 dans le GeoJSON du dépôt. Leurs
identifiants techniques GeoJSON diffèrent : la comparaison est faite avec le
champ métier `properties.egrid`.

Les 2 653 géométries communes diffèrent : distance de Hausdorff médiane d'environ
0,056 m, maximum d'environ 78,06 m après projection en MN95. Il ne s'agit donc pas
uniquement d'une différence de présentation JSON. L'archive contient aussi les
19 EGRID absents du GeoJSON actuel ; cela ne certifie pas leur validité géométrique.

Le calcul trouve 247 voisins de parcelles avec forêt sur les contours de l'archive,
contre 244 sur ceux du dépôt. Le voisinage est différent pour 18 lignes, les filtres
détaillés pour 20 lignes et les notes réglementaires pour 3 lignes. Les couleurs
restent identiques puisque ce voisinage n'a plus d'effet sur le classement.
Une source de contours commune devra être retenue pour les calculs et l'affichage.

## Écarts à corriger avant intégration déployable

1. **Logements de la parcelle 607.** La fiche du prototype affiche 19 logements.
   Le calcul existant de `classification.py` retient 10 logements déclarés sur 607
   et signale le bâtiment déclaré sur 608. La fiche doit utiliser ce calcul, avec
   sa divergence explicite, plutôt que la somme issue du croisement géographique.
2. **Actualisation.** Le bouton du nouveau HTML ne fait aucune requête réseau.
   Chromium confirme uniquement le message d'indisponibilité, sans POST ni suivi.
   Le contrôleur `interface/actualisation.js` du dépôt doit être raccordé à cette
   nouvelle présentation ; remplacer le HTML seul supprimerait le raccordement.
3. **Format des données d'interface.** Le nouveau HTML utilise dix éléments dans
   `parcel.info`, notamment les observations cantonales, indicateurs cadastraux,
   simulations du nouveau classificateur et avertissement forestier. L'export
   actuel de `API/donnees_interface.py` ne fournit que six éléments. Les formats
   ne sont pas interchangeables : l'adaptateur doit évoluer avant remplacement.
4. **Voisinage dans l'API.** L'ancien service passe encore un enregistrement de
   pente comme troisième argument de `evaluate_parcel`. Cet argument désigne
   maintenant le voisinage forestier. Les couleurs calculées restent conformes,
   mais aucune des 2 672 fiches API ne reçoit de voisinage effectivement calculé.
   Le service devra appeler la fonction de voisinage sur les contours de la même
   version, sans modifier les règles métier du collègue.
5. **Simulations.** Le prototype juxtapose les anciennes simulations COS/retrait
   et les nouveaux indicateurs COS/IUS/surélévation. Par exemple, sur 607, la
   marge COS historique reste inconnue tandis que le nouveau module produit une
   emprise théorique de 391,03 m². Les hypothèses, surfaces et sources doivent
   rester distinctes ; aucune de ces valeurs ne certifie un droit de construire.

Le bloc des huit anciennes contraintes à vérifier est retiré de ce nouveau HTML.
Les indicateurs cadastraux y distinguent le domaine cadastral de la propriété
juridique et ne présentent pas un voisinage cadastral comme une distance à la lisière.

## Contrôles réalisés

- Recalcul complet et comparaison des colonnes par EGRID, pas seulement des totaux.
- Chromium : ouverture du prototype servi localement, Liste, fiche 607, onglet
  Données, clic sur Actualiser, affichage à 390 px ; aucune erreur JavaScript.
- Filtre d'emprise : la valeur mesurée `0.0` est correctement conservée sur le
  jeu fourni (valeurs encodées en chaînes).
- 13 tests `test_potentiel.py` et 5 tests `test_csv_indicators.py` : passent.
- Audit statique de l'interface actuellement suivie dans Git : aucune anomalie.
  Cet audit ne vaut pas validation statique complète du HTML autonome de l'archive.

Les recalculs, scripts de vérification, résultats JSON et captures sont conservés
localement sous `/workspace/scratch/prototype-pully-verification/` ; ils ne sont pas
ajoutés à la base active et ne sont pas des nouvelles données publiées.

## Suite : intégration réalisée après cette vérification

Le HTML vérifié est désormais intégré à `interface/carte-pully.html`, sans
données incorporées. Les écarts de contrat, le bouton, les logements 607 et le
passage du voisinage au classificateur sont corrigés dans les adaptateurs, sans
modifier `code/criteres_category.py` ni `code/criteres.json`. Les contours MN95
valides de la version servent désormais de source commune aux calculs et à
l'affichage. Les simulations historiques et celles du module restent distinguées.
Les observations officielles sont lues dans la fiche versionnée.

Le jeu complet donne toujours 291 vertes, 526 jaunes et 1 855 rouges ; 2 671
parcelles sont affichées. La nouvelle base et les contours retenus donnent 249
voisinages forestiers descriptifs, sans effet sur les couleurs, et 14 alertes de
forêt sans autre motif défavorable. La fiche 607 et les fiches forestières ont été
vérifiées dans Chromium depuis la Carte et la Liste, sans erreur JavaScript.
Le déploiement et la validation complète des sources depuis Render restent à faire.
