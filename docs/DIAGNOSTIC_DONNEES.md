# Diagnostic et plan d'intégration des données de Pully

Vérification du **3 novembre 2026**, sur le dépôt au commit `1fa3e61` avant
correction documentaire du README. Aucun nouveau filtre n'est activé par ce plan.
Le seuil courant est **600 m² inclus**, et non les 1 000 m² du prototype historique.

## Diagnostic exécuté

Lecture de `code/classification.py`, `code/prospection.py`, `code/filtres.json`,
`code/CLASSIFICATION.md`, `CRITERES_PROSPECTION.md`, des documentations et
métadonnées de `data/`, et examen des en-têtes et valeurs du CSV principal,
des CSV de formes et pentes et du modèle d'observation des arbres.

Les **25 tests** du dossier `code/` passent, dont les quatre géométriques avec
Shapely/pyproj installés. Une exécution isolée dans `/tmp` reproduit :
1 345 `exclue_cible`, 126 `a_verifier_filtres`, 1 201 `retenue_filtres_connus`.
Les 2 672 dossiers gardent `statut_potentiel=non_etabli`. La reconstruction
reste le scénario principal ; extension et surélévation doivent être étudiées
séparément, notamment parce que le COS au sol ne mesure pas les étages réalisables.

Principaux constats nouveaux :

- **Aucun champ de propriétaire** ni preuve foncière. `genre_parcelle` contient
  2 316 « parcelle privée », 273 « DP communal », 61 « DP cantonal » et 22
  « DDP superficie ». Aucun de ces libellés ne certifie le titulaire du droit.
- **Les données réglementaires sont déjà partiellement présentes** :
  `zones_affectation_json` est non vide pour 2 671 parcelles et contient des codes,
  dates, statuts juridiques, COS et parts d'intersection. Le code utilise seulement
  une sélection des champs dominants, pas un moteur juridique complet.
- `sigip_pga_zones_affectation_json` est non vide pour **2 500 parcelles** et
  contient **71 URL documentaires distinctes** de plans, règlements ou addenda.
  Les exploiter avant de rechercher de nouvelles données équivalentes.
- **637 parcelles** ont une part de zone dominante inférieure à 99 % ou inconnue.
  Une règle du seul libellé dominant ne suffit pas à les interpréter.
- `sigip_zone_reservee_json` concerne **2 094 parcelles**, pour 2 157 objets
  après intersections. Ils renseignent une enquête au **7 juin 2025**, mais
  ni approbation, ni entrée en vigueur, ni date de fin. Une intersection n'établit
  donc pas une restriction actuellement opposable. Ne pas additionner les surfaces
  d'objets qui peuvent se chevaucher.
- `pleine_terre_reglementaire_m2`, `surface_plancher_verifiee_m2`,
  `decision_conti` et `motif_conti` sont **vides sur les 2 672 lignes**.
  Le modèle arbres ne contient aucune observation et ne possède pas encore de
  champ de date distinct. Les décisions de l'expert ne sont donc pas collectées.
- Le `statut_potentiel` du CSV brut vaut `a_evaluer` sur toutes les lignes.
  Les statuts calculés se trouvent dans l'export de classification, pas dans ce champ.

## Sources et accès : ce qui a réellement été vérifié

Les liens ci-dessous sont officiels ou proviennent directement des attributs
sources. Un lien disponible dans les données n'est pas une preuve que son
document a été lu ou que sa règle est encore en vigueur.

