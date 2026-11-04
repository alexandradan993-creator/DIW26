import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent / "code"))

from classification import run

def main():
    base_dir = Path(__file__).parent
    input_csv = base_dir / "pully_parcelles.csv"
    config_json = base_dir / "code" / "filtres.json"
    output_dir = base_dir / "out"

    output_dir.mkdir(parents=True, exist_ok=True)

    print("Exécution du pipeline Foncimo sur les parcelles de Pully...")

    rapport = run(input_csv, config_json, output_dir)

    print("\nTraitement terminé avec succès")
    print("Statistiques globales :")
    for statut, nombre in rapport.get('effectifs', {}).items():
        print(f"  - {statut} : {nombre} parcelles")

    print(f"Fichiers de sortie enregistrés dans : {output_dir.resolve()}")

if __name__ == "__main__":
    main()