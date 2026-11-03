# Critères de prospection immobilière à Pully

## Mise à jour après clarification avec l'expert

La première classification configurable est décrite dans
[`prototype_pully/CLASSIFICATION.md`](prototype_pully/CLASSIFICATION.md).
Elle applique une surface minimale de **600 m² inclus** et l'exclusion
patrimoniale 1–3, même provisoire. Les arbres centraux sont un axe majeur à
documenter, sans exclusion automatique faute de règle et de données validées.
La sous-exploitation est explorée via une simulation COS, sans droit à bâtir
garanti. L'énergie est entièrement exclue ; la pente reste descriptive, sans
pénalité. Aucun score global ni pondération n'est validé. Les critères et besoins
géographiques futurs pourront être intégrés progressivement.

Les anciennes hypothèses et seuils ci-dessous sont conservés comme contexte
historique ; ils ne remplacent pas ces orientations actualisées.

État des échanges au 3 novembre 2026. Document de cadrage issu de l'entretien
avec l'expert, du travail du groupe et des décisions discutées ensuite.
Il ne constitue pas une validation réglementaire. Sa rédaction ne modifie pas
les règles du pipeline existant.

## Objectif et utilisateur

Repérer les parcelles présentant les meilleurs signaux de potentiel pour
l'expert, expliquer leur intérêt et indiquer les vérifications restantes.
L'outil ne certifie ni la constructibilité ni les droits à bâtir et n'estime
pas la valeur d'une parcelle.

L'expert travaille seul, réalise actuellement une à deux expertises par mois et
repère les occasions principalement lors de ses déplacements dans Pully.
Il souhaite développer sa prospection auprès de clients privés. Le temps
d'analyse non rémunéré après identification d'une parcelle constitue un coût
important : l'outil doit faciliter la décision de poursuivre ou d'arrêter.

## Scénarios recherchés

1. **Démolition-reconstruction : priorité principale.**
2. **Extension : scénario complémentaire confirmé lors de l'entretien.**
3. **Surélévation : intérêt indiqué dans les échanges précédents**, à traiter
   séparément avec vérification des hauteurs autorisées et de la structure.

Une difficulté propre à un scénario ne prouve pas l'absence de toute possibilité
sur la parcelle. Les exclusions ci-dessous expriment la cible commerciale de
l'expert, pas une déclaration générale d'inconstructibilité.

## Exclusions commerciales retenues

| Critère | Règle souhaitée | État et limites |
|---|---|---|
| Patrimoine | Exclure dès qu'un bâtiment ou un site porte une note 1, 2 ou 3, même provisoire | Déjà appliqué dans le prototype, qui contrôle aussi les objets ponctuels disponibles. Une note provisoire 4 ne lève pas une exclusion. |
| ISOS | Écarter les parcelles dans les périmètres ISOS concernés | Souhait de l'expert ; périmètres et règle d'intersection à préciser. Les points de localisation récupérés ne sont pas des périmètres. |
| Propriété communale | Écarter si la commune est propriétaire | Souhait de l'expert ; nécessite une source fiable et une propriété confirmée. La propriété inconnue n'est pas une exclusion automatique. |
| Centre-ville et proximité du lac | Éviter ces secteurs jugés complexes | Souhait exprimé ; l'expert doit les délimiter sur une carte. Aucun rayon ou périmètre d'exclusion n'est encore fixé. |

Les « notes 1 à 3 » sont les notes patrimoniales, pas des numéros de zones
d'affectation. Une note inconnue, par exemple 0, appelle une vérification.

## Signal principal : sous-exploitation apparente

Comparer l'emprise bâtie existante à une emprise théorique calculée à partir
du coefficient d'occupation du sol (COS) applicable à la zone.

**Information issue de l'entretien : COS = 0,20 pour la moyenne densité.**
Les coefficients varient selon la zone. Cette valeur doit être reliée au texte
réglementaire applicable ; elle ne doit pas être étendue aux autres zones ni aux
plans spéciaux sans vérification.

Calculs envisagés :

```text
Emprise théorique maximale = surface de terrain de référence × COS applicable
Écart apparent = emprise théorique maximale − emprise existante comparable
Ratio d'occupation = emprise existante comparable / emprise théorique maximale
```

Le ratio n'est calculable que si le dénominateur est positif et les données
comparables. Un écart négatif doit rester visible et être examiné.

Exemple purement illustratif : 1 500 m² × 0,20 = 300 m² d'emprise théorique.
Avec 120 m² d'emprise existante comparable, l'écart apparent est de 180 m² et le
ratio de 40 %. Cela ne garantit pas une extension de 180 m².

**Points indispensables avant automatisation :**

- établir la table des zones, des COS et des sources réglementaires ;
- vérifier la définition de la surface de terrain de référence ;
- distinguer l'emprise cadastrale disponible dans le CSV de l'emprise
  réglementaire déterminante ;
- vérifier les règles des plans spéciaux et les dispositions en vigueur ;
- distinguer emprise au sol et surface de plancher : le COS seul ne donne ni
  la surface totale de plancher ni le nombre de logements réalisables.

