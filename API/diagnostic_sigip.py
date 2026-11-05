"""Deux lectures WFS minimales, sans actualisation ni activation de données."""
import json
import time
import xml.etree.ElementTree as ET

from suivi_collecte import download


def reseau():
    """Sondes sans données applicatives ; conserver tout proxy configuré."""
    import os
    import socket
    import ssl
    def trace(**data):
        print('Foncimo réseau SIGIP '+json.dumps(data),flush=True)
    if any(os.environ.get(key) for key in ('HTTPS_PROXY','https_proxy','ALL_PROXY','all_proxy')):
        trace(etat='sondes directes ignorées : proxy configuré')
        return
    host='www.sigip.ch'
    try:
        addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        seen=set()
        for family,kind,proto,_,address in addresses:
            if address[0] in seen:continue
            seen.add(address[0])
            if len(seen)>4:break
            phase='connexion TCP'
            try:
                with socket.socket(family,kind,proto) as connection:
                    connection.settimeout(5)
                    connection.connect(address)
                    trace(ip=address[0],phase=phase,etat='ok')
                    phase='négociation TLS'
                    with ssl.create_default_context().wrap_socket(connection,server_hostname=host) as secured:
                        trace(ip=address[0],phase=phase,etat='ok',tls=secured.version())
            except Exception as error:
                trace(ip=address[0],phase=phase,etat='erreur',type=type(error).__name__)
    except Exception as error:
        trace(phase='DNS',etat='erreur',type=type(error).__name__)


def autorise(flag, jusqua):
    try:return flag=='1' and time.time()<float(jusqua)
    except (ValueError,TypeError):return False


def verifier(transport=download):
    if transport is download:reseau()
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
