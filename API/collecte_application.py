"""Adaptateur isolé du collecteur de l'équipe ; aucune modification de celui-ci."""
import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERT_FIELDS = ('decision_conti', 'motif_conti', 'type_bati_valide',
                 'surface_plancher_verifiee_m2', 'pleine_terre_reglementaire_m2')


def collecter(stage, etat, precedentes, _module=None):
    module = _module
    if module is None:
        spec = importlib.util.spec_from_file_location('_collecteur_application', ROOT/'API/actualiser_pully.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    from suivi_collecte import SuiviCollecte
    transport = SuiviCollecte(etat, module.telecharger if _module is not None else None)
    original_wfs = module.wfs_requete
    inventories = []
    contours = []

    def controle_transport(url, params=None, post=False):
        contenu = transport(url, params, post)
        params = params or {}
        if url.endswith('/query'):
            rep = json.loads(contenu)
            if 'error' in rep:
                raise RuntimeError(f"Source ArcGIS indisponible : {rep['error']}")
            if params.get('returnIdsOnly') == 'true':
                ids = rep.get('objectIds')
                if ids is None or len(ids) != len(set(ids)):
                    raise ValueError('Inventaire ArcGIS absent ou dupliqué')
                inventories.append((url, dict(params), set(ids)))
                etat.maj(inventaire_recu=len(ids))
            if 'objectIds' in params:
                attendus = {int(i) for i in params['objectIds'].split(',')}
                champ = next((f['name'] for f in rep.get('fields', []) if f['type']=='esriFieldTypeOID'), 'OBJECTID')
                recus = [f['attributes'].get(champ) for f in rep.get('features', [])]
                if rep.get('exceededTransferLimit') or len(recus)!=len(set(recus)) or set(recus)!=attendus:
                    raise ValueError('Page ArcGIS incomplète ou dupliquée')
                sr = rep.get('spatialReference', {})
                if sr.get('latestWkid', sr.get('wkid')) != 2056:
                    raise ValueError('Réponse ArcGIS hors MN95')
                etat.maj(objets_dernier_lot=len(recus))
                print(f'Foncimo lot contrôlé : {len(recus)} objets reçus', flush=True)
                if url.endswith('/272/query'):
                    contours.extend(rep['features'])
        return contenu

    def controle_wfs(couche, bbox, max_par_requete=5000, profondeur=0):
        resultat = original_wfs(couche, bbox, max_par_requete, profondeur)
        if profondeur >= 6 and len(resultat) >= max_par_requete:
            raise ValueError(f'Pagination SIGIP incomplète : {couche}')
        if profondeur == 0:
            hits = ET.fromstring(transport(module.SIGIP_WFS, {
                'SERVICE':'WFS', 'VERSION':'1.1.0', 'REQUEST':'GetFeature',
                'TYPENAME':couche, 'RESULTTYPE':'hits', 'SRSNAME':'EPSG:2056',
                'BBOX':','.join(map(str,bbox))+',EPSG:2056'}))
            total = hits.attrib.get('numberOfFeatures', hits.attrib.get('numberMatched'))
            if total is None or not total.isdigit() or int(total)!=len(resultat):
                raise ValueError(f'Effectif SIGIP non confirmé : {couche}')
            ids = [e.get('gml_id') for e in resultat]
            if any(not i for i in ids) or len(ids)!=len(set(ids)):
                raise ValueError(f'Identifiants SIGIP absents/dupliqués : {couche}')
            etat.data['sources']['sigip_'+couche] = {
                'objets':len(resultat), 'verifie_utc':module.maintenant(),
                'etat':'reçue ; contrôles finaux en attente'}
            etat.maj()
        return resultat

    original_arcgis = getattr(module, "arcgis_requete", None)
    if original_arcgis is not None:
        def controle_arcgis(layer_id, where, bbox=None):
            result = original_arcgis(layer_id, where, bbox)
            etat.data["sources"]["geovd_"+str(layer_id)] = {
                "objets":len(result), "verifie_utc":module.maintenant(),
                "etat":"reçue ; contrôles finaux en attente"}
            etat.maj(etape=f"GEO.vd · couche {layer_id} · {len(result)} objets reçus ; contrôles finaux en attente")
            return result
        module.arcgis_requete = controle_arcgis

    module.telecharger = controle_transport
    module.wfs_requete = controle_wfs
    etat.maj(etape='Récupération de la base GEO.vd et SIGIP', mode='application')
    rows = module.construire(etat)
    # Les inventaires sont relus : pas de publication d'un assemblage tronqué.
    for url, params, before in inventories:
        after = json.loads(transport(url, params, True)).get('objectIds')
        if after is None or set(after)!=before:
            raise ValueError('Inventaire ArcGIS modifié pendant la collecte')
    ids = [r['egrid'] for r in rows]
    raw_ids = [module.trouver_egrid(f['attributes']) for f in contours]
    if not ids or len(ids)!=len(set(ids)) or None in raw_ids or len(raw_ids)!=len(set(raw_ids)) or set(ids)!=set(raw_ids):
        raise ValueError('Parcelles absentes, ignorées ou dupliquées pendant la collecte')
    for row in rows:
        for field in EXPERT_FIELDS:
            if row['egrid'] in precedentes:
                row[field] = precedentes[row['egrid']].get(field)
    for feature, egrid in zip(contours, raw_ids):
        feature['attributes']['egris_egrid'] = egrid
    module.ecrire_csv(stage/'parcelles.csv', rows)
    (stage/'contours.json').write_text(json.dumps({'sr':2056,'results':contours},ensure_ascii=False),encoding='utf-8')
    (stage/'collecte.json').write_text(json.dumps({
        'verifie_utc':module.maintenant(), 'sources':etat.data['sources'],
        'urls':{'geovd':module.GEOVD,'sigip':module.SIGIP_WFS},
        'limite':'Dates des jeux non exposées : non déduites de la date de vérification.'},ensure_ascii=False),encoding='utf-8')
