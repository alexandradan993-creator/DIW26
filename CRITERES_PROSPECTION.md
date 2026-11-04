# Critères de prospection immobilière à Pully

## 1. Double temporalité et cadre réglementaire

Le projet structure son analyse autour de deux temporalités clés pour évaluer les parcelles :
- **Potentiel latent immédiat (Règlement actuel / PACom 1954) :** Analyse sous l'angle des dispositions en vigueur, incluant le COS (ex. 0,20 en zone de moyenne densité), la surface minimale de 600m² inclus, et les contraintes immédiates (reculs RDPPF, notes patrimoniales 1 à 3 exclues).
- **Scénario d'évolution (Horizon Pully 2040 / 2030) :** Intégration de la zone réservée communale (exigence de pleine terre : exclusion sous 50%, zone de malus entre 50% et 64%, confortable dès 65%) et des ratios de sous-exploitation (Rd).
- **Périmètre d'application :** L'analyse globale du projet s'exécute sur un ensemble de 2672 parcelles recensées sur le territoire de Pully.

---

## 2. Précision : forme et pourcentages
Deux indicateurs séparés sont calculés :
- **Part du terrain restant** après retrait uniforme simulé de 6m (hypothèse utilisateur à confirmer dans les règlements, sans exclusion automatique).
- **Marge d'emprise** par rapport au plafond COS simulé.

---

## 3. Synthèse des seuils validés (`criteres.json`)
- **Surface minimale :** 600m² (fort potentiel>1200m², moyen potentiel 600-1200m², faible/exclusion<600m²).
- **Emprise max / COS :** 0,20 (pour la moyenne densité).
- **Patrimoine :** Exclusion stricte des notes 1, 2 et 3 (les notes 4 à 7 sont prises en compte).
- **Pleine terre (zone réservée) :** Exclusion<50%, malus de 50% à 64%, confortable>=65%.
- **Ratio de sous-exploitation (Rd) :** Fort potentiel<35 %, moyen potentiel 35%-70%, saturé/exclu>70%.
- **Écart constructible (potentiel de densification) :** Potentiel>300m², moyen 50-300m², saturé<50m².
- **Reculs RDPPF :** Lisière de forêt (10m), cours d'eau (15m), route (3m).
- **Pente :** Faible (<10%), modérée (10-25%), forte (>25%).
- **Dangers et accès :** Exclusion en cas de zone à danger naturel avéré ou d'accès compliqué.
- **Énergie :** Critère énergétique entièrement exclu des filtres.

---

## 4. Objectif et utilisateur
Repérer les parcelles présentant les meilleurs signaux de potentiel pour l'expert, expliquer leur intérêt et indiquer les vérifications restantes. L'outil ne certifie ni la constructibilité ni les droits à bâtir et n'estime pas la valeur d'une parcelle. 
L'expert travaille seul, réalise actuellement une à deux expertises par mois et repère les occasions principalement lors de ses déplacements dans Pully. Il souhaite développer sa prospection auprès de clients privés. Le temps d'analyse non rémunéré après identification d'une parcelle constitue un coût important : l'outil doit faciliter la décision de poursuivre ou d'arrêter.

---

## 5. Scénarios recherchés
1. **Démolition-reconstruction :** Priorité principale.
2. **Extension :** Scénario complémentaire confirmé lors de l'entretien.
3. **Surélévation :** Intérêt indiqué, à traiter séparément avec vérification des hauteurs autorisées et de la structure.
Une difficulté propre à un scénario ne prouve pas l'absence de toute possibilité sur la parcelle. Les exclusions expriment la cible commerciale de l'expert, pas une déclaration générale d'inconstructibilité.

---

## 6. Exclusions commerciales retenues
- **Patrimoine :** Exclure dès qu'un bâtiment ou un site porte une note 1, 2 ou 3 (même provisoire).
- **ISOS :** Écarter les parcelles dans les périmètres ISOS concernés (pénalité).
- **Propriété communale :** Écarter si la commune est propriétaire.
- **Centre-ville et proximité du lac :** Éviter ces secteurs jugés complexes (à délimiter sur carte).
- **Affectation :** Exclusion si hors zone d'habitation (agricole, industrielle, forêt, domaine public).
- **Accès et dangers :** Exclusion en cas d'accès compliqué ou de présence de dangers naturels.

---

## 7. Signal principal : sous-exploitation apparente
Comparaison de l'emprise bâtie existante à une emprise théorique calculée à partir du COS (0,20 pour la moyenne densité).
- **Emprise théorique max** = surface de référence x COS
- **Ratio d'occupation (Rd)** = emprise existante comparable / emprise théorique max

---

## 8. Contraintes et signaux complémentaires
- **Pleine terre :** Prise en compte du seuil de 50% (zone réservée).
- **Forme et reculs :** Espace utilisable après reculs (forêt 10m, cours d'eau 15m, route 3m).
- **Arbres et accès :** Analyse au cas par cas, pas d'exclusion automatique sans vérification des données de terrain.