## Contraintes et signaux complémentaires

| Critère | Rôle dans la prospection | À définir ou vérifier |
|---|---|---|
| Pleine terre | Prendre en compte le critère des 50 % mentionné lors de l'entretien | Champ d'application, texte et définition réglementaire. Ne pas déduire que les 50 % restants sont constructibles ni exclure automatiquement une parcelle actuellement sous ce seuil. |
| Forme | Préférence pour les terrains carrés ou rectangulaires | Mesure à choisir ; regarder surtout l'espace utilisable après les reculs. Pas de seuil géométrique arrêté. |
| Arbres | Un arbre massif au centre peut compliquer l'implantation | Localisation, protection, périmètre racinaire et possibilités à examiner. Pas d'exclusion générale de toute parcelle arborée. |
| Reculs | Évaluer l'enveloppe d'implantation restante | Distances applicables aux limites, bâtiments, routes, forêts et eaux. Calcul géométrique ; ne pas soustraire des mètres à des m². |
| Pente | Apprécier la difficulté du projet et de l'accès | Choisir l'indicateur par parcelle et les seuils avec l'expert. Le raster disponible est en degrés ; les seuils du groupe sont en pourcentage. |
| Accès | Vérifier les possibilités réelles d'accès | Accès physique et juridique, servitudes et exigences techniques. Une proximité routière seule ne suffit pas. |
| Affectation | Identifier les usages autorisés et la règle de zone | Liste des zones ciblées à confirmer ; ne pas confondre faible emprise et droit à densifier. |
| Dangers et autres contraintes | Signaler les difficultés nécessitant un examen | Couches pertinentes et gravité à déterminer ; une présence ne justifie pas automatiquement une exclusion totale. |

La surface du terrain, les logements existants, l'ancienneté et les rénovations
peuvent compléter la lecture commerciale. Leurs seuils définitifs et leur rôle
par scénario restent à confirmer.

## Règles actuelles du prototype, conservées pour référence

Ces seuils sont exploratoires et ne constituent pas encore la configuration
finale issue de l'entretien :

- surface géométrique minimale : **1 000 m²** ;
- emprise cadastrale maximale : **20 %** de la surface géométrique ;
- logements maximum : **3**, avec au moins un logement renseigné et un bâtiment ;
- exclusion patrimoniale prioritaire, puis vérification des données incertaines,
  puis application des seuils.

**Le seuil exploratoire d'emprise de 20 % n'est pas le COS réglementaire de
0,20 évoqué pour la moyenne densité**, même si les valeurs numériques coïncident.

Les logements sont recalculés selon le rattachement déclaré au registre des
bâtiments. Sur la parcelle 607, 10 logements sont retenus ; les 9 déclarés sur
608 sont écartés du total et la divergence est signalée.

Référence de l'exécution sur 2 672 parcelles : 771 exclusions patrimoniales,
950 dossiers à vérifier, 860 hors cible et 91 candidates à approfondir.

## Données disponibles et manquantes

- CSV principal de 2 672 parcelles : présent dans le dépôt.
- Terrain swissALTI3D et pente calculée à 2 m : présents dans `data/terrain/`,
  sur un rectangle de travail de 6 × 8 km ; pas encore utilisés par le pipeline.
- Contours des parcelles : extraction exploratoire disponible dans
  `data/parcelles/` (2 672 EGRID retrouvés, 2 653 contours valides). Les anomalies
  géométriques et écarts de surface doivent être examinés avant les croisements,
  les mesures de forme, les pentes par parcelle et l'enveloppe après reculs.
- ISOS : références de sites voisins disponibles, périmètres et objectifs de
  sauvegarde à examiner. Aucune absence de protection n'est déduite des points.
- Propriété communale, arbres, accès, pleine terre réglementaire et règles
  détaillées par zone : sources et complétude à vérifier.

Voir [la documentation des données](data/README.md) pour les provenances et limites.

## Résultat attendu de l'outil

Pour chaque dossier prioritaire : identification de la parcelle, scénario à
examiner, signaux favorables, contraintes connues, données manquantes, sources
et première vérification utile. Une liste courte et explicable est préférable
à une précision artificielle.

Une donnée absente reste **« à vérifier »** ; elle ne devient pas un signal
favorable. Distinguer l'exclusion commerciale, la vérification nécessaire et
la priorité de prospection.

Aucun score final ni pondération n'est validé. Les seuils et points proposés
dans le PDF du groupe restent des hypothèses de travail. La revue documentaire
des 15 parcelles ne remplace pas les décisions commerciales de l'expert ; les
statuts du script ne sont pas des labels d'entraînement.

## Prochaines décisions avant le code

1. Valider les COS et leurs définitions dans les sources réglementaires.
2. Délimiter avec l'expert les secteurs centre-ville et lac à éviter.
3. Résoudre les anomalies des contours récupérés et obtenir les périmètres ISOS pertinents.
4. Faire qualifier des exemples par l'expert, dont l'échantillon de 15 parcelles :
   approfondir, écarter ou attendre, avec scénario et motif.
5. Fixer les seuils par scénario et le volume de dossiers qu'il souhaite examiner.
