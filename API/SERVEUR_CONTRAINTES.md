# Fiches de contraintes et actualisation côté serveur

Premier lot : ISOS cantonal (404) et carte synthétique des dangers (422).
Les nouveaux modules sont séparés : **aucun fichier existant du commit du collègue
`712fc98` n'est modifié**, y compris `actualiser_pully.py`, son schéma, ses tests,
`run_pipeline.py` et `criteres_category.py`.

`observations_cantonales.py` adapte l'exporteur existant dans une instance de
module isolée, sans le modifier globalement. `service_contraintes.py` réutilise
`Etat`, son écriture atomique et le verrou. Il appelle la classification existante
sans changer ses règles et conserve les observations nouvelles séparément.

## Installation et démarrage

Depuis la racine, Python 3.10+ et un environnement virtuel actif :

```bash
python -m pip install -r API/requirements_contraintes.txt
python API/serveur_contraintes.py --reference API/bases/pully_parcelles_2026-11-04_1614.csv
```

Le serveur écoute uniquement sur la machine locale, port 8000 par défaut.
`--port` change ce port. `--stockage` change le dossier versionné, par défaut
`API/versions/` (déjà ignoré par Git). `--contours` sélectionne les contours ESRI
MN95 ; par défaut `data/parcelles/source_esri_lv95.json`.

Le serveur utilise une **base de référence choisie côté serveur**. Il actualise
les contraintes ISOS/dangers ; il ne relance pas toutes les collectes GEO.vd/SIGIP
ni ne régénère les contours du script du collègue à chaque clic. Pour une nouvelle
base, fournir la nouvelle référence et ses contours correspondants. Les valeurs
de pleine terre et autres inconnues ne sont pas inventées pendant l'import.

Ce serveur constitue la connexion à appeler depuis l'interface codée. Aucune
interface web n'existe actuellement dans ce dépôt : aucun bouton visuel n'a donc
été modifié. Figma ne lance pas directement ce serveur.

En développement, si l'interface est servie sur une autre origine, ajouter par
exemple `--origine-interface http://localhost:5173`. Seules les origines déclarées
sont acceptées pour cet usage ; sinon utiliser la même origine via un proxy.
Une mise en service distante avec authentification reste un chantier séparé.

## Routes

| Route | Réponse et rôle |
|---|---|
| `POST /actualisations` | Corps JSON `{}` ; 202 et `operation_id` pour une nouvelle tâche ; 200 et le même ID si une tâche serveur est déjà en cours |
| `GET /actualisations/etat` | Contenu actuel de `etat_actualisation.json` |
| `GET /actualisations/{operation_id}` | Historique/suivi de cette opération, sans le confondre avec une suivante |
| `GET /versions/active` | Identifiant de la version active |
| `GET /parcelles?version=…&offset=0&limit=50` | Liste paginée d'EGRID/numéros/statuts, avec son identifiant de version ; limite maximale 200 |
| `GET /parcelles/{egrid}?version=…` | **Fiche canonique commune à la Carte et la Liste**, avec contraintes, classement et annotations |

Carte et Liste doivent mémoriser la version renvoyée puis utiliser le **même
endpoint de fiche avec cette version**. Ne pas créer deux copies de fiche dans
deux services. Sans paramètre, une requête lit la version active au début de la
lecture ; l'identifiant renvoyé permet de figer les requêtes suivantes. Les anciennes
versions restent lisibles pendant et après une actualisation.

Les routes ne prennent ni URL, ni chemin de fichier, ni configuration arbitraire
du navigateur. Les EGRID et versions inconnus donnent 404. Une actualisation CLI
externe déjà en cours, qui ne possède pas d'identifiant serveur, donne 409 et se
suit via le fichier d'état existant ; elle n'est pas lancée une deuxième fois.

## Appel du bouton dans la future interface

Exemple de raccordement, pas une modification d'un frontend absent :

