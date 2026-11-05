"""Application WSGI commune au serveur local et à l'hébergement Waitress."""
from __future__ import annotations

import base64
import hmac
import json
import logging
import os
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def create_app(service, origins=(), username=None, password=None):
    origins = set(origins)
    if (username is None) != (password is None):
        raise ValueError('Identifiant et mot de passe requis ensemble')

    def application(environ, start_response):
        origin = environ.get('HTTP_ORIGIN')
        method = environ['REQUEST_METHOD']
        path = environ.get('PATH_INFO', '/')

        def answer(code, value=None, *, body=None, content_type='application/json; charset=utf-8', headers=()):
            if body is None:
                body = b'' if code == 204 else json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
            result = [('Content-Type', content_type), ('Content-Length', str(len(body))),
                      ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), *headers]
            if origin in origins:
                result.extend([('Access-Control-Allow-Origin', origin), ('Vary', 'Origin'),
                               ('Access-Control-Allow-Credentials', 'true')])
            start_response(f'{code} {HTTPStatus(code).phrase}', result)
            return [body]

        # Contrôle d'hébergement sans exposer les données ou lancer de collecte.
        if path == '/healthz' and method == 'GET':
            try:
                service.version_path(service.active())
                return answer(200, {'statut': 'pret'})
            except (ValueError, KeyError, OSError):
                return answer(503, {'statut': 'indisponible'})

        if method == 'OPTIONS':
            if origin not in origins:
                return answer(403, {'erreur': 'Origine non autorisée'})
            return answer(204, headers=[('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
                                        ('Access-Control-Allow-Headers', 'Content-Type, Authorization')])

        if password is not None:
            try:
                kind, token = environ.get('HTTP_AUTHORIZATION', '').split(' ', 1)
                if kind.lower() != 'basic':
                    raise ValueError('Type d’authentification')
                user, supplied = base64.b64decode(token, validate=True).decode('utf-8').split(':', 1)
                user_ok = hmac.compare_digest(user.encode('utf-8'), username.encode('utf-8'))
                password_ok = hmac.compare_digest(supplied.encode('utf-8'), password.encode('utf-8'))
                authorized = user_ok and password_ok
            except (ValueError, UnicodeError):
                authorized = False
            if not authorized:
                return answer(401, {'erreur': 'Connexion requise'},
                              headers=[('WWW-Authenticate', 'Basic realm="Foncimo", charset="UTF-8"')])

        try:
            query = parse_qs(environ.get('QUERY_STRING', ''))
            version = query.get('version', [None])[0]
            if method == 'GET':
                if path in ('/', '/carte-pully.html', '/actualisation.js'):
                    name = 'actualisation.js' if path.endswith('.js') else 'carte-pully.html'
                    mime = 'text/javascript' if name.endswith('.js') else 'text/html'
                    return answer(200, body=(ROOT/'interface'/name).read_bytes(), content_type=mime+'; charset=utf-8')
                if path == '/application/donnees':
                    return answer(200, service.interface(version))
                if path == '/versions/active':
                    return answer(200, {'version': service.active()})
                if path == '/actualisations/etat':
                    return answer(200, service.status())
                if path.startswith('/actualisations/'):
                    return answer(200, service.status(path.split('/')[-1]))
                if path == '/parcelles':
                    offset = int(query.get('offset', ['0'])[0]); limit = int(query.get('limit', ['50'])[0])
                    if offset < 0 or not 1 <= limit <= 200:
                        raise ValueError('Pagination invalide')
                    return answer(200, service.liste(version, offset, limit))
                if path.startswith('/parcelles/'):
                    return answer(200, service.fiche(path[len('/parcelles/'):], version))
            elif method == 'POST' and path == '/actualisations':
                if origin and origin not in origins and urlsplit(origin).netloc != environ.get('HTTP_HOST'):
                    return answer(403, {'erreur': 'Origine non autorisée'})
                if environ.get('CONTENT_TYPE', '').split(';', 1)[0].strip().lower() != 'application/json':
                    return answer(415, {'erreur': 'Content-Type application/json requis'})
                size = int(environ.get('CONTENT_LENGTH') or '0')
                if not 0 <= size <= 1024:
                    raise ValueError('Corps trop volumineux')
                value = json.loads(environ['wsgi.input'].read(size) or b'{}')
                if value != {}:
                    raise ValueError('Configuration côté serveur uniquement')
                result = service.start()
                return answer(200 if result['reutilisee'] else 202, result)
            return answer(404, {'erreur': 'Route inconnue'})
        except KeyError as error:
            return answer(404, {'erreur': str(error)})
        except ValueError as error:
            return answer(400, {'erreur': str(error)})
        except RuntimeError as error:
            return answer(409, {'erreur': str(error)})
        except OSError:
            return answer(503, {'erreur': 'Stockage momentanément indisponible'})
        except Exception:
            logging.exception('Erreur du serveur Foncimo')
            return answer(500, {'erreur': 'Erreur serveur ; données actives conservées'})

    return application


def main():
    from waitress import serve
    from collecte_application import collecter
    from service_contraintes import DEFAULT_REFERENCE, UpdateService

    password = os.environ.get('FONCIMO_PASSWORD', '')
    username = os.environ.get('FONCIMO_USERNAME', 'foncimo')
    if len(password) < 16 or not username or ':' in username:
        raise SystemExit('Configurer FONCIMO_USERNAME et FONCIMO_PASSWORD (16 caractères minimum) dans les secrets de l’hébergeur.')
    storage = Path(os.environ.get('FONCIMO_STORAGE', str(ROOT/'API/versions/web')))
    reference = Path(os.environ.get('FONCIMO_REFERENCE', str(DEFAULT_REFERENCE)))
    service = UpdateService(storage=storage, reference=reference, base_collector=collecter)
    app = create_app(service, username=username, password=password)
    print('Foncimo prêt : interface et API, authentification activée.', flush=True)
    from diagnostic_sigip import autorise, verifier
    if autorise(os.environ.get('FONCIMO_DIAGNOSTIC_SIGIP'),os.environ.get('FONCIMO_DIAGNOSTIC_SIGIP_UNTIL')):
        import threading
        threading.Thread(target=verifier,name='diagnostic-sigip',daemon=True).start()
    # Une instance et un processus ; stockage temporaire sur Free.
    serve(app, host=os.environ.get('HOST', '0.0.0.0'), port=int(os.environ.get('PORT', '8000')),
          threads=8, max_request_body_size=2048, channel_timeout=30,
          clear_untrusted_proxy_headers=True)


if __name__ == '__main__':
    main()
