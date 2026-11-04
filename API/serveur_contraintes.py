"""Serveur local des fiches ; aucune interface Figma ne lance du Python seule."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote

from service_contraintes import UpdateService


def make_server(service,host='127.0.0.1',port=8000,origins=()):
    origins=set(origins)
    class Handler(BaseHTTPRequestHandler):
        def answer(self,code,value):
            body=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(body)))
            if self.headers.get('Origin') in origins:
                self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
                self.send_header('Vary','Origin')
            self.end_headers();self.wfile.write(body)

        def do_OPTIONS(self):
            origin=self.headers.get('Origin')
            if origin not in origins:
                self.answer(403,{'erreur':'Origine non autorisée'});return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers','Content-Type')
            self.send_header('Content-Length','0');self.end_headers()

        def do_GET(self):
            url=urlsplit(self.path);query=parse_qs(url.query)
            version=query.get('version',[None])[0]
            try:
                if url.path in ('/','/carte-pully.html','/actualisation.js'):
                    name='actualisation.js' if url.path.endswith('.js') else 'carte-pully.html'
                    body=(Path(__file__).resolve().parents[1]/'interface'/name).read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type',('text/javascript' if name.endswith('.js') else 'text/html')+'; charset=utf-8')
                    self.send_header('Content-Length',str(len(body)))
                    self.send_header('Cache-Control','no-store')
                    self.end_headers();self.wfile.write(body)
                elif url.path=='/application/donnees':
                    self.answer(200,service.interface(version))
                elif url.path=='/versions/active':
                    self.answer(200,{'version':service.active()})
                elif url.path=='/actualisations/etat':
                    self.answer(200,service.status())
                elif url.path.startswith('/actualisations/'):
                    self.answer(200,service.status(url.path.split('/')[-1]))
                elif url.path=='/parcelles':
                    offset=int(query.get('offset',['0'])[0]);limit=int(query.get('limit',['50'])[0])
                    if offset<0 or not 1<=limit<=200:raise ValueError('Pagination invalide')
                    self.answer(200,service.liste(version,offset,limit))
                elif url.path.startswith('/parcelles/'):
                    self.answer(200,service.fiche(unquote(url.path[len('/parcelles/'):]),version))
                else:self.answer(404,{'erreur':'Route inconnue'})
            except KeyError as error:self.answer(404,{'erreur':str(error)})
            except ValueError as error:self.answer(400,{'erreur':str(error)})
            except OSError:self.answer(503,{'erreur':'Stockage momentanément indisponible'})

        def do_POST(self):
            if urlsplit(self.path).path!='/actualisations':
                self.answer(404,{'erreur':'Route inconnue'});return
            origin=self.headers.get('Origin')
            if origin and origin not in origins and urlsplit(origin).netloc!=self.headers.get('Host'):
                self.answer(403,{'erreur':'Origine non autorisée'});return
            if self.headers.get_content_type()!='application/json':
                self.answer(415,{'erreur':'Content-Type application/json requis'});return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<=size<=1024:raise ValueError('Corps trop volumineux')
                body=json.loads(self.rfile.read(size) or b'{}')
                if body!={}:raise ValueError('Aucun chemin ni paramètre arbitraire accepté ; configuration côté serveur')
                result=service.start()
                self.answer(200 if result['reutilisee'] else 202,result)
            except ValueError as error:self.answer(400,{'erreur':str(error)})
            except RuntimeError as error:self.answer(409,{'erreur':str(error)})
            except OSError:self.answer(503,{'erreur':'Stockage momentanément indisponible'})

        def log_message(self,*args):
            pass

    return ThreadingHTTPServer((host,port),Handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--contours',type=Path)
    parser.add_argument('--stockage',type=Path)
    parser.add_argument('--origine-interface',action='append',default=[],help="origine précise du frontend de développement")
    args=parser.parse_args()
    from collecte_application import collecter
    service=UpdateService(args.stockage,args.reference,args.contours,base_collector=collecter)
    for origin in args.origine_interface:
        parsed=urlsplit(origin)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            parser.error('Origine attendue : schéma + hôte + port, sans chemin')
    server=make_server(service,port=args.port,origins=args.origine_interface)
    print(f'Serveur API local prêt sur le port {server.server_address[1]}. Version : {service.active()}')
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        if service.thread:service.thread.join()


if __name__=='__main__':
    main()
