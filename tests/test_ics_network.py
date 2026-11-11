"""Real TLS transport on explicitly loopback-only sockets; no public network."""
import http.server
import socket
import ssl
import subprocess
import threading
import time

import pytest

from test_ics import BASE, EVENT, source

CONNECT = socket.socket.connect
RESOLVE = socket.getaddrinfo
CONTEXT = ssl.create_default_context


@pytest.fixture
def peer(tmp_path, monkeypatch):
    def connect(sock, address):
        assert address[0] == '127.0.0.1', 'only owned loopback peer allowed'
        return CONNECT(sock, address)
    def resolve(host, *args, **kwargs):
        assert host == '127.0.0.1', 'only loopback resolution allowed'
        return RESOLVE(host, *args, **kwargs)
    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    cert, key = tmp_path/'cert.pem', tmp_path/'key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key), '-out', str(cert), '-days', '1', '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'], check=True, capture_output=True)
    requests = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            requests.append(dict(self.headers))
            try:
                self.respond()
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass
        def respond(self):
            if self.path.startswith('/redirect'):
                self.send_response(302)
                self.send_header('Location', 'https://external.invalid/SECRET')
                self.end_headers()
                return
            if self.path.startswith('/slow'):
                time.sleep(.6)
            self.send_response(200)
            if self.path.startswith('/large'):
                self.send_header('Content-Length', '1048577')
            self.end_headers()
            if self.path.startswith('/stream'):
                self.wfile.write(b'x'*1048577)
            elif self.path.startswith('/trickle'):
                for _ in range(20):
                    self.wfile.write(b'x'); self.wfile.flush(); time.sleep(.04)
            else:
                self.wfile.write(BASE.format(events=EVENT).encode())
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = CONTEXT(cafile=str(cert))
    monkeypatch.setattr(ssl, 'create_default_context', lambda: context)
    monkeypatch.setenv('https_proxy', 'http://external.invalid:1234')
    try:
        yield f'https://127.0.0.1:{server.server_port}', requests
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_https_real_transport(module, peer, now):
    url, requests = peer
    adapter = source(module, ics_url=url+'/private/SECRET')
    assert len(adapter.read(now=now).events) == 1
    assert len(requests) == 1
    assert not {'Authorization', 'Cookie', 'Referer', 'Proxy-Authorization'} & requests[0].keys()
    assert 'SECRET' not in repr(adapter.status)


@pytest.mark.parametrize('path', ['/redirect/SECRET', '/large/SECRET', '/stream/SECRET', '/slow/SECRET', '/trickle/SECRET'])
def test_https_denials(module, peer, now, path):
    url, requests = peer
    adapter = source(module, ics_url=url+path, timeout=.2)
    start = time.monotonic()
    with pytest.raises(ValueError) as exc:
        adapter.read(now=now)
    assert time.monotonic()-start < 1
    assert 'SECRET' not in str(exc.value)
    assert adapter.status['error'] == 'calendar_unavailable'
    assert len(requests) == 1


def test_tls_untrusted_rejected(module, peer, now, monkeypatch):
    url, requests = peer
    monkeypatch.setattr(ssl, 'create_default_context', CONTEXT)
    with pytest.raises(ValueError, match='calendar unavailable'):
        source(module, ics_url=url+'/SECRET').read(now=now)
    assert requests == []
