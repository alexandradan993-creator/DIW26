"""Contrat commun des contraintes pour la Carte et la Liste, par EGRID."""
SOURCE_URLS={
    'isos':'https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer/404',
    'dangers':'https://www.ogc.vd.ch/public/rest/services/OGC/wmsVD/MapServer/422',
}


def observation(value=None,unit=None,state='a_verifier',source=None,date=None,checked=None,reason=None):
    return dict(valeur=value,unite=unit,etat=state,source=source,date_donnee=date,
                date_verification=checked,motif=reason)


def contraintes(crossing=None,provenance=None):
    crossing=crossing or {};provenance=provenance or {}
    sources=provenance.get('sources',{})
    result={}
    for name in ('isos','dangers'):
        cross=crossing.get(name+'_json')
        info=sources.get(name,{})
        source=dict(id=name,url=info.get('url',SOURCE_URLS[name]),
                    version=info.get('version_donnee'),
                    empreinte=info.get('empreinte_contenu_sha256'))
        def value(v=None,unit=None,state='a_verifier',reason=None):
            return observation(v,unit,state,source,info.get('date_donnee'),info.get('verifie_utc'),reason)
        if not cross:
            result[name+'_presence']=value(reason='Croisement non disponible : contour absent/invalide ou aucune collecte validée.')
            result[name+'_part_parcelle_pct']=value(unit='%',reason='Croisement non calculable.')
            result[name+'_surface_m2']=value(unit='m²',reason='Croisement non calculable.')
            result[name+'_objets']=value(reason='Aucune observation exploitable.')
            result[name+'_couverture_pct']=value(unit='%',reason='Couverture non établie.')
        else:
            state=crossing.get(name+'_etat')
            presence=True if state in ('dans_perimetre','danger_identifie') else False if state in (
                'aucun_recouvrement_couche_consultee','hors_perimetres_consultes',
                'danger_nul_zone_etudiee','aucun_danger_identifie_dans_donnees_consultees') else None
            result[name+'_presence']=value(presence,state='etabli' if presence is not None else 'a_verifier',
                                          reason=None if presence is not None else 'Hors couverture interprétable, couverture partielle ou classe inconnue/en révision.')
            result[name+'_part_parcelle_pct']=value(cross['part_parcelle_pct'],'%','calcule')
            result[name+'_surface_m2']=value(cross['surface_union_m2'],'m²','calcule')
            result[name+'_objets']=value(cross['objets'],state='calcule')
            covered=cross.get('couverture_etude_pct')
            result[name+'_couverture_pct']=value(covered,'%',
                'calcule' if covered is not None else 'a_verifier',
                None if covered is not None else 'Périmètre d’étude non documenté ; l’emprise du service ne suffit pas.')
        if name=='dangers':
            risk=cross.get('part_danger_identifie_pct') if cross else None
            complete=bool(cross and cross.get('statut_couverture')=='complete')
            # Un zéro de risque ne doit pas masquer une zone non étudiée.
            if risk==0 and not complete:risk=None
            result['danger_part_risque_pct']=value(risk,'%',
                'calcule' if complete and risk is not None else 'partiel' if risk is not None else 'a_verifier',
                None if complete and risk is not None else 'Couverture incomplète ou inconnue : valeur positive éventuelle limitée au danger cartographié, pas à toute l’information nécessaire.')
            result['dangers_classes']=value(cross['classes'] if cross else None,state='calcule' if cross else 'a_verifier',
                reason=None if cross else 'Classes non calculables.')
            # Zéro uniquement quand W couvre la parcelle sans autre classe.
            null_danger=crossing.get('dangers_etat')=='danger_nul_zone_etudiee'
            result['danger_nul_etudie']=value(0 if null_danger else None,'degré nul',
                'etabli' if null_danger else 'a_verifier',None if null_danger else 'Le degré nul n’est pas confirmé sur toute la parcelle.')
            result['danger_naturel_bloquant']=value(reason='Une observation de danger ne détermine pas sa portée bloquante ; règle validée requise.')
    missing={
        'distance_foret_indicative_m':('m','Limite forestière officielle identifiée (couche 490), mesure non encore intégrée.'),
        'distance_eau_indicative_m':('m','Contour d’eau et ligne de mesure à valider ; espace réservé distinct.'),
        'distance_route_indicative_m':('m','Réseau/limite de route et ligne de mesure à valider ; pas de droit d’accès déduit.'),
        'recul_foret_reglementaire_m':('m','Règle applicable au projet non validée.'),
        'recul_eau_reglementaire_m':('m','Règle applicable au projet non validée.'),
        'recul_route_reglementaire_m':('m','Règle applicable au projet non validée.'),
        'arbres_classes':(None,'Inventaire communal et droits de réutilisation à confirmer ; inventaire cantonal remarquable non équivalent.'),
        'arbre_important_central':(None,'Observation datée de position et d’importance manquante.'),
        'pleine_terre_reglementaire_pct':('%','Valeur réglementaire validée manquante ; espaces verts insuffisants.'),
        'acces_physique':(None,'Accès physique non observé ; proximité routière insuffisante.'),
        'droit_acces':(None,'Titre ou servitude confirmant le droit non disponible.'),
        'propriete_communale':(None,'Aucune preuve autorisée concluante par EGRID ; affectation publique insuffisante.'),
    }
    result.update({key:observation(unit=unit,reason=reason) for key,(unit,reason) in missing.items()})
    return result
