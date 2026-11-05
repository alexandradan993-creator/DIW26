"""Sonde temporaire Render : santé minimale publique, diagnostic dans les logs privés."""
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from diagnostic_sigip import verifier


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'{"statut":"pret"}' if self.path in ('/','/healthz') else b'{}'
        self.send_response(200 if self.path in ('/','/healthz') else 404)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self,*args):
        pass


if __name__=='__main__':
    threading.Thread(target=verifier,daemon=True,name='diagnostic-sigip').start()
    ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8000'))),HealthHandler).serve_forever()
