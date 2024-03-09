import argparse
import http.server
import socketserver


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-length", "0")
        self.end_headers()

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-length", "0")
        self.end_headers()

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--port', default=8000, help='Port to serve on')

PORT = int(parser.parse_args().port)
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), MyHttpRequestHandler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
