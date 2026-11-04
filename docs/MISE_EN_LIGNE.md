# Première version Foncimo sur Render

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
4. Render lit `render.yaml`. Examiner le service `foncimo-pully`, le plan **Starter**
   et le disque persistant **1 Go**. **Ces ressources sont payantes** : vérifier le
   montant indiqué par Render avant de valider. Une publication gratuite sans disque
   ne garantirait pas la conservation des versions ; elle n'est pas configurée ici.
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
- Stockage des versions sous `/var/data/foncimo/versions`, sur le disque persistant.
- Collecte réutilisant le script inchangé de l'équipe ; aucun changement des critères.
- Base initiale issue du CSV suivi dans le dépôt, sans collecte réseau au démarrage.
  Les observations ISOS/dangers sont inconnues tant qu'une actualisation n'a pas abouti.

Le disque contient les versions et les annotations serveur. Les notes et dossiers
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

Vérifier `FONCIMO_STORAGE=/var/data/foncimo/versions`, le montage du disque sur
`/var/data/foncimo` et la présence du mot de passe. Le serveur refuse de démarrer
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
- Version inchangée après arrêt et redémarrage sur le même stockage.
- Tests API, contrôle de la collecte et parcours Chromium du bouton.

Ces vérifications sont locales. Le Blueprint, le domaine HTTPS et l'accès SIGIP de
Render ne peuvent être contrôlés en conditions réelles qu'après création du service
par votre compte Render.
