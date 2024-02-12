# start a webserver to spoof the image request
import http.server
import socketserver
import threading
import requests


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()


PORT = 8000
with socketserver.TCPServer(("", PORT), MyHttpRequestHandler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
