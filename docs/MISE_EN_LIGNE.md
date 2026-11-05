# Première version gratuite Foncimo sur Render

Cette publication héberge **l'interface HTML issue de Figma et son API Python ensemble**.
Le dépôt contient le nécessaire dans `render.yaml`. Un fichier Figma publié seul ne
fait pas tourner Python. Aucun service Render n'a été créé automatiquement depuis ce chat.

## Publier depuis GitHub

1. Exporter les dossiers personnels de votre prototype avant de changer d'adresse.
   Les notes et dossiers du navigateur ne se transfèrent pas automatiquement vers
   un nouveau domaine. Le CSV d'import de dossiers reste disponible dans l'interface.
2. Se connecter à [Render](https://dashboard.render.com/), puis choisir **New → Blueprint**.
3. Connecter GitHub et sélectionner `alexandradan993-creator/DIW26`, branche `main`.
   Si le dépôt est privé, lui accorder l'accès depuis l'installation GitHub Render.
4. Render lit `render.yaml`. Vérifier le service `foncimo-pully`, le plan **Free**
   et l’absence de disque persistant. Ne pas valider une ressource Starter ou un
   disque payant. Si une facturation ou une carte est demandée, vérifier les
   conditions affichées par Render avant de poursuivre : ce dépôt ne garantit
   pas les conditions d’inscription de la plateforme.
5. Valider le Blueprint lorsque ces paramètres conviennent. Attendre la fin du build
   et l'état **Live**. Render fournit alors l'adresse HTTPS effective de l'application.
6. Dans le service, ouvrir **Environment** et consulter `FONCIMO_PASSWORD`, généré par
   Render. L'identifiant est `foncimo`. Ne pas copier le mot de passe dans GitHub,
   Figma ou le code frontend. Utiliser ces identifiants à l'ouverture de l'adresse.
7. Vérifier Carte, Liste, la fiche 607, puis lancer **Actualiser les données**.
   Attendre le résultat réel. Si une source échoue, la version précédente reste active ;
   l'interface montre l'erreur. Ne pas considérer un état **Live** comme la preuve
   que la collecte de toutes les sources a réussi.

Le déploiement automatique à chaque commit est désactivé. Pour publier une version
suivante, sélectionner **Manual Deploy → Deploy latest commit** dans Render.
La configuration garde une instance et un processus pour partager le verrou et le
stockage. Ne pas augmenter le nombre d'instances sans revoir ce fonctionnement.

## Ce qui est déjà préparé

- Python 3.12.14 et dépendances contrôlées par `API/contraintes_web.txt`.
- Serveur Waitress : `python API/application_web.py`, écoute sur le `PORT` de Render.
- Interface et API à la même origine : pas d'URL API à coller dans le navigateur.
- Authentification HTTP Basic sur les pages, les données et l'actualisation.
  Le contrôle `/healthz` est public et ne révèle ni parcelle ni identifiant de version.
- Stockage temporaire des versions sous `/tmp/foncimo/versions`, sans disque payant.
- Collecte réutilisant le script inchangé de l'équipe ; aucun changement des critères.
- Base initiale : `API/bases/pully_parcelles_2026-11-04_1614.csv`, configurée par
  `FONCIMO_REFERENCE`, sans collecte réseau au démarrage.
  Les observations ISOS/dangers sont inconnues tant qu'une actualisation n'a pas abouti.

Le stockage temporaire contient les versions et les annotations serveur. Il peut
être effacé lors d’un redémarrage, d’une mise en veille ou d’un redéploiement :
l’application repart alors du CSV GitHub configuré. Un simple redémarrage qui
conserve les fichiers peut conserver la version, mais ce n’est pas une garantie.
Les actualisations API ne sont pas enregistrées automatiquement sur GitHub.

Les notes et dossiers
créés dans l'interface reçue restent dans le navigateur : un autre ordinateur ne
les retrouvera pas automatiquement. La conservation doit être distinguée de la
synchronisation entre utilisateurs, qui n'est pas implémentée.

## Accès aux sources

La collecte appelle `www.ogc.vd.ch` et `www.sigip.ch` ; les calculs de pente utilisent
le raster déjà présent dans le dépôt. Le téléchargement d'un nouveau millésime du
modèle de terrain n'est pas encore automatisé.

Dans **l'environnement de ce chat**, GEO.vd répond mais SIGIP est refusé par le
proxy réseau. Le domaine SIGIP a été ajouté au **brouillon de configuration cloud**,
en conservant les autres domaines. Il faut examiner et enregistrer ce réglage dans
les paramètres de l'environnement, puis publier l'environnement pour l'appliquer.
Cela ne publie pas le site sur Render et ne configure pas le réseau de Render.

L'accès SIGIP depuis Render devra être testé par la première actualisation sur
l'hébergement réel. Aucune collecte complète GEO.vd/SIGIP n'est annoncée comme
validée tant que ce test n'a pas abouti. Les conditions de réutilisation restent
celles documentées dans `API/SERVEUR_CONTRAINTES.md` et les sources officielles.

## Si le déploiement ne démarre pas

Consulter **Logs** dans Render. Les commandes attendues sont :

```text
Build : python -m pip install -r API/requirements_web.txt
Start : python API/application_web.py
Health check : /healthz
```

Vérifier `FONCIMO_STORAGE=/tmp/foncimo/versions`, le plan Free sans disque
et la présence du mot de passe. Le serveur refuse de démarrer
avec un mot de passe absent ou inférieur à 16 caractères. La plateforme Render
fournit HTTPS ; ne pas exposer cette authentification sur Internet en HTTP simple.

Une erreur SIGIP pendant l'actualisation ne doit pas être corrigée en désactivant
TLS ou les contrôles de téléchargement. Garder la version valide et relever le
message d'erreur pour diagnostiquer l'accès ou le service officiel.

## Vérifications effectuées avant publication

- Installation propre des dépendances et `pip check`.
- Serveur Waitress réellement démarré avec une configuration analogue à Render.
- Refus de l'accès anonyme aux données ; `/healthz` fonctionnel.
- Jeu complet de 2 672 parcelles ; fiche 607 avec 10 logements déclarés.
- Version inchangée après arrêt et redémarrage tant que les fichiers sont conservés ;
  réinitialisation depuis le CSV GitHub vérifiée lorsque le stockage temporaire disparaît.
- Tests API, contrôle de la collecte et parcours Chromium du bouton.

Ces vérifications sont locales. Le Blueprint, le domaine HTTPS et l'accès SIGIP de
Render ne peuvent être contrôlés en conditions réelles qu'après création du service
par votre compte Render.

## Base API sélectionnée le 5 novembre 2026

Le CSV `API/bases/pully_parcelles_2026-11-04_1614.csv` devient la référence par défaut
des nouveaux stockages, en remplacement du choix initial `pully_parcelles.csv`.
L'ancien CSV reste intact. La référence et son empreinte SHA-256 sont inscrites
dans le manifeste de la version initiale. `render.yaml` fixe explicitement ce choix.

Cette sélection ne remplace pas une version déjà active sur un disque existant.
Pour tester avant le premier déploiement, un stockage séparé a été préparé sous
`API/versions/base_2026-11-04_1614` ; les anciens dossiers restent conservés.
Commande de démarrage local, en arrêtant d'abord uniquement votre ancienne instance :

```bash
python API/serveur_contraintes.py --stockage API/versions/base_2026-11-04_1614
```

La base contient 2 672 EGRID uniques et les 76 colonnes attendues. Avec les critères
`49566c2`, elle donne 291 vertes, 526 jaunes et 1 855 rouges, comme l'ancien CSV.
La fiche calculée 607 retient 10 logements déclarés ; le total géographique brut
reste 19 dans la source, sans être écrasé. Le dernier HTML fourni est désormais raccordé au contrat d'interface version 2 ;
les données ne sont plus incorporées dans le HTML. La mise en ligne reste à effectuer
dans Render, puis l'accès aux sources officielles doit être vérifié sur cet hébergement.

## HTML final intégré

La version de `prototype-pully-verification.zip` est maintenant servie par le
serveur, avec son bouton relié à l'API, les indicateurs cadastraux et les simulations
de surélévation. Les logements de la fiche 607 sont corrigés à 10 déclarés. Le lac
est masqué de l'affichage mais conservé dans la base. Les anciennes versions de
fiches sont migrées localement au nouveau format, sans supprimer les notes.

Avant de considérer l'actualisation complète comme opérationnelle sur Render,
cliquer sur le bouton et attendre une réponse `termine` ou `aucun_changement` :
l'accès SIGIP reste bloqué dans l'environnement de ce chat malgré son ajout
au brouillon. Aucun déploiement Render ni réussite réseau SIGIP ne sont attestés
par les seuls tests locaux de l'interface.

## Actualisation sur l’offre gratuite

Le bouton et le serveur Python restent actifs sur Free. Le serveur télécharge les
sources accessibles, recalcule les critères et active une nouvelle version après
contrôle, comme auparavant. Si le téléchargement échoue, la dernière version valide
présente sur ce serveur reste active.

La gratuité ne garantit ni l’accès à chaque source ni des ressources suffisantes
pour la collecte complète : ce test reste nécessaire après le déploiement réel.
Le serveur peut se mettre en veille ; la première ouverture peut être lente et
une interruption pendant un calcul peut obliger à relancer l’actualisation.
Il n’y a ni tâche mensuelle automatique ni sauvegarde persistante ajoutée.

Si un Blueprint payant a déjà été préparé dans votre compte, ne supposez pas que
sa configuration a changé : resynchroniser le Blueprint depuis `main` et vérifier
le plan Free et l’absence de disque avant de valider. Si un service payant existe
déjà, examiner ses ressources et sa facturation dans Render ; ce changement GitHub
ne supprime ni ne rembourse automatiquement des ressources existantes.

## Correctif mémoire après le premier essai Render Free

Le premier build du commit `89f99d4` réussit, mais Render arrête l'initialisation
pour dépassement de 512 Mio. Le pic est reproduit localement à environ 592 Mio :
la sérialisation complète des fiches JSON crée des copies temporaires volumineuses.
`write_json` écrit désormais progressivement dans un fichier temporaire, puis
remplace atomiquement la destination. Une erreur de sérialisation conserve le
fichier précédent. Un verrou d'initialisation appartenant à un processus mort peut
être repris ; un propriétaire encore actif conserve son verrou. Aucun dossier
candidat ou jeu de données n'est supprimé par cette reprise.

Validation locale après correctif : 36 tests API/collecte/stockage passent ;
initialisation complète à environ 249 Mio de pic, puis lecture de l'interface et
d'une fiche à environ 429 Mio. Les 2 672 EGRID et les couleurs 291/526/1 855 sont
conservés ; la fiche 607 affiche 10 logements et la divergence de rattachement 608.
Ces mesures locales ne prouvent pas que la collecte réseau complète tient sur Free.
Les règles métier, l'authentification et les contrôles de collecte restent inchangés.

## Diagnostic des téléchargements de l'actualisation

Le suivi serveur expose maintenant `telechargement` (source, couche, action,
numéro de requête, tentative, état, octets reçus et durée) et
`progression_reseau`. L'étape affichée par l'interface reprend la source et la
couche en cours. Les logs `Foncimo collecte` sont immédiatement écrits avec
l'identifiant d'opération ; ils ne contiennent ni URL complète, ni en-tête,
ni secret, ni contenu cadastral. Les inventaires et lots ArcGIS contrôlés ainsi
que les effectifs SIGIP reçus sont consignés au fur et à mesure. Une réponse
reçue n'est pas présentée comme une validation finale de la collecte.

Le transport de l'adaptateur applicatif utilise un processus Python temporaire
par requête : limite effective de 45 secondes connexion et lecture comprises,
deux tentatives maximum sur dépassement de délai, attente réseau de 20 secondes
et réponse limitée à 64 Mio. Le processus est arrêté et attendu après dépassement,
puis ses fichiers temporaires sont supprimés. La récupération de base et celle
des observations cantonales sont chacune bornées à 20 minutes au travers de
leurs requêtes. Cette limite ne couvre pas les calculs géométriques ultérieurs.
TLS et les contrôles de complétude restent actifs. Le collecteur métier de
l'équipe n'est pas modifié. Les tests injectent leur transport synthétique.

En cas d'échec, l'opération passe en erreur avec source/couche/action ; aucune
version partielle n'est activée et la version valide présente reste utilisée.
Après arrêt du serveur ou perte de /tmp, la reprise et les limites de rétention
Free restent celles décrites plus haut. Ce suivi ne garantit pas qu'une collecte
complète tienne en mémoire sur Free.

### SIGIP lent : subdivision des requêtes

L'adaptateur limite désormais les lots WFS à 500 objets. Si une requête dépasse
son délai, il découpe son emprise en quatre sous-zones et dédoublonne les objets
par identifiant GML. Le nombre total est toujours comparé au `resultType=hits`
de l'emprise initiale. Le découpage s'arrête au niveau 6 et respecte la limite
globale de récupération ; une indisponibilité persistante provoque une erreur,
jamais l'omission d'une couche patrimoniale. Ce correctif est testé sur des
réponses synthétiques ; la réussite réelle de SIGIP sur Render reste à vérifier.

### Repère du lien Uzuverse

L'API enrichit l'export d'interface avec l'altitude du raster local au point MN95
représentatif de chaque parcelle. Le bouton existant retrouve ainsi son format
`https://pully.uzuverse.com/?x=...&y=...&z=...`, qui affiche un repère de coordonnées,
au lieu du seul positionnement de caméra `lon/lat/alt`. Le point de contrôle
2540003.59 / 1151259.87 donne 412.79 m, conformément à la capture du prototype.
Les versions déjà stockées bénéficient aussi de cet enrichissement à la lecture,
sans migration de données. Un repère n'est pas un contour cadastral surligné.

## Parcours Web GEO.vd uniquement

Suite au choix utilisateur, `application_web.py` et le lanceur local utilisent
`collecter_geovd`. L'adaptateur isole le collecteur d'équipe et désactive ses
appels SIGIP sans modifier son fichier ni les critères. Les données SIGIP déjà
présentes sont conservées et signalées comme historiques non actualisées.
Les nouvelles parcelles ne reçoivent pas de faux zéros pour ces données absentes.

Le patrimoine est téléchargé séparément depuis `vd.batiment_recense` (316) et
`vd.site` (402), avec inventaires, lots et comptages vérifiés, en MN95. Les notes
NOTE_CARTO/NOTE_DETAIL sont rattachées aux contours de cette version avec le seuil
existant de 0,1 m². Toute note inconnue fait échouer le candidat. Les notes GEO.vd
et leur comparaison sont archivées dans `patrimoine_geovd.json` et les fiches.
Les anciennes notes bloquantes ne sont pas effacées. Le bilan indique le périmètre
GEO.vd et distingue la première observation des évolutions réellement observées.

Dans Dossiers, chaque version valide disponible est listée avec date et heure,
périmètre et lien ZIP authentifié. Le ZIP contient tous les fichiers de cette
version, dont parcelles, fiches, contours, manifeste et observations. Les notes
personnelles du navigateur et annotations serveur séparées ne sont pas incluses.
Sur Free, télécharger les ZIP avant une mise en veille/redéploiement pour les
conserver ; aucune conservation durable n'est ajoutée sur Render.

Un test réel peut être lancé une seule fois au démarrage durant une fenêtre
explicite avec `FONCIMO_TEST_GEOVD_UNTIL` (époque UTC en secondes). En dehors de
cette fenêtre, seul le bouton authentifié déclenche une actualisation.
