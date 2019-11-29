# -*- coding: utf-8 -*-

import sys

from gevent.wsgi import WSGIServer
from httpbin import app


try:
    port = int(sys.argv[1])
except (KeyError, ValueError):
    port = 5000

print 'Starting httpbin on port {0}'.format(port)
http_server = WSGIServer(('', port), app)
http_server.serve_forever()