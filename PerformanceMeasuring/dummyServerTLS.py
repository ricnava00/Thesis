import argparse
import http.server
import socketserver
import ssl
import subprocess
import os
import tempfile

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-length", "0")
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-length", "0")
        self.end_headers()

def generate_self_signed_cert(cert_file, key_file):
    subprocess.run([
        'openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-keyout', key_file,
        '-out', cert_file, '-days', '365', '-nodes', '-subj', '/CN=localhost'
    ])

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', default=8000, help='Port to serve on')

PORT = int(parser.parse_args().port)

with tempfile.NamedTemporaryFile(delete=False,suffix=".pem") as cert_file, tempfile.NamedTemporaryFile(delete=False,suffix=".pem") as key_file:
    CERT_FILE = cert_file.name
    # CERT_FILE = "cert.pem"
    KEY_FILE = key_file.name
    # KEY_FILE = "key.pem"

    generate_self_signed_cert(CERT_FILE, KEY_FILE)

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), MyHttpRequestHandler) as httpd:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        print("serving at port", PORT)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

    os.remove(CERT_FILE)
    os.remove(KEY_FILE)