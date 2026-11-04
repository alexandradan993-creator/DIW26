"""Serveur local des fiches ; aucune interface Figma ne lance du Python seule."""
import argparse
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server as wsgi_server

from application_web import create_app
from service_contraintes import UpdateService


class ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def make_server(service,host='127.0.0.1',port=8000,origins=()):
    return wsgi_server(host, port, create_app(service, origins),
                       server_class=ThreadedServer, handler_class=QuietHandler)


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
