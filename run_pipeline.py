import json
from pathlib import Path
import sys

base_dir = Path(__file__).parent
sys.path.append(str(base_dir / "code"))
sys.path.append(str(base_dir / "scripts"))

from classification import run as run_classification
from preparer_terrain import main as preparer_terrain_main
from calculer_formes_parcelles import main as calculer_formes_main
from calculer_pentes_parcelles import main as calculer_pentes_main
from exporter_qgis import main as exporter_qgis_main

def main():
    print("Lancement du pipeline complet Foncimo - Densification à Pully...\n")

    print("--- Étape 1/4 : Préparation des données de terrain ---")
    try:
        preparer_terrain_main()
    except Exception as e:
        print(f"Avertissement ou erreur lors de la préparation du terrain : {e}")

    print("\n--- Étape 2/4 : Calcul des formes et des enveloppes ---")
    try:
        calculer_formes_main()
    except Exception as e:
        print(f"Erreur lors du calcul des formes : {e}")

    print("\n--- Étape 3/4 : Calcul topographique des pentes par parcelle ---")
    try:
        calculer_pentes_main()
    except Exception as e:
        print(f"Erreur lors du calcul des pentes : {e}")

    print("\n--- Étape 4/4 : Exécution de la classification réglementaire finale ---")
    input_csv = base_dir / "pully_parcelles.csv"
    config_json = base_dir / "code" / "filtres.json"
    output_dir = base_dir / "out"

    output_dir.mkdir(parents=True, exist_ok=True)
    rapport = run_classification(input_csv, config_json, output_dir)

    print("\n--- Étape 5/5 : Export des données géographiques pour QGIS ---")
    try:
        exporter_qgis_main()
    except Exception as e:
        print(f"Erreur lors de l'export QGIS : {e}")

    print("\nPipeline complet terminé avec succès")
    print("Statistiques globales de classification :")
    for statut, nombre in rapport.get('effectifs', {}).items():
        print(f"  - {statut} : {nombre} parcelles")

    print(f"\n Tous les résultats consolidés sont enregistrés dans : {output_dir.resolve()}")

if __name__ == "__main__":
    main()