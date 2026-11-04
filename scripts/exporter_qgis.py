import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    output_dir = ROOT / "out"
    contours_path = ROOT / "data/parcelles/contours.geojson"
    classification_path = output_dir / "classification.csv"

    if not contours_path.exists() or not classification_path.exists():
        print("Erreur : Fichiers sources introuvables. Exécutez d'abord le pipeline complet.")
        return

    print("Chargement de la classification et des contours géographiques...")

    classification = {}
    with classification_path.open('r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            classification[row['egrid']] = row

    contours_data = json.loads(contours_path.read_text(encoding='utf-8'))

    features_enrichies = []
    match_count = 0
    for feature in contours_data.get('features', []):
        egrid = feature.get('id')
        if egrid in classification:
            feature['properties'].update(classification[egrid])
            features_enrichies.append(feature)
            match_count += 1

    qgis_geojson = {
        "type": "FeatureCollection",
        "features": features_enrichies
    }

    target_path = output_dir / "parcelles_qgis.geojson"
    target_path.write_text(json.dumps(qgis_geojson, ensure_ascii=False), encoding='utf-8')

    print(f"Fichier QGIS généré avec succès ({match_count} parcelles exportées) :")
    print(f" {target_path.resolve()}")
    print("Astuce : Glissez-déposez simplement ce fichier dans QGIS pour colorer vos parcelles selon leur potentiel")

if __name__ == "__main__":
    main()