```javascript
async function actualiserDonnees(api = "") {
  const reponse = await fetch(`${api}/actualisations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
  const operation = await reponse.json();
  if (!reponse.ok) throw new Error(operation.erreur);
  return operation.operation_id;
}
```

Interroger ensuite `GET /actualisations/{id}`. Pendant `en_cours`, garder la
version affichée. À `termine`, proposer/recharger la version active **pour les
deux vues** ; à `aucun_changement`, garder leurs données et actualiser la date de
vérification ; à `erreur`, afficher le motif et conserver la version précédente.

## Contrat des observations

Chaque entrée de `fiche.contraintes` contient :

```json
{
  "valeur": null,
  "unite": "m",
  "etat": "a_verifier",
  "source": null,
  "date_donnee": null,
  "date_verification": null,
  "motif": "Source ou observation nécessaire non disponible."
}
```

États : `etabli`, `calcule`, `partiel`, `a_verifier`. Une valeur absente est `null`,
jamais convertie en zéro/false. Inversement, une absence de recouvrement calculée,
un degré nul établi ou une présence fausse établie conservent leur zéro/false.
L'identité technique du contenu et l'URL sont dans `source`. Une date de couche
non publiée reste `null` ; la date de téléchargement n'est pas sa date de validité.
Les dates `DATE_MODIF` restent disponibles par objet dans les attributs source.

Champs servis :

- `isos_presence`, `isos_surface_m2`, `isos_part_parcelle_pct`, `isos_objets`,
  `isos_couverture_pct` : site via `NOM_SITE`, attributs et objectifs bruts conservés.
  Une valeur `false` signifie absence de recouvrement **dans la couche cantonale
  404 intégralement collectée**, pas une certification générale d'absence de protection.
- `dangers_presence`, `dangers_classes`, `dangers_surface_m2`,
  `dangers_part_parcelle_pct`, `dangers_objets`, `dangers_couverture_pct` : classes
  et couverture de la carte, **y compris les polygones de danger nul**.
- `danger_part_risque_pct` : union des classes de danger R/B/J/H, distincte de la
  couverture cartographique. Si elle est positive en couverture incomplète, c'est
  une mesure partielle. Un zéro en zone non étudiée devient inconnu, pas « sans risque ».
- `danger_nul_etudie` : degré numérique `0` seulement lorsque toute la parcelle est
  recouverte par W, sans autre classe ; `danger_naturel_bloquant` reste inconnu.

La légende officielle de 422 distingue **R élevé, B moyen, J faible, H résiduel,
W nul, X information manquante, Z en révision**. Le périmètre interprétable est
l'union des polygones R/B/J/H/W ; X/Z ne deviennent pas des zones étudiées sans
danger. Hors de cette union, une absence de polygone reste « À vérifier ».
Un danger identifié sur une partie suffit à signaler sa présence, mais ne
supprime pas l'alerte de couverture partielle ni ne détermine son caractère bloquant.

## Version candidate, verrou et données de l'expert

1. Initialisation locale : snapshot du CSV et classement, contraintes inconnues.
2. Au clic : ID d'opération, verrou commun `actualisation.lock` et état `en_cours`.
3. Capture du CSV, des contours, des pentes et de la configuration ; collecte des
   couches par identifiants, contrôle des effectifs et subdivision des lots tronqués.
4. Croisements en MN95, union des intersections (sans double comptage), production
   de l'export et des fiches candidates. Le classement réutilise les seules règles
   de `criteres_category.py`, sans injecter les observations en critères éliminatoires.
5. Vérification des EGRID et relecture des fichiers ; renommage du dossier complet,
   puis remplacement atomique de **`version_active.json`** : les vues basculent par
   ce pointeur, pas fichier par fichier.

Une erreur laisse le pointeur précédent. Les versions antérieures ne sont pas
supprimées. Les EGRID absents de la nouvelle référence restent conservés avec
`presente_derniere_collecte=false` et une alerte ; aucun archivage automatique.
Les annotations sont lues dans `annotations_expert.json`, séparément et sans
écriture lors d'un recalcul. Dossiers/contacts peuvent y être conservés ; les
écrans et routes de gestion de ces annotations ne sont pas créés dans ce lot.

Un contrôle d'empreintes compare données, métadonnées, contours, référence, règles,
pentes et algorithmes. Les seules dates de vérification ne créent pas une nouvelle
version : `aucun_changement` conserve le pointeur et rafraîchit le suivi des sources.
Le serveur peut récupérer un verrou de sa propre opération après constat que le
processus a disparu, en marquant l'opération en erreur ; il ne supprime pas un
verrou CLI externe ou un processus vivant.

## Extension de `etat_actualisation.json`

Le contrat existant est conservé (`etape`, `sources`, `alertes`, `bilan`, dates,
`fichier`, `erreur`) et enrichi dans le nouveau service :

- `operation_id`, `mode: "contraintes"`, `version_active` ;
- `statut` : `en_cours`, `termine`, **`aucun_changement`**, `erreur` ;
- étapes supplémentaires : `Validation de la version candidate`, `Activation` ;
- bilan comprenant parcelles, ajoutées, absentes et états des croisements.

Les historiques d'opérations sont sous `operations/`. Le CLI du collègue garde
son comportement et son contrat d'origine. Le fichier de verrou n'est partagé
que si le CLI et le serveur utilisent le même `--sortie` / `--stockage`.

## Vérification réelle du 4 novembre 2026

Test effectué via `POST /actualisations`, attente via l'API, activation d'une
version **locale de validation**, puis lecture de la fiche 607. Base de référence :
`API/bases/pully_parcelles_2026-11-04_1614.csv`, contours ESRI existants du dépôt.
Les CSV originaux et le code des collègues n'ont pas été modifiés.

| Résultat | Nombre |
|---|---:|
| EGRID exportés et conservés | 2 672 |
| Objets ISOS téléchargés dans l'emprise | 115 |
| Objets dangers téléchargés, sur 22 lots | 4 206 |
| Parcelles avec recouvrement ISOS | 109 |
| Sans recouvrement dans la couche 404 consultée | 2 544 |
| ISOS non calculable (contour) | 19 |
| Danger identifié | 751 |
| Danger nul étudié sur toute la parcelle | 341 |
| Danger à vérifier | 1 580 |

Les 63 écarts de surface >1 % avec cette référence plus récente sont signalés.
Les formes/couvertures dépendent des contours locaux disponibles : une géométrie
invalidée reste inconnue et n'est pas réparée silencieusement. Vérifier quelques
EGRID dans les guichets avant toute utilisation décisionnelle.

Les requêtes publiques ont réellement abouti sans authentification sur
`www.ogc.vd.ch`. Les métadonnées ne publient pas de date/version de jeu ni
d'autorisation commerciale explicite : elles sont conservées comme inconnues,
avec empreintes techniques. Les conditions de réutilisation doivent être confirmées
via les fiches officielles [404](https://www.asitvd.ch/md/630) et
[422](https://viageo.ch/md/186ed094-00df-46d0-a070-6ba8c5417c2d). L'accès technique
public ne vaut pas validation de tous les usages commerciaux. Les données réelles
restent un export local de contrôle, pas de nouveaux fichiers bruts publiés dans Git.

## Sources/champs restant à intégrer

| Sujet | Source identifiée le 4 novembre | Limite / suite |
|---|---|---|
| Forêt | Couche cantonale 490 `vd.limite_foret`, polyligne | Valider la nature de la limite et le point de mesure avant distance ; recul juridique séparé |
| Eau | Couche 114 `vd.etendue_eau`, polygone ; espace réservé 538 identifié au catalogue | Étendue, axe du cours d'eau et espace réservé sont distincts ; fixer la mesure adaptée |
| Route | Couche 392 `vd.limite_construction_route_communale_cantonale`, polyligne | C'est une limite de construction, pas un axe ni une preuve d'accès ; réseau à choisir selon la mesure |
| Arbres | Couche 501 `vd.inventaire_cantonal_arbres_remarquables`, points | Pas équivalent à un inventaire communal exhaustif d'arbres classés ; autorisation et couverture à confirmer |
| Arbre important au centre | Observation datée manquante | Position/importance non déduites d'un inventaire partiel |
| Pleine terre | Plans/règles et surfaces validées manquants | Les espaces verts ne prouvent pas la pleine terre réglementaire |
| Accès | Observation physique et droits manquants | Aucune déduction depuis la route ; deux champs séparés |
| Propriété communale | Preuve autorisée par EGRID manquante | Ni affectation ni DP communal n'établissent le titulaire |

Ces champs sont déjà renvoyés avec `valeur=null`, unité, état et motif ; aucune
distance non calculée ou absence d'arbre n'est affichée comme zéro/false.

## Tests

```bash
python -m unittest discover -s API -p "test_*contraintes.py" -v
python API/test_actualiser_pully.py pully_parcelles.csv
```

18 tests ciblés passent à ce stade : exporteur existant + nouveau service. Ils
couvrent notamment recouvrement partiel, zéro confirmé, hors couverture, réponse
tronquée, calcul/activation en échec, absence conservée, annotations préservées,
double clic, aucun changement et vraie requête HTTP locale sur données synthétiques.
Le contrôle de référence de l'actualiseur est exécuté séparément, sans le modifier.
