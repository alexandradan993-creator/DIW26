---
version: alpha
name: Foncimo Pully
description: Outil de prospection parcellaire pour un expert immobilier à Pully.
colors:
  primary: "#2a3c37"
  accent: "#d3de79"
  soft: "#eef4b8"
  background: "#f3f6f8"
  border: "#dfe3e5"
  text: "#2b2b2b"
typography:
  sans:
    fontFamily: "Kanit, system-ui, sans-serif"
rounded:
  DEFAULT: "0px"
omitted:
  - section: spacing
    reason: Géométrie existante de l'interface fournie, sans nouvelle échelle globale.
components:
  refresh:
    width: "250px"
---

# Interface Foncimo

## Overview

Application de travail en français pour la prospection à Pully, Suisse. Le plan cadastral coloré et les fiches constituent la signature existante. La version du 5 novembre reprend l'HTML du paquet `prototype-pully-verification.zip`, ses onglets Carte, Liste et Mes dossiers et ses contrôles natifs. Elle n'ajoute aucun score de constructibilité.

Le CSS de `interface/carte-pully.html` reste canonique (modèle B) : les variables `--foncimo-dark`, `--foncimo-accent`, `--foncimo-soft`, `--foncimo-paper`, `--foncimo-line`, `--foncimo-text` correspondent respectivement aux couleurs ci-dessus. Ce document décrit ces valeurs, sans deuxième génération de thème.

## Colors

Vert sombre pour la navigation et la marque, accent jaune vert pour les actions existantes. Les statuts rouge, jaune et vert restent accompagnés de libellés ; aucun nouveau sens métier n'est déduit de leur couleur. Les barres de défilement restent visibles, avec couleurs système en contraste forcé.

## Typography

Kanit avec repli système pour toutes les zones ; nombres en `fr-CH`, dates affichées en heure suisse. La feuille de police distante est facultative et son absence ne bloque pas le chargement des données.

## Layout

Conserver les panneaux existants, leurs recherches et leurs zones de défilement. Le message d'actualisation réserve cinq lignes ; le bouton garde son libellé et sa largeur pendant le traitement. Pas de nouveau thème mobile dans cette intégration.

## Elevation & Depth

Bordures existantes et dialogues natifs pour les fiches ; aucun nouvel effet d'élévation.

## Shapes

Bords droits issus de l'interface reçue. Contours cadastraux dessinés dans le canevas, sans réparation destinée à établir une constructibilité.

## Components

Le contrôleur `interface/actualisation.js` possède l'appel API, le suivi et le retour utilisateur commun. En cours : bouton désactivé, `aria-busy` et étape réelle. Réussite : rechargement de la version commune. Erreur : texte persistant et nouvelle tentative possible. Pas de progression inventée.

Fiches : les contraintes proviennent du même endpoint par EGRID, quelle que soit la vue d'origine. Valeur inconnue : « À vérifier » ; zéro ou faux confirmé : affichage conservé. Les sources et dates accompagnent les observations. Les nouveaux indicateurs cadastraux et simulations sont affichés dans leurs sections dédiées ; le bloc des huit anciennes contraintes non renseignées reste retiré, conformément à l'HTML reçu. La présence de forêt est signalée dans un encart en flux normal, sans superposition à la fiche.

Sélecteurs existants natifs, popup gérée par le système. Pas de nouvelle bibliothèque d'icônes. Aucune animation ajoutée ; réduction des mouvements respectée.

## Do's and Don'ts

- Conserver les notes et dossiers lors d'un rechargement.
- Présenter les simulations COS et retraits comme simulations.
- Ne pas annoncer de réussite après une erreur réseau.
- Ne pas remplacer une inconnue par zéro ni un danger observé par une exclusion juridique.

Les couleurs viennent exclusivement de `criteres_category.py`. Le lac
`CH298395274555` reste dans la base/API mais est masqué de la Carte et de la Liste,
comme dans le prototype fourni ; le bandeau distingue le total et les lignes affichées.

La section des archives dans Dossiers reprend le composant `.parcelFacts`, les
liens natifs et les dates en français suisse. Les notes GEO.vd sont présentées
dans le même composant des fiches, avec un avertissement sur les données SIGIP
historiques. Aucun nouveau thème ni nouvelle convention de navigation n'est ajouté.
