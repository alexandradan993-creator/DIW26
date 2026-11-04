# Prospection immobilière à Pully (Backend / Pipeline de calcul)

## 1. Vue d'ensemble du projet
Ce dépôt contient le moteur de calcul et le pipeline de classification pour l'analyse du potentiel de densification des parcelles de Pully (Canton de Vaud), réalisé dans le cadre de la Digital Innovation Week 2026 (HEC Lausanne).

L'outil intègre :
- **La double temporalité :** Potentiel latent immédiat (règlement en vigueur / PACom 1954 / zone réservée) et scénario d'évolution (Pully 2040).
- **Les règles métier validées :** Seuil de 600m² minimum, exclusion stricte du patrimoine (notes 1, 2, 3), respect de la zone réservée (pleine terre ≥ 50%), prise en compte des reculs RDPPF et des pentes.

---

## 2. Structure du Pipeline
Le projet s'exécute désormais via un pipeline global automatisé (`run_pipeline.py`) qui enchaîne les étapes de préparation, de calcul géométrique/topographique et de classification réglementaire.

---

## 3. L'exécution du Pipeline

Pour lancer l'ensemble du traitement et générer les résultats consolidés :

```bash
python run_pipeline.py
