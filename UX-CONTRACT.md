# Contrat de l'interface Foncimo

Sources métier et techniques : `API/SERVEUR_CONTRAINTES.md`, `API/README.md`, `code/criteres_category.py`, `CRITERES_PROSPECTION.md` et demandes utilisateur. Les règles de classement de l'équipe sont conservées.

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Sélecteurs natifs de carte-pully.html | DESIGN.md | Popup du système | Test navigateur |
| Form | Formulaires existants de carte-pully.html | Interface fournie | Dossiers et filtres locaux | Syntaxe et test navigateur |
| Scrollbar | CSS global de carte-pully.html | DESIGN.md | Contraste forcé système | Inspection CSS |
| Toast | Contrôleur actualisation.js, messages persistants role=status | Contrat API | État général et état Données | Test navigateur |
| CRUD | Dossiers locaux existants | Interface fournie | Aucun écrasement par import serveur | Tests conservation |

## Actualisation

- Déclencheur : bouton « Actualiser les données », opération `POST /actualisations`.
- Double clic ou tâche déjà active : même identifiant d'opération côté serveur.
- Suivi : `GET /actualisations/{operation_id}`, état réel de `etat_actualisation.json`.
- Pendant : version affichée conservée. Navigation possible, pas de pourcentage inventé.
- Succès ou aucun changement : `GET /application/donnees` ; remplacement préparé puis appliqué aux données communes de la Carte et de la Liste.
- Fiche : `GET /parcelles/{EGRID}?version=...`, même version que la carte et la liste.
- Erreur ou délai réseau : message persistant, version précédente conservée ; reprise du suivi au prochain clic.
- Après 30 minutes de suivi, l'interface rend la main ; elle n'annule pas le travail serveur et propose de reprendre le même suivi.

## Données et dossiers

La base candidate n'est activée qu'après contrôles et calculs. Les champs personnels du CSV sont conservés par EGRID. Les annotations serveur restent séparées. Les dossiers et notes du prototype restent dans le stockage local du navigateur ; aucune synchronisation multiutilisateur n'est ajoutée. Un changement de domaine ou de port change ce stockage local : exporter les dossiers avant migration.

La carte et la liste sont une exploration locale de l'ensemble borné de Pully, chargé dans une seule réponse contrôlée. La recherche et les filtres existants sont transitoires, sans modification de la base ni persistance dans l'URL. Les dialogues et les suppressions de dossiers suivent le comportement existant fourni.

Les données descriptives ISOS et dangers ne modifient pas les exclusions métier. Les inconnues restent inconnues. L'outil ne certifie ni la constructibilité ni une valeur immobilière.

## Première publication privée sur l’offre gratuite

L'interface et l'API sont hébergées ensemble sur Render selon `render.yaml` et
`docs/MISE_EN_LIGNE.md`. Le serveur de publication demande une authentification
HTTP Basic, transportée en HTTPS par Render. Le mot de passe est généré côté
hébergeur et n'est jamais intégré dans l'interface. `/healthz` ne sert que le statut
du service et reste anonyme. Aucune gestion de comptes ou de rôles multiples
n'est ajoutée à cette première version.

## Contrat du HTML final — version 2

L'adaptateur `API/donnees_interface.py` fournit `schema_version: 2`. Chaque ligne
contient dix éléments dans `info` : surface, zone, motifs, vérifications, lien
RDPPF, mesures historiques, observations officielles, indicateurs cadastraux,
simulations du classificateur et indicateur de vigilance forestière. Les valeurs
des fiches et de l'export proviennent du même calcul et de la même version.
La couleur reste celle du classificateur de l'équipe.

Le voisinage forestier est calculé avec `compute_forest_neighbor_index` sur les
contours valides de cette version, convertis de MN95 vers le contrat WGS84 requis
par cette fonction. Les contours invalides ne sont pas réparés. Les pentes ne sont
plus transmises à cet argument ; elles restent un filtre d'affichage facultatif.

La fiche affiche les logements déclarés calculés par `classification.py`, avec
leurs divergences explicites. Le CSV brut reste conservé, y compris son total
géographique différent. Aucun nouveau droit de construire n'est déduit des simulations.

Au démarrage, une ancienne version d'interface est migrée dans une nouvelle version
locale complète, activée atomiquement. La migration conserve les données brutes,
observations et annotations ; aucune collecte n'est déclenchée. Les anciennes
mesures de pente exportées sont reprises si leur CSV n'était pas archivé. Une
version sans contour archivé ne peut être migrée en mélangeant les sources actuelles.
Une erreur de préparation laisse la version précédente active.

## Stockage temporaire de la démo gratuite

`render.yaml` sélectionne Free, sans disque persistant. Le bouton d’actualisation
conserve le même contrat, mais la dernière version valide n’est disponible que
tant que les fichiers du serveur existent. En cas de perte du stockage temporaire,
la base initiale est recréée depuis le CSV GitHub configuré. Les notes locales du
navigateur ne sont pas stockées dans ce répertoire ; les annotations serveur,
elles, n’ont pas de conservation durable sur cette offre.

## Repère Uzuverse

Les actions « Voir en 3D » de la Carte et de la fiche utilisent le même lien
Uzuverse `x/y/z`. Le point est celui de la version affichée, en MN95 ; son altitude
provient du raster local swissALTI3D LN02 (2019/2021), échantillonné au point.
Ce repère ne représente ni une hauteur de bâtiment ni une délimitation cadastrale
surlignée. L'altitude reste inconnue hors couverture ; aucun zéro n'est inventé.
L'enrichissement de la réponse API ne modifie pas les fichiers des versions.

## Actualisation GEO.vd uniquement et archives

Le parcours Web actualise désormais le cadastre, les bâtiments, les affectations,
les adresses, les observations ISOS/dangers et les notes des bâtiments/sites
recensés via GEO.vd. Aucun appel SIGIP n'est effectué par ce parcours. Les champs
SIGIP déjà présents sont conservés comme historiques non actualisés, de même que
les exclusions patrimoniales antérieures. Les nouvelles notes GEO.vd peuvent
ajouter une exclusion selon les critères inchangés ; elles ne lèvent pas seules
une ancienne exclusion SIGIP. Une première observation ne démontre aucune évolution.

Les observations patrimoniales GEO.vd sont stockées séparément, par EGRID, avec
les objets, notes, source et date de vérification. La comparaison se fait entre
deux observations GEO.vd de la même application ; la date de collecte n'est pas
une date de publication officielle. Carte et Liste utilisent la même version.

Données contient une section « Archives des bases de données », chargée via
GET /versions, avec date/heure Europe/Zurich, périmètre, base active et lien ZIP.
GET /versions/{version}/archive.zip exige la même authentification que les données.
L'archive contient la version serveur, pas les notes du navigateur ni le mot de
passe. Les échecs n'activent aucune base et ne créent pas d'archive visible ; une
vérification sans changement ne duplique pas la base. Ces archives serveur restent
temporaires sur Free ; le téléchargement permet une conservation par l'utilisateur.

Les lectures API reprennent au maximum deux fois après une interruption réseau ou
une réponse HTML temporaire. Une demande POST d’actualisation n’est jamais renvoyée
automatiquement : le prochain clic retrouve d’abord l’état serveur. Les fiches sont
lues individuellement avec un cache borné ; les accès simultanés ne chargent pas
plusieurs copies de la base complète.

Après une actualisation réussie, la section des archives ouverte dans Données
se recharge automatiquement. Son contenu est remplacé sans doublon ; une réponse
plus ancienne ne peut pas remplacer la liste de la nouvelle version.