- **[CadastralWebMap, métadonnées](https://api3.geo.admin.ch/rest/services/api/MapServer/ch.kantone.cadastralwebmap-farbe/legend?lang=fr)** : réponse HTTP 200 le 3 novembre 2026 ; actualité affichée **2 novembre 2026**. Service cartographique à contenu réduit, pas la MO complète. Les conditions du fournisseur et d'extraction doivent être vérifiées avant redistribution ; la consultation technique ne prouve pas une licence ouverte.
- **[Catalogue ISOS](https://data.geo.admin.ch/api/stac/v0.9/collections/ch.bak.bundesinventar-schuetzenswerte-ortsbilder)** : HTTP 200 le 3 novembre ; millésime de collection **1er novembre 2026**, licence déclarée `proprietary`, renvoi [terms_by_ask](https://opendata.swiss/en/terms-of-use/#terms_by_ask). Les PDF font foi selon le catalogue. Aucun droit de réutilisation commerciale libre n'est déduit.
- Les tentatives vers `www.vd.ch`, `www.geo.vd.ch`, `www.pully.ch`,
  `www.rdppf.vd.ch`, `www.recensementarchitectural.vd.ch` et `api.isos.bak.admin.ch`
  ont reçu **« Tunnel connection failed: 403 Forbidden »** le 3 novembre.
  Il s'agit du **proxy de cet environnement**, pas d'un refus d'accès établi
  par le registre foncier ou d'une preuve que les documents sont privés.
  La liste réseau actuellement autorisée ne comprend que `api3.geo.admin.ch`
  et `data.geo.admin.ch`, en plus des domaines techniques prédéfinis.
- Le plan ne remplace pas les paramètres réseau. Pour une collecte ultérieure,
  ajouter ces six domaines aux accès autorisés, en conservant les autres domaines,
  puis vérifier les réponses effectives. Des conditions d'accès propres au
  fournisseur peuvent encore s'appliquer après cette correction.

## Tableau des treize axes

« ND » = date non démontrée par les éléments consultés. La vérification de ce
diagnostic date du **03/11/2026** ; elle ne rajeunit pas la donnée. Pour les
sources bloquées, la vérification porte sur l'accès et les références existantes,
pas sur le contenu juridique actuel.

| Axe | Déjà présent / réellement utilisé | À obtenir ou préciser | Source officielle et lien | Accès / réutilisation | Date de la donnée | Rattachement | Contrôles nécessaires |
|---|---|---|---|---|---|---|---|
| **1. Propriété communale, priorité** | Aucun propriétaire ; genre foncier seulement. Pas de filtre propriétaire dans `classification.py`. | Preuve actuelle que la Commune de Pully détient le droit identifié ; titulaires, quotes-parts, fonds/support et DDP. | [Registre foncier vaudois](https://www.vd.ch/territoire-et-construction/registre-foncier) : point d'entrée à confirmer après déblocage ; demande au RF compétent et à la Commune de Pully pour une liste attestée par EGRID. | Aucun flux ouvert par EGRID confirmé. Vérifier consultation, éventuel accès professionnel, intérêt légitime/mandat si requis, extraction en lot et droit de réutilisation auprès du RF ; ne pas supposer qu'une connexion suffit à autoriser une collecte massive. | ND ; exiger date de constat/extrait et, si disponible, validité du droit. | EGRID du droit, EGRID du fonds support, ID officiel du titulaire, rôle et quote-part. | Ne jamais déduire le propriétaire de DP, utilité publique ou d'une URL RF/RDPPF. Distinguer commune, canton et entités liées. Copropriétés et DDP : contrôle séparé. |
| **2. Taille et contours** | Surface géométrique et MO sur 2 672 lignes ; RF sur 2 338. 2 653 contours valides, 19 invalides. Surface géométrique utilisée avec seuil ≥ 600. | Réconcilier les surfaces, obtenir la géométrie complète ou confirmation pour les cas litigieux. | [CadastralWebMap](https://api3.geo.admin.ch/rest/services/api/MapServer/ch.kantone.cadastralwebmap-farbe), [GéoVD](https://www.geo.vd.ch/) / mensuration officielle. | API fédérale accessible ; MO complète et licence à demander/vérifier auprès du fournisseur cantonal. | Service 02/11/2026, extraction 03/11 ; date propre des surfaces du CSV ND. | EGRID ; numéro + commune seulement en contrôle secondaire. | 61 écarts >1 % entre contour et CSV ; écarts MO/géométrie >1 % sur 39 lignes, RF/géométrie sur 208 des lignes renseignées. Ne pas remplacer automatiquement ; 19 contours non réparés. |
| **3. Patrimoine existant et provisoire** | Notes synthétiques et objets bâtiments/sites/ponctuels. 459 parcelles avec objets bâtiments existants, 618 provisoires, 296 sites existants, 236 sites provisoires. Exclusion 1–3 déjà active. | Fraîcheur, géométries sources et rattachements, éventuelles contradictions ; version officielle des inventaires. | [Recensement architectural VD](https://www.recensementarchitectural.vd.ch/territoire/recensementarchitectural/), inventaires provisoires via [Commune de Pully](https://www.pully.ch/) / service communal concerné. | Références disponibles dans le CSV ; accès bloqué ici. Conditions d'extraction, photos et fiches à vérifier par couche ; pas de licence globale présumée. | Actualité propre des couches ND ; date d'import historique ne suffit pas. | EGRID par intersection ; num_eca, fiche, objet et commune pour contrôle. | Union des couches, sans écrasement d'une note 3 par une 4 provisoire. `0`, JSON illisible, notes contradictoires : vérification, avec exclusion conservée si note bloquante connue. |
| **4. COS et écart apparent** | 1 598 COS bruts de 0,20, non validés. Simulation configurée uniquement pour « Zone de moyenne densité », part ≥99 %, surfaces cohérentes : 681 calculs, y compris des dossiers exclus par d'autres filtres. Liens réglementaires déjà présents. | Plans/règlements en vigueur, plans spéciaux, définitions des surfaces et emprises ; éventuels coefficients par secteur. | [RCATC lié dans le CSV](https://www.pully.ch/media/kx2bz5gf/rcatc-2017-final-2017-11-03.pdf), [exemple PPA Cerisiers–Combes](https://www.pully.ch/media/vqgbg1yv/36_ppa_cerisiers-combes_pplusr.pdf), [RDPPF VD](https://www.rdppf.vd.ch/). | PDF non lus en direct car proxy ; statut, droits et versions à vérifier avant transcription. Le nom d'un PDF ne démontre pas sa validité actuelle. | Hypothèse entretien ; dates d'entrée/sortie variables dans les objets, à contrôler individuellement. | EGRID → portions de zones → ID plan/règle/article/version. | Emprise cadastrale ≠ emprise réglementaire ≠ plancher. Conserver écarts négatifs ; pas de COS universel, ni exclusion automatique <50 m². |
| **5. Arbre central** | Modèle `egrid,arbre_central,source` vide ; état inconnu sur toutes les parcelles. 114 parcelles avec jardins historiques : ce n'est pas un inventaire d'arbres centraux. | Inventaire arboré s'il existe et est accessible, protections, positions, dimensions, date d'observation ; règle de centralité à définir. | [Commune de Pully](https://www.pully.ch/) : service compétent pour arbres/protection ; [GéoVD](https://www.geo.vd.ch/) pour rechercher les couches. Aucune API exhaustive d'arbres privés vérifiée. | Demander couverture public/privé et licence ; absence d'objet d'inventaire ≠ absence d'arbre. | ND ; date terrain obligatoire à ajouter. | Coordonnées/ID arbre puis EGRID ; observation humaine directement par EGRID. | Importance, couronne/racines, protection, distance à l'enveloppe. États présence signalée / absence signalée / inconnu, pas d'exclusion automatique. |
| **6. Pleine terre / zone réservée** | Pleine terre réglementaire vide partout ; surfaces vertes sur 2 435 parcelles, dures sur 891 ; objets ZR sur 2 094. Non utilisés comme filtre. | Texte applicable, opposabilité/dates, définition de pleine terre, sous-sol, surfaces légalement comptables ; bornes 64–65 à arbitrer. | [Document ZR référencé](https://www.rdppf.vd.ch/ws/utilities/GetDocuments.ashx?rep=AMENAGEMENT&nom=5590_230484_PR01.pdf), [Pully](https://www.pully.ch/), [GéoVD](https://www.geo.vd.ch/). | Références connues, lecture bloquée ; données de couverture et droits à vérifier. | Enquête 07/06/2025 dans le CSV ; approbation, entrée et fin absentes. Actualité des surfaces vertes ND. | EGRID + intersection du périmètre/règle, unions géométriques sans double compte. | Ne pas assimiler végétation et pleine terre ; ni 50 % de pleine terre à 50 % constructibles. Aucune exclusion <50 % avant validation. |
| **7. Ratio d'occupation** | `emprise_batie_m2`, surface et ratio cadastral calculable déjà disponibles ; pas de filtre de ratio dans la nouvelle version. | Définir le dénominateur retenu et la comparabilité des emprises ; validation des tranches. | MO via [GéoVD](https://www.geo.vd.ch/) et [CadastralWebMap](https://api3.geo.admin.ch/rest/services/api/MapServer/ch.kantone.cadastralwebmap-farbe) ; règles locales pour les définitions. | Réemploi interne possible immédiatement pour décrire le CSV ; redistribution/source à vérifier. | Celle des deux mesures, ND si non tracée ; ne pas substituer la date du calcul. | EGRID ; bâtiments/EGID et intersections pour audit. | 0 ≤ bâti ≤ terrain, pas de division par zéro. Bâti/terrain différent de bâti/max COS. Tranches <35 / 35–70 inclus / >70 descriptives à valider. Anciens 20 % et trois logements inactifs. |
| **8. Servitudes, reculs, ISOS** | Forêts sur 150 parcelles, eaux sur 78 : objets de couverture, sans limites juridiques complètes. Retrait uniforme 6 m simulé, formes pour 2 653 ; quatre points ISOS voisins, aucun périmètre exploitable confirmé. | Limites forestières légales, espaces réservés aux eaux, limites de construction routières, servitudes accessibles, géométries ISOS et objectifs. | [RDPPF VD](https://www.rdppf.vd.ch/), [GéoVD](https://www.geo.vd.ch/), RF pour servitudes ; [catalogue ISOS](https://data.geo.admin.ch/api/stac/v0.9/collections/ch.bak.bundesinventar-schuetzenswerte-ortsbilder), [PDF Lausanne cité](https://api.isos.bak.admin.ch/ob/4397/doc/ISOS_4397.pdf). | Catalogue accessible ; PDF/cantonal bloqués ici. ISOS `terms_by_ask` ; droits des autres couches et accès aux actes RF à confirmer. | ISOS collection 01/11/2026, relevés voisins anciens ; dates de chaque couche juridique ND. Retrait 6 m = hypothèse, sans date de validité réglementaire. | EGRID + intersection/ID objet ; servitudes liées au droit. | 10 m forêt/15 m eau/3 m route non validés ; préciser la ligne de mesure. Calcul de bandes géométriques, pas soustraction de mètres à des m². Un point n'est pas un périmètre ; couverture insuffisante → inconnu, pas hors ISOS. Traitement commercial ISOS à valider. |
| **9. Pente** | Raster 2 m et CSV par EGRID présents ; 2 591 calculés sans alerte, 61 à vérifier, 20 non calculables. Jointure facultative `--pentes`, purement descriptive. | Aucune nouvelle collecte nécessaire pour commencer ; suivre prochains millésimes et améliorer les cas mal couverts si utile. | [swissALTI3D, catalogue officiel](https://data.geo.admin.ch/api/stac/v0.9/collections/ch.swisstopo.swissalti3d). | Données déjà téléchargées ; vérifier conditions swisstopo et attribution ; métadonnées conservées, champ de licence non réinterprété. | Terrain 2019/2021 ; calcul 03/11/2026. | EGRID + pixels dans le contour MN95 ; altitude LN02. | Degrés ≠ pourcentage ; médiane et parts <10 / 10–25 inclus / >25 ; NoData jamais zéro. 7469 sans pixel, DP 5590 partiellement couvert. Aucune pénalité. |
| **10. Affectation / densité** | Zones cantonales détaillées sur 2 671, plans SIGIP sur 2 500 ; codes, libellés exacts et surfaces d'intersection déjà dans le CSV. Seul le libellé dominant sert à la simulation COS. | Géométries et statut courant, correspondance usages/densité vérifiée, hiérarchie des plans spéciaux et portions mixtes. | [GéoVD](https://www.geo.vd.ch/), [RDPPF VD](https://www.rdppf.vd.ch/), documents [Pully](https://www.pully.ch/) déjà référencés. | Exploiter attributs locaux d'abord ; API, licence et statut des textes après déblocage. | Champs DATE_EV/DATE_FIN par objet ; pas de date unique certifiée. | EGRID → plusieurs zones et parts ; ID/codes/version, pas seulement texte dominant. | Habitation permise / non permise / mixte à vérifier ; villas/moyenne/forte/autre/inconnue sans potentiel déduit. Recouvrement, trous et sommes de parts. |
| **11. Accès routier** | Adresses et surfaces dures disponibles ; aucune preuve structurée d'accès physique ou juridique. Pas de filtre. | Voirie/raccordement, entrées, passage, actes et capacité technique d'accès. | [GéoVD](https://www.geo.vd.ch/), service communal de voirie [Pully](https://www.pully.ch/), RF pour droits et servitudes. | Réseau cartographique ≠ droit d'accès. Accès/licence et consultation des actes à confirmer. | ND pour réseau local et droits ; date visite à ajouter. | EGRID, segment routier/entrée, droit et acte correspondant. | Proximité ≠ accès direct ; séparer physique/juridique et direct/compliqué/inconnu. Exclusion si compliqué non validée. |
| **12. Dangers naturels** | Aucune couche de danger dédiée ni classe structurée dans le CSV. Pas de filtre. | Cartes officielles par aléa, couverture effectivement étudiée, classes, règles et versions. | [GéoVD](https://www.geo.vd.ch/) et services cantonaux des dangers naturels via [État de Vaud](https://www.vd.ch/). Couche exacte et service à identifier, pas encore confirmés. | Demander catalogue/métadonnées, licence, couverture et possibilité d'extraction ; accès portail bloqué ici. | ND ; exiger date d'étude, publication et validité/version. | EGRID + intersection par aléa/classe. | Sans polygone ne signifie sans danger que si couverture démontrée ; hors couverture → inconnu. Aucun danger identifié ≠ certitude d'absence ; pas d'exclusion générale automatique. |
| **13. Centre-ville / lac** | Aucun périmètre commercial validé. Les noms de zones ne le remplacent pas. | Dessin avec l'expert, raison, version, règle de croisement et éventuelles tolérances. | Fonds officiels [GéoVD](https://www.geo.vd.ch/) et [Pully](https://www.pully.ch/) ; décision de ciblage provenant de l'expert, pas d'une source réglementaire. | Vérifier droit du fond ; le périmètre commercial doit être validé par l'expert. | ND avant validation ; date/version à enregistrer ensuite. | EGRID + intersection ou part de surface selon règle approuvée. | Pas de rayon inventé ni d'exclusion par simple proximité du lac. Garder désactivé jusqu'à validation. |

## Priorité foncière : démarche et règle proposée

1. Après déblocage réseau, vérifier le canal officiel de consultation RF et
   l'office compétent pour Pully. Demander si un export autorisé par EGRID est
   possible, avec les dates, catégories de droit, titulaires et quotes-parts.
   Si le canal est restreint, suivre la demande officielle d'accès ou d'extrait,
   avec mandat/justification si exigés ; pas de contournement ou collecte non autorisée.
2. Solliciter, sans envoyer de demande automatiquement depuis cet outil, une
   liste communale attestée et datée des EGRID détenus, en distinguant le fonds
   et les droits de superficie. Faire confirmer sa portée et sa réutilisation.
3. Une preuve de propriété de la **Commune de Pully** sur le droit concerné
   déclenche la première exclusion commerciale une fois ce filtre implémenté.
   L'identité doit être normalisée, pas recherchée par simple mot « Pully ».
4. Propriété inconnue, source inaccessible, extrait ambigu ou contradictoire :
   conserver la ligne, marquer « À vérifier », sans la qualifier de privée.
5. Copropriété et DDP : stocker la relation fonds/droit et chaque titulaire,
   sa qualité et quote-part. Faire valider si une participation communale
   minoritaire ou un fonds communal grevé d'un DDP privé suffit à exclure.
   Tant que ce traitement n'est pas validé, mettre ces cas en vérification.

Une absence de la commune dans une liste non exhaustive ne prouve pas une
propriété privée. Ne pas recopier inutilement des identités privées dans les
exports publics/Git ; conserver la preuve dans un espace conforme aux conditions
du fournisseur et publier seulement le statut dérivé nécessaire et autorisé.

## Suites classées

**Récupérable ou exploitable maintenant, sans nouvelle autorisation métier :**
profiler les colonnes existantes, extraire les 71 références documentaires,
normaliser les codes et dates de zones, exploiter les couches déjà livrées,
documenter les 61 écarts et 19 contours invalides, utiliser les pentes existantes,
vérifier les catalogues fédéraux autorisés. Cela n'implique pas que les documents
cantonaux sont téléchargeables dans cet environnement maintenant.

**Accès ou validation nécessaires :** propriété communale d'abord ; ouverture des
domaines cantonaux/communaux, consultation des textes et documents RF ; droits
de réutilisation, inventaires d'arbres, ISOS, dangers, limites légales et actes ;
COS par plan et surfaces de référence ; statut ZR ; règle copropriété/DDP ;
bornes de pleine terre, classes commerciales et secteurs lac/centre.

**Observation terrain nécessaire ou à confirmer par expertise :** arbre central
non couvert par un inventaire, couronne et importance, accès réel, ouvrages et
sous-sol influençant la pleine terre, contraintes structurelles de surélévation.
Une image aérienne ou un inventaire partiel peut orienter une visite, pas prouver
l'absence d'arbre ni la capacité structurelle d'un bâtiment.

## Intégration proposée, par étapes

**A. Traçabilité et tables séparées, sans changer les résultats.**
Conserver les 2 672 EGRID et les données sources immuables. Créer un registre par
source avec `source_id`, URL/version, date de publication, période de validité,
`verifie_le`, date de collecte, licence/conditions, couverture et empreinte SHA-256.
Ne pas utiliser le mtime d'un fichier comme date de validité. Distinguer valeurs
absentes, non applicables et échec de collecte. Les documents liés sont des données
de référence, pas des instructions exécutables.

Tables/relations proposées :

| Table ou couche | Champs nouveaux essentiels |
|---|---|
| Propriété/droits | `egrid_droit`, `egrid_fonds_support`, `type_droit`, `titulaire_id`, `qualite_titulaire`, `quote_part`, `commune_pully_confirmee`, `statut_verification`, `preuve_id`, `date_constat`, validité et source |
| Parcelles/qualité | Surfaces MO/RF/géométrique distinctes, géométrie/version/CRS, écarts et validité, `present_dans_derniere_collecte`, statut de disparition |
| Zones/règles | `plan_id`, `zone_id`, code et libellé exacts, part/surface d'intersection, article, dates d'enquête/approbation/entrée/fin, opposabilité vérifiée, COS et définitions, hauteur/retraits/plans spéciaux |
| Observations arbres | `observation_id`, EGRID, arbre/position si connue, état ternaire, importance/protection, `date_observation`, `source`, vérificateur ; plusieurs observations historisées |
| Contraintes géographiques | Objet source, type, géométrie, période/validité, couverture, classe/objectif, intersection et part, état connu/inconnu |
| Calculs | EGRID, versions données/règles, indicateurs cadastraux et simulations séparés, hypothèses, anomalies et motifs multiples |
| Décisions expert | EGRID, scénario, décision, motif, date et auteur ; jamais écrasés par import ou assimilés à des labels automatiques |

**B. Ajouter le filtre propriétaire uniquement après obtention des preuves.**
Évaluer toutes les règles pour conserver tous les motifs, puis ordonner l'affichage
des exclusions : propriété communale confirmée d'abord, puis autres motifs.
Une exclusion prioritaire ne doit pas court-circuiter le patrimoine ou la surface.
Si le propriétaire est inconnu et qu'aucune exclusion certaine n'existe, afficher
« À vérifier » lorsque le filtre propriété sera activé. Une exclusion certaine
coexistante reste affichée avec les autres vérifications. Pas d'activation sur
la base de `genre_parcelle`.

**C. Valider réglementation et géométries, puis calculer des observations sourcées.**
Lire d'abord les plans/règlements déjà référencés, choisir la règle par portion
de parcelle et plan spécial, résoudre dates/hiérarchie. Valider les définitions
avant de remplacer les simulations COS et retraits. Contrôler la qualité de
l'emprise existante ; traiter séparément plancher/hauteur pour la surélévation.
Ajouter les périmètres et observations d'arbres sans supposer des exclusions.

**D. Import différentiel contrôlé et activation par version.**
Staging → schéma/identifiants/CRS/validité/licences → comparaison avec le dernier
lot complet → rapport → validation si anomalie → publication atomique du lot.
Une parcelle absente d'un téléchargement reste conservée avec un indicateur de
disparition à examiner ; aucun effacement automatique. Si le lot est incomplet,
garder la dernière version valide. Archiver seulement après décision explicite,
en préservant notes et historique. Vérifier également les changements d'EGRID
(division, réunion, droit distinct), sans correspondance approximative silencieuse.

**E. Filtres d'affichage et validation métier.**
L'interface sélectionne les lignes d'une version identifiée ; elle n'écrase pas
la base ni les décisions. Désactivé ≠ absence de contrainte. Les données inconnues
restent visibles par défaut. Confirmer l'utilité avec l'expert sur ses dossiers,
sans réutiliser les statuts calculés comme vérité d'entraînement. Aucun score,
aucune pondération et aucun critère énergétique.

## Tests à conserver et ajouter avant activation

| Cas | Attendu | État |
|---|---|---|
| 599,99 / 600 / 600,01 m² | Sous seuil / retenue surface / retenue surface | Test frontière existant à compléter au-dessus de la borne |
| Propriété communale confirmée par preuve, + note 3 + surface <600 | Exclusion communale prioritaire et conservation des trois motifs | À ajouter avec le filtre propriétaire |
| Propriétaire inconnu ou réponse RF inaccessible | Ligne conservée, état propriété inconnu et vérification visible ; aucune exclusion propriétaire | À ajouter |
| « DP communal », zone publique ou URL RF sans preuve | Ne pas déduire le propriétaire | À ajouter |
| Copropriété/DDP, commune et privé en rôles différents | Pas de confusion entre titulaire du droit et propriétaire du fonds ; cas ambigu à vérifier | À ajouter avec décision métier |
| Note 3 provisoire + note 4 | Exclusion conservée ; preuves visibles | Déjà couvert |
| Note 0 / couche absente / JSON invalide | Inconnu ou incohérent à vérifier, pas de validation automatique | Déjà couvert en partie ; ajouter contradictions détaillées |
| Géométrie absente ou invalide | Ligne conservée ; forme/pente inconnues, pas zéro, pas de réparation silencieuse | Calculs existants le signalent ; ajouter test d'intégration d'import |
| COS zone mixte / plan spécial / source manquante | Pas de coefficient universel ni de droit acquis ; simulation absente ou explicitement qualifiée | Zone mixte déjà couverte ; validation juridique à ajouter |
| Date d'enquête sans entrée en vigueur | Ne pas appliquer une nouvelle règle comme opposable | À ajouter |
| Pas de polygone de danger/ISOS hors couverture | Inconnu, pas absence de contrainte | À ajouter |
| Pente NoData / couverture partielle | Inconnue ou partielle sans pénalité automatique | Tests dédiés disponibles dans `tests/` ; non réexécutés pour ce diagnostic |
| Parcelle absente du nouveau lot / lot vide | Conserver, signaler ; pas de suppression automatique ni de remplacement du dernier lot valide | À ajouter |
| Note/décision expert existante lors d'un recalcul | Conservation sans modification | À ajouter à l'import différentiel |

## Décision pour cette première étape

**Applicable maintenant :** surface géométrique ≥600 m² et exclusion commerciale
des notes 1–3 connues dans les données, avec leurs limites de fraîcheur. Les
calculs d'occupation, pente, forme et marge COS restent descriptifs/simulés.

**Avant de modifier le classement :** preuve de propriété, règle des droits
mixtes, fraîcheur des inventaires, réglementation opposable et définitions,
géométries/couvertures et décisions commerciales supplémentaires doivent être
obtenues et testées. Les classes d'écart <50 / 50–300 inclus / >300, le traitement
ISOS, l'accès compliqué, le danger et les secteurs géographiques ne sont pas
des exclusions actives. Les bornes 64–65 de pleine terre restent à arbitrer.

Ce diagnostic ne modifie ni le CSV source, ni `classification.py`, ni `filtres.json`,
ni les décisions de l'expert. Seule la documentation est corrigée/enrichie.
