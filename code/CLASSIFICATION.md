# Classification configurable — première version à 600m²

**Évolution :** [deux pourcentages et effet de la forme](FORME_ET_POURCENTAGES.md).
Le retrait uniforme de 6m est une hypothèse configurable à confirmer.

Cette version accompagne la prospection de l'expert immobilier. Elle produit
une présélection expliquée et des vérifications, pas une certification de
constructibilité ou une estimation de valeur. Elle complète le prototype
historique `prospection.py`, conservé sans changement.

## Relancer depuis la racine du dépôt

Le projet utilise désormais un pipeline global automatisé pour enchaîner la préparation, les calculs de formes, de pentes et la classification.

Python 3.10 ou ultérieur, bibliothèque standard uniquement :

```bash
python run_pipeline.py