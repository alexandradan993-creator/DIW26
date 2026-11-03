# Formes et enveloppes exploratoires

Voir [la méthode et les pourcentages](../../code/FORME_ET_POURCENTAGES.md).

- `formes_parcelles.csv` : 2 672 EGRID ; résultats pour 2 653 contours,
  dont 61 avec alerte de surface ; 19 non calculables (valeurs vides).
- `enveloppes_simulees.geojson` : enveloppes non vides après retrait de 6 m,
  en WGS84. Simulation cartographique, pas une limite réglementaire.
- `resume.json` : date, hypothèse, effectifs et empreintes des entrées.

530 contours ont une enveloppe vide dans cette hypothèse, sans exclusion
commerciale automatique. Les surfaces sont calculées en MN95. Les arbres,
le bâti, la pleine terre et les reculs particuliers ne sont pas retirés.
