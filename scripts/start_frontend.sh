#!/usr/bin/env bash
set -euo pipefail

cd /root/wuwa/mgt

exec /usr/bin/python3 - <<'PY'
import http.server
import socketserver
import urllib.request
import urllib.error
import os
from urllib.parse import urlparse

BACKEND_BASE = 'http://127.0.0.1:8765'
DIST_DIR = '/root/wuwa/mgt/frontend/dist'


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def _proxy(self):
        url = BACKEND_BASE + self.path
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length) if length > 0 else None
        headers = {'Content-Type': self.headers.get('Content-Type', 'application/json')}
        req = urllib.request.Request(url=url, data=body, method=self.command, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
                self.send_response(resp.status)
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as e:
            content = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', e.headers.get('Content-Type', 'application/json'))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            if content:
                self.wfile.write(content)
        except Exception as e:
            msg = str(e).encode('utf-8')
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/api/') or self.path == '/api':
            return self._proxy()
        parsed = urlparse(self.path)
        rel = parsed.path.lstrip('/')
        if parsed.path not in {'', '/'} and not os.path.exists(os.path.join(DIST_DIR, rel)):
            self.path = '/'
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/') or self.path == '/api':
            return self._proxy()
        self.send_error(405)

    def do_PUT(self):
        if self.path.startswith('/api/') or self.path == '/api':
            return self._proxy()
        self.send_error(405)

    def do_PATCH(self):
        if self.path.startswith('/api/') or self.path == '/api':
            return self._proxy()
        self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith('/api/') or self.path == '/api':
            return self._proxy()
        self.send_error(405)

os.chdir(DIST_DIR)
with ReusableTCPServer(('0.0.0.0', 3001), ProxyHandler) as httpd:
    httpd.serve_forever()
PY
