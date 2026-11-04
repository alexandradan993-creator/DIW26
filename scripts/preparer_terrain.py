import hashlib
import json
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/terrain"

def slope(dem, valid, spacing=2):
    dy, dx = np.gradient(dem.astype('float64'), spacing)
    safe = valid.copy()
    safe[0, :] = safe[-1, :] = False
    safe[:, 0] = safe[:, -1] = False
    safe[1:-1, 1:-1] &= (valid[:-2, 1:-1] & valid[2:, 1:-1]
                         & valid[1:-1, :-2] & valid[1:-1, 2:])
    result = np.full(dem.shape, -9999, dtype='float32')
    result[safe] = np.degrees(np.arctan(np.hypot(dx[safe], dy[safe])))
    return result

def main():
    catalogue_path = OUT / 'catalogue_selection.json'
    if not catalogue_path.exists():
        raise FileNotFoundError(f"Catalogue introuvable : {catalogue_path}")

    catalogue = json.loads(catalogue_path.read_text())
    assets = [next(a for name, a in f['assets'].items()
                   if name.endswith('_2_2056_5728.tif')) for f in catalogue['features']]

    with tempfile.TemporaryDirectory(prefix='terrain_') as temporary:
        def download(asset):
            path = Path(temporary) / asset['href'].rsplit('/', 1)[-1]
            with urllib.request.urlopen(asset['href'], timeout=120) as response:
                content = response.read()
            checksum = asset.get('checksum:multihash', '').lower()
            if checksum and checksum.startswith('1220'):
                if hashlib.sha256(content).hexdigest() != checksum[4:]:
                    raise ValueError('Empreinte source incorrecte : ' + path.name)
            path.write_bytes(content)
            return path

        with ThreadPoolExecutor(max_workers=4) as executor:
            paths = list(executor.map(download, assets))

        sources = [rasterio.open(path) for path in paths]
        try:
            dem, transform = merge(sources, nodata=-9999)
            profile = sources[0].profile.copy()
        finally:
            for source in sources:
                source.close()

        profile.update(driver='GTiff', dtype='float32', count=1,
                       width=dem.shape[2], height=dem.shape[1], transform=transform,
                       nodata=-9999, compress='deflate', predictor=3, tiled=True,
                       blockxsize=256, blockysize=256)

        values = dem[0]
        valid = np.isfinite(values) & (values != -9999)

        OUT.mkdir(parents=True, exist_ok=True)
        with rasterio.open(OUT / 'altitude_2m.tif', 'w', **profile) as target:
            target.write(values.astype('float32'), 1)
            target.update_tags(source='swissALTI3D © swisstopo', units='metres')

        with rasterio.open(OUT / 'pente_degres_2m.tif', 'w', **profile) as target:
            target.write(slope(values, valid), 1)
            target.update_tags(source='Calcul dérivé de swissALTI3D © swisstopo',
                               units='degrees', method='central differences, spacing 2m')

    print('Tuiles vérifiées :', len(assets))
    print('Dimensions :', values.shape)

if __name__ == '__main__':
    main()