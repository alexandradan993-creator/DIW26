"""Deux lectures WFS minimales, sans actualisation ni activation de données."""
import json
import time
import xml.etree.ElementTree as ET

from suivi_collecte import download


def verifier(transport=download):
    url='https://www.sigip.ch/mapserv_proxy'
    common={'SERVICE':'WFS','VERSION':'1.1.0','REQUEST':'GetFeature',
            'TYPENAME':'pully_recensement_provisoire_batiments'}
    results=[]
    for name,extra in [('effectif',{'RESULTTYPE':'hits'}),
                       ('un_objet',{'MAXFEATURES':1,'SRSNAME':'EPSG:2056'})]:
        started=time.monotonic()
        print('Foncimo diagnostic SIGIP '+json.dumps({'test':name,'etat':'envoi'}),flush=True)
        result={'test':name}
        try:
            content=transport(url,dict(common,**extra),False,45)
            root=ET.fromstring(content)
            if not root.tag.endswith('FeatureCollection'):
                raise ValueError('Réponse sans FeatureCollection WFS')
            result.update(etat='réponse WFS',octets=len(content),
                          effectif=root.get('numberOfFeatures'),
                          objets=sum(len(list(member)) for member in root.iter()
                                     if member.tag.endswith('featureMember') or member.tag.endswith('featureMembers')))
        except Exception as error:
            result.update(etat='erreur',erreur=str(error))
        result['duree_s']=round(time.monotonic()-started,2)
        results.append(result)
        print('Foncimo diagnostic SIGIP '+json.dumps(result,ensure_ascii=False),flush=True)
    return results
