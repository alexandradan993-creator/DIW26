# Classification configurable — première version à 600 m²

**Évolution :** [deux pourcentages et effet de la forme](FORME_ET_POURCENTAGES.md).
Le retrait uniforme de 6 m est une hypothèse configurable à confirmer.

Cette version accompagne la prospection de l'expert immobilier. Elle produit
une présélection expliquée et des vérifications, pas une certification de
constructibilité ou une estimation de valeur. Elle complète le prototype
historique `prospection.py`, conservé sans changement.

## Relancer depuis la racine du dépôt

Python 3.10 ou ultérieur, bibliothèque standard uniquement :

```bash
python code/classification.py --input pully_parcelles.csv --config code/filtres.json --pentes data/pentes_parcelles/pentes_parcelles.csv --output code/resultats_classification
```

Ouvrir les fichiers locaux produits :

- `classification.csv` : toutes les parcelles, décisions, motifs, données et inconnues ;
- `retenues_a_examiner.csv` : celles qui passent les filtres connus activés ;
- `resume.json` : effectifs, configuration complète, version et empreintes sources.

Ces sorties sont ignorées par Git, comme les résultats historiques. Un dossier
de sortie doit être utilisé par un seul processus à la fois. Les fichiers sont
préparés avant remplacement et le résumé est publié en dernier.

## Règles actives

| Élément | Comportement initial |
|---|---|
| Surface | Minimum **600 m² inclus** sur la surface géométrique disponible ; surface inconnue à vérifier |
| Patrimoine | Exclusion commerciale dès qu'une note 1, 2 ou 3, même provisoire, est détectée ; note 4 ne lève pas une exclusion ; notes inconnues à vérifier |
| Arbres centraux | Présence, absence signalée ou inconnu ; **aucune exclusion automatique** |
| COS | Simulation descriptive à 0,20 seulement pour le libellé exact « Zone de moyenne densité », avec couverture de zone ≥ 99 % et surfaces cohérentes |
| Pente | Information facultative importée avec ses statuts et alertes, sans pénalité ni filtre |

La table COS vient de l'entretien et doit être vérifiée dans les textes. Elle ne
certifie aucune règle réglementaire. Les COS déjà présents dans le CSV ne sont
pas appliqués automatiquement : certains concernent des plans spéciaux ou
d'autres zones sans règle validée. Une zone absente de la configuration reste
inconnue, sans coefficient de remplacement.

Le calcul est : `surface géométrique × COS configuré − emprise cadastrale`.
Il utilise donc des **approximations cadastrales** de la surface de référence
et de l'emprise réglementaire, pas des grandeurs juridiquement validées. Les
valeurs sont nommées `*_simule*` et les écarts négatifs restent visibles. Un
écart positif n'est pas un droit à bâtir. Aucun seuil de 50 ou 300 m² d'écart
ni aucune pondération n'est activé.

Les scénarios prioritaires restent la reconstruction, puis l'extension et la
surélévation ; leur faisabilité est à qualifier par l'expert. Le COS au sol ne
mesure pas à lui seul le potentiel d'une surélévation.

## Comprendre les statuts

- `exclue_cible` : au moins une exclusion connue (surface ou patrimoine).
  Tous les motifs détectés sont conservés même si d'autres données manquent.
- `a_verifier_filtres` : aucune exclusion certaine, mais information nécessaire
  incertaine ou incohérente (par exemple une note 0).
- `retenue_filtres_connus` : les filtres connus activés sont satisfaits.
  **Ce n'est pas une parcelle à fort potentiel démontré.**

Pour toutes les parcelles, `statut_potentiel` reste `non_etabli` tant que l'analyse
nécessaire n'est pas disponible. Les arbres inconnus et le COS non renseigné ne
sont pas transformés en signaux favorables. Ils apparaissent dans la fiche et
les vérifications restantes, même pour les parcelles retenues.

Les anciens seuils d'emprise maximale de 20 % et de trois logements ne sont
**pas actifs** dans cette nouvelle version. Les logements restent recalculés et
les anomalies de rattachement sont conservées comme informations, sans exclusion
automatique. Les règles historiques restent testables avec `prospection.py`.

## Modifier les filtres

Dans `filtres.json`, chaque section possède un booléen `actif`. Modifier
`surface.minimum_m2` change le seuil commercial. Modifier le contenu de
`cos.par_zone` permet de préparer d'autres simulations, avec un libellé exact,
une valeur et une source obligatoires. Mettre à jour `version` à chaque changement
de critères ; le résumé conserve aussi leur empreinte et leur contenu exact.

Les paramètres inattendus et types incorrects sont refusés pour ne pas ignorer
silencieusement une faute de frappe. Un nouveau critère doit être ajouté au code
avec sa validation, son explication et ses tests ; cette version ne fournit pas
encore d'éditeur graphique.

**Aucun critère énergétique ni score global n'existe dans cette version.**
L'année de construction n'a aucun effet sur la classification. Les besoins
géographiques futurs, ISOS, pleine terre, accès, dangers, propriété communale et
reculs ne sont pas implémentés comme filtres : ils restent explicitement à
vérifier. Aucun seuil réglementaire n'est inventé.

## Ajouter des observations sur les arbres

Copier `observations_arbres_modele.csv` dans un fichier local et le compléter :

```text
egrid,arbre_central,source
```

Une ligne par EGRID connu, avec `oui`/`non` (ou `true`/`false`, `1`/`0`) et une
source non vide telle qu'une visite datée. Un EGRID absent de ce fichier reste
inconnu. Une valeur illisible ou sans source reste à vérifier. Les doublons et
EGRID étrangers au CSV sont refusés. Ne pas remplir « non » faute d'observation.
Les observations et décisions humaines sont distinctes des résultats calculés.

Ajouter à la commande :

```bash
--observations-arbres chemin/observations_arbres.csv
```

Le modèle livré est vide ; aucun relevé d'arbres n'a été inventé.

## Vérifier

```bash
python -m unittest discover -s code -p "test_*.py" -v
```

Les tests couvrent la borne de 600 m², les notes provisoires et inconnues, les
arbres, les simulations COS et zones mixtes, les filtres désactivés, l'absence
d'effet de la pente et de l'année de construction et les entrées dupliquées.
