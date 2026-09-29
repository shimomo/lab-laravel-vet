"""Serve the local Composer repository over HTTPS and log who downloads what.

Usage: python3 serve.py <port> <root> <cert> <key> <log>
"""
import functools
import http.server
import ssl
import sys

port, root, cert, key, log_path = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        agent = self.headers.get('User-Agent', '-') if self.headers else '-'
        with open(log_path, 'a', encoding='utf-8') as log:
            log.write('%s %s | UA=%s\n' % (self.log_date_time_string(), format % args, agent))


httpd = http.server.ThreadingHTTPServer(('127.0.0.1', port), functools.partial(Handler, directory=root))
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(cert, key)
httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
httpd.serve_forever()
