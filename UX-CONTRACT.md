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

## Première publication privée

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
