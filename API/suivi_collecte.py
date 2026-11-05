"""Transport borné et suivi des sources publiques, sans modifier le collecteur métier."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

REQUEST_SECONDS = 45
COLLECTION_SECONDS = 20 * 60
MAX_BYTES = 64 * 1024 * 1024


class CollectionTimeout(RuntimeError):
    """Délai technique dépassé ; jamais interprété comme une source complète."""


def description(url, params):
    parsed = urlsplit(url)
    params = {**parse_qs(parsed.query), **(params or {})}
    layer = str(params.get('TYPENAME', params.get('TYPENAMES', '')))
    if isinstance(params.get('TYPENAME'), list):
        layer = params['TYPENAME'][0]
    if not layer:
        parts = parsed.path.rstrip('/').split('/')
        layer = next((p for p in reversed(parts) if p.isdigit()), 'service')
    source = 'SIGIP' if 'sigip' in (parsed.hostname or '') else 'GEO.vd'
    if params.get('returnIdsOnly') == 'true':
        action = 'inventaire des identifiants'
    elif params.get('returnCountOnly') == 'true' or params.get('RESULTTYPE') == 'hits':
        action = 'contrôle des effectifs'
    elif 'objectIds' in params:
        action = 'lot de '+str(len(str(params['objectIds']).split(',')))+' objets'
    else:
        action = str(params.get('REQUEST', 'métadonnées' if not parsed.path.endswith('/query') else 'requête'))
    return dict(source=source, couche=layer, action=action)


class SuiviCollecte:
    def __init__(self, etat, transport=None):
        self.etat = etat
        self.transport = transport
        self.deadline = time.monotonic() + COLLECTION_SECONDS
        self.number = 0
        self.bytes = 0

    def publish(self, details, **values):
        details.update(values)
        self.etat.maj(etape=f"{details['source']} · couche {details['couche']} · {details['action']} · {details['etat']}",
                      telechargement=dict(details),
                      progression_reseau=dict(requetes=self.number, octets_recus=self.bytes))
        print('Foncimo collecte '+json.dumps(dict(operation_id=self.etat.data.get('operation_id'), **details),
                                           ensure_ascii=False), flush=True)

    def __call__(self, url, params=None, post=False):
        self.number += 1
        details = dict(description(url, params), requete=self.number)
        started = time.monotonic()
        try:
            for attempt in range(1, 3):
                remaining = self.deadline - time.monotonic()
                if remaining <= 0:
                    raise CollectionTimeout('Durée maximale de récupération de 20 minutes dépassée')
                self.publish(details, etat='envoi', tentative=attempt, octets_recus=0)
                try:
                    data = (self.transport(url, params, post) if self.transport else
                            download(url, params, post, min(REQUEST_SECONDS, remaining)))
                    if time.monotonic() > self.deadline:
                        raise CollectionTimeout('Durée maximale de récupération de 20 minutes dépassée')
                    self.bytes += len(data)
                    self.publish(details, etat='réponse reçue', octets_recus=len(data),
                                 duree_s=round(time.monotonic()-started, 2))
                    return data
                except CollectionTimeout:
                    if attempt == 2 or time.monotonic() >= self.deadline:
                        raise
                    self.publish(details, etat='nouvelle tentative après délai dépassé')
        except Exception as error:
            self.publish(details, etat='erreur', motif=str(error), duree_s=round(time.monotonic()-started, 2))
            raise RuntimeError(f"{details['source']} / couche {details['couche']} / {details['action']} : {error}") from error


def download(url, params=None, post=False, timeout=REQUEST_SECONDS):
    # Processus dédié : timeout interrompt réellement connexion ET lecture, même
    # si la source envoie quelques octets régulièrement. Aucun thread abandonné.
    with tempfile.TemporaryDirectory(prefix='foncimo-http-') as folder:
        destination = Path(folder)/'response'
        payload = json.dumps(dict(url=url, params=params, post=post, destination=str(destination)))
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--download'],
                                    input=payload, text=True, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise CollectionTimeout(f'Délai maximal de téléchargement dépassé ({timeout:g} s)') from None
        if result.returncode:
            try:failure = json.loads(result.stdout)
            except (ValueError, TypeError):failure = {'type':'transport interrompu'}
            if failure.get('type') in ('TimeoutError', 'timeout'):
                raise CollectionTimeout('Délai réseau de 20 secondes dépassé')
            code = failure.get('code')
            raise RuntimeError('Téléchargement refusé ou impossible : '+failure['type']+
                               (f' (HTTP {code})' if code else ''))
        return destination.read_bytes()


def _download_worker():
    import urllib.request
    from urllib.error import HTTPError, URLError
    request = json.load(sys.stdin)
    url = request['url']
    body = None
    if request['params']:
        encoded = urlencode(request['params'])
        if request['post']:
            body = encoded.encode()
        else:
            url += ('&' if '?' in url else '?')+encoded
    try:
        req = urllib.request.Request(url, data=body, headers={'User-Agent':'DIW26-actualisation/1.0'})
        with urllib.request.urlopen(req, timeout=20) as response, open(request['destination'], 'wb') as stream:
            size = 0
            while True:
                block = response.read(65536)
                if not block:break
                size += len(block)
                if size > MAX_BYTES:raise ValueError('Réponse supérieure à 64 Mio')
                stream.write(block)
    except Exception as error:
        # Ne jamais exposer l'URL, les paramètres, les en-têtes ou le corps.
        kind = type(error.reason).__name__ if isinstance(error, URLError) and isinstance(error.reason, TimeoutError) else type(error).__name__
        print(json.dumps(dict(type=kind, code=error.code if isinstance(error, HTTPError) else None)))
        raise SystemExit(1)


if __name__ == '__main__':
    _download_worker()
