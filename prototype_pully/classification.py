"""Filtres de prospection évolutifs, sans score ni certification réglementaire.

Python 3.10+, bibliothèque standard. Le prototype prospection.py reste inchangé.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prospection import HERITAGE_SOURCES, dwelling_count, heritage, load_rows, numeric


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError('Configuration attendue : objet JSON')
    allowed = {'version', 'surface', 'patrimoine', 'arbres', 'cos'}
    if set(config) != allowed:
        raise ValueError('Clés de configuration attendues : '+', '.join(sorted(allowed)))
    if not isinstance(config['version'], str) or not config['version'].strip():
        raise ValueError('Version de configuration requise')
    for key in allowed-{'version'}:
        section=config[key]
        expected={'actif'} | ({'minimum_m2'} if key=='surface' else {'par_zone'} if key=='cos' else set())
        if not isinstance(section,dict) or set(section)!=expected or type(section['actif']) is not bool:
            raise ValueError('Configuration invalide : '+key)
    minimum=config['surface']['minimum_m2']
    if type(minimum) not in (int,float) or not math.isfinite(minimum) or minimum<0:
        raise ValueError('Surface minimale : nombre fini positif ou nul')
    zones=config['cos']['par_zone']
    if not isinstance(zones,dict):
        raise ValueError('COS : table par_zone attendue')
    for zone, rule in zones.items():
        if (not zone.strip() or not isinstance(rule,dict) or set(rule)!={'valeur','source'}
                or type(rule['valeur']) not in (int,float) or not math.isfinite(rule['valeur'])
                or not 0<rule['valeur']<=1 or not isinstance(rule['source'],str)
                or not rule['source'].strip()):
            raise ValueError('COS et source invalides pour la zone : '+zone)


def analyse(row: dict, config: dict, observation: dict | None = None,
            slope: dict | None = None) -> dict:
    exclusions, issues, remaining, signals = [], [], [], []
    surface=numeric(row.get('surface_geometrique_m2'))
    footprint=numeric(row.get('emprise_batie_m2'))
    zone=str(row.get('zone_dominante') or '').strip()
    filters=[]
    evidence=[]
    if config['surface']['actif']:
        threshold=config['surface']['minimum_m2']
        state='inconnu' if surface is None or surface<=0 else 'hors_cible' if surface<threshold else 'retenu'
        filters.append(dict(critere='surface',etat=state,seuil_m2=threshold))
        if state=='hors_cible':
            exclusions.append(f'Surface inférieure à {threshold:g} m²')
        elif state=='inconnu':
            issues.append('Surface absente ou invalide')
        else:
            signals.append(f'Surface de {surface:g} m², seuil inclusif de {threshold:g} m² satisfait')
    if config['patrimoine']['actif']:
        heritage_issues=[]
        for _, summary, details, _ in HERITAGE_SOURCES[:4]:
            if summary not in row and details not in row:
                heritage_issues.append('Couche patrimoniale absente : '+str(summary))
        evidence=heritage(row,heritage_issues)
        blocked=any(e.get('indicateur_bloquant') or e.get('note') in (1,2,3) for e in evidence)
        filters.append(dict(critere='patrimoine',etat='exclu' if blocked else 'inconnu' if heritage_issues else 'retenu'))
        if blocked:
            exclusions.append('Note patrimoniale 1, 2 ou 3, même provisoire')
        issues.extend(heritage_issues)
        remaining.append('Confirmer le recensement et les protections actuelles auprès des sources officielles')
    tree='desactive'
    if config['arbres']['actif']:
        observation=observation or {}
        value=str(observation.get('arbre_central','')).strip().lower()
        source=str(observation.get('source','')).strip()
        if value in ('true','1','oui') and source:
            tree='presence_signalee'
            remaining.append('Arbre central signalé : vérifier implantation, protection et effet sur chaque scénario')
        elif value in ('false','0','non') and source:
            tree='absence_signalee_a_confirmer'
            remaining.append('Confirmer l’observation d’absence d’arbre central et les autres arbres à conserver')
        else:
            tree='inconnu'
            remaining.append('Arbres : localisation, importance et protection à vérifier (observation sourcée manquante ou illisible)')
        filters.append(dict(critere='arbres',etat=tree,effet='information_sans_exclusion',source=source))

    cos, maximum, gap, ratio = None, None, None, None
    rule=config['cos']['par_zone'].get(zone) if config['cos']['actif'] else None
    if config['cos']['actif']:
        if rule is None:
            remaining.append('COS applicable absent de la configuration pour cette zone ; aucun calcul effectué')
        elif surface is None or surface<=0 or footprint is None or not 0<=footprint<=surface:
            issues.append('Surfaces absentes ou incohérentes : simulation COS impossible')
        elif (numeric(row.get('zone_dominante_part_surface')) is None
              or not .99<=numeric(row.get('zone_dominante_part_surface'))<=1.001):
            issues.append('Zone dominante insuffisamment certaine : simulation COS non effectuée')
        else:
            cos=rule['valeur']
            maximum=surface*cos
            gap=maximum-footprint
            ratio=footprint/maximum
            signals.append('Écart apparent de la simulation COS : '+f'{gap:.1f} m² (non garanti)')
        remaining.append('Vérifier COS, surface de référence, emprise réglementaire, plans spéciaux et reculs ; simulation sur données cadastrales uniquement')
    if surface is not None and surface>0 and footprint is not None and 0<=footprint<=surface:
        cadastral_ratio=footprint/surface
    else:
        cadastral_ratio=None
    # Ne pas transformer une mesure de pente ou une information manquante en exclusion.
    remaining.extend([
        'Périmètres ISOS, affectation et règles applicables à vérifier',
        'Pleine terre, accès physique et juridique, dangers et servitudes à vérifier',
        'Propriété communale et secteurs géographiques à confirmer avant activation de leurs exclusions',
        'Faire qualifier commercialement reconstruction, extension et surélévation par l’expert',
    ])
    status='exclue_cible' if exclusions else 'a_verifier_filtres' if issues else 'retenue_filtres_connus'
    building_issues=[]
    dwellings, known, matched=dwelling_count(row,building_issues)
    return dict(
        egrid=row['egrid'],numero_parcelle=row['numero_parcelle'],statut_filtrage=status,
        statut_potentiel='non_etabli',version_criteres=config['version'],
        motifs_exclusion_json=exclusions,signaux_json=signals,anomalies_json=issues,
        filtres_json=filters,preuves_patrimoine_json=evidence,
        verifications_restantes_json=remaining,surface_geometrique_m2=surface,
        emprise_cadastrale_m2=footprint,taux_occupation_cadastral=cadastral_ratio,
        zone_dominante=zone,arbre_central_statut=tree,
        cos_simulation=cos,cos_source=rule['source'] if rule else None,
        emprise_theorique_simulee_m2=maximum,ecart_apparent_simule_m2=gap,
        ratio_emprise_sur_maximum_simule=ratio,
        pente_information_json=slope or {},decision_expert=row.get('decision_conti',''),
        logements_rattachement_declare=dwellings,logements_objets_renseignes=known,
        logements_objets_total=matched,anomalies_bati_json=building_issues,
        motif_expert=row.get('motif_conti',''),url_rdppf=row.get('url_rdppf',''))


def index_csv(path: Path | None, expected: set[str], required: set[str]) -> dict:
    if path is None:
        return {}
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if not required<=set(reader.fieldnames or []):
            raise ValueError('Colonnes requises absentes : '+str(path))
        rows=list(reader)
    index={r['egrid']:r for r in rows}
    if len(index)!=len(rows) or not set(index)<=expected:
        raise ValueError('EGRID dupliqué ou inconnu : '+str(path))
    return index


def run(input_path: Path, config_path: Path, output: Path,
        observations: Path | None = None, slopes: Path | None = None) -> dict:
    config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    validate_config(config)
    rows=load_rows(input_path)
    expected={r['egrid'] for r in rows}
    trees=index_csv(observations,expected,{'egrid','arbre_central','source'})
    slope_index=index_csv(slopes,expected,{'egrid','statut_calcul','alertes_json'})
    results=[analyse(row,config,trees.get(row['egrid']),slope_index.get(row['egrid'])) for row in rows]
    counts=Counter(r['statut_filtrage'] for r in results)
    files=['classification.csv','retenues_a_examiner.csv','resume.json']
    inputs=[p.resolve() for p in [input_path,config_path,observations,slopes] if p]
    if any((output/f).resolve() in inputs for f in files):
        raise ValueError('La sortie écraserait un fichier d’entrée')
    summary=dict(date_execution_utc=datetime.now(timezone.utc).isoformat(),
                 criteres=config,parcelles_total=len(results),effectifs=dict(counts),
                 simulations_cos=sum(r['cos_simulation'] is not None for r in results),
                 arbres=dict(Counter(r['arbre_central_statut'] for r in results)),
                 sources_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                 [input_path,config_path,observations,slopes] if p},
                 limite='Retenue signifie uniquement passage des filtres connus activés. Potentiel non établi, données et réglementation à compléter. Aucun score ni critère énergétique.')
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temp:
        staging=Path(temp)
        for filename, selection in [('classification.csv',results),
                                    ('retenues_a_examiner.csv',[r for r in results if r['statut_filtrage']=='retenue_filtres_connus'])]:
            with (staging/filename).open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(results[0]),lineterminator='\n')
                writer.writeheader()
                writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in selection)
        (staging/'resume.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        for filename in files:
            os.replace(staging/filename,output/filename)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('prototype_pully/resultats_classification'))
    parser.add_argument('--observations-arbres',type=Path)
    parser.add_argument('--pentes',type=Path)
    args=parser.parse_args()
    try:
        summary=run(args.input,args.config,args.output,args.observations_arbres,args.pentes)
    except (OSError,ValueError,TypeError) as error:
        parser.exit(2,'Erreur : '+str(error)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
