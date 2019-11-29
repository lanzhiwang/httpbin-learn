# -*- coding: utf-8 -*-

"""
httpbin.helpers
~~~~~~~~~~~~~~~

This module provides helper functions for httpbin.
"""

from hashlib import md5
from werkzeug.http import parse_authorization_header

from flask import request, make_response


from .structures import CaseInsensitiveDict


ASCII_ART = """
    -=[ teapot ]=-

       _...._
     .'  _ _ `.
    | ."` ^ `". _,
    \_;`"---"`|//
      |       ;/
      \_     _/
        `\"\"\"`
"""

REDIRECT_LOCATION = '/redirect/1'

ENV_HEADERS = (
    'X-Varnish',
    'X-Request-Start',
    'X-Heroku-Queue-Depth',
    'X-Real-Ip',
    'X-Forwarded-Proto',
    'X-Heroku-Queue-Wait-Time',
    'X-Forwarded-For',
    'X-Heroku-Dynos-In-Use',
    'X-Forwarded-For',
    'X-Forwarded-Protocol'
)



def get_files():
    """Returns files dict from request context."""

    files = dict()

    for k, v in request.files.items():
        files[k] = v.read()

    return files


def get_headers(hide_env=True):
    """Returns headers dict from request context."""

    headers = dict(request.headers.items())

    if hide_env and ('show_env' not in request.args):
        for key in ENV_HEADERS:
            try:
                del headers[key]
            except KeyError:
                pass

    return CaseInsensitiveDict(headers.items())


def get_dict(*keys, **extras):
    """Returns request dict of given keys."""

    _keys = ('url', 'args', 'form', 'data', 'origin', 'headers', 'files')

    assert all(map(_keys.__contains__, keys))

    data = request.data
    form = request.form

    if (len(form) == 1) and (not data):
        if not form.values().pop():
            data = form.keys().pop()
            form = None

    d = dict(
        url=request.url,
        args=request.args,
        form=form,
        data=data,
        origin=request.remote_addr,
        headers=get_headers(),
        files=get_files()
    )

    out_d = dict()

    for key in keys:
        out_d[key] = d.get(key)

    out_d.update(extras)

    return out_d


def status_code(code):
    """Returns response object of given status code."""

    redirect = dict(headers=dict(location=REDIRECT_LOCATION))

    code_map = {
        301: redirect,
        302: redirect,
        303: redirect,
        304: dict(data=''),
        305: redirect,
        307: redirect,
        401: dict(headers={'WWW-Authenticate': 'Basic realm="Fake Realm"'}),
        407: dict(headers={'Proxy-Authenticate': 'Basic realm="Fake Realm"'}),
        418: dict(  # I'm a teapot!
            data=ASCII_ART,
            headers={
                'x-more-info': 'http://tools.ietf.org/html/rfc2324'
            }
        ),

    }

    r = make_response()
    r.status_code = code

    if code in code_map:

        m = code_map[code]

        if 'data' in m:
            r.data = m['data']
        if 'headers' in m:
            r.headers = m['headers']

    return r


def check_basic_auth(user, passwd):
    """Checks user authentication using HTTP Basic Auth."""

    auth = request.authorization
    return auth and auth.username == user and auth.password == passwd



# Digest auth helpers
# qop is a quality of protection

def H(data):
    return md5(data).hexdigest()


def HA1(realm, username, password):
    """Create HA1 hash by realm, username, password

    HA1 = md5(A1) = MD5(username:realm:password)
    """
    return H("%s:%s:%s" % (username,
                           realm,
                           password))


def HA2(credentails, request):
    """Create HA2 md5 hash

    If the qop directive's value is "auth" or is unspecified, then HA2:
        HA2 = md5(A2) = MD5(method:digestURI)
    If the qop directive's value is "auth-int" , then HA2 is
        HA2 = md5(A2) = MD5(method:digestURI:MD5(entityBody))
    """
    if credentails.get("qop") == "auth" or credentails.get('qop') is None:
        return H("%s:%s" % (request['method'], request['uri']))
    elif credentails.get("qop") == "auth-int":
        for k in 'method', 'uri', 'body':
            if k not in request:
                raise ValueError("%s required" % k)
        return H("%s:%s:%s" % (request['method'],
                               request['uri'],
                               H(request['body'])))
    raise ValueError


def response(credentails, password, request):
    """Compile digest auth response

    If the qop directive's value is "auth" or "auth-int" , then compute the response as follows:
       RESPONSE = MD5(HA1:nonce:nonceCount:clienNonce:qop:HA2)
    Else if the qop directive is unspecified, then compute the response as follows:
       RESPONSE = MD5(HA1:nonce:HA2)

    Arguments:
    - `credentails`: credentails dict
    - `password`: request user password
    - `request`: request dict
    """
    response = None
    HA1_value = HA1(credentails.get('realm'), credentails.get('username'), password)
    HA2_value = HA2(credentails, request)
    if credentails.get('qop') is None:
        response = H(":".join([HA1_value, credentails.get('nonce'), HA2_value]))
    elif credentails.get('qop') == 'auth' or credentails.get('qop') == 'auth-int':
        for k in 'nonce', 'nc', 'cnonce', 'qop':
            if k not in credentails:
                raise ValueError("%s required for response H" % k)
        response = H(":".join([HA1_value,
                               credentails.get('nonce'),
                               credentails.get('nc'),
                               credentails.get('cnonce'),
                               credentails.get('qop'),
                               HA2_value]))
    else:
        raise ValueError("qop value are wrong")

    return response


def check_digest_auth(user, passwd):
    """Check user authentication using HTTP Digest auth"""

    if request.headers.get('Authorization'):
        credentails = parse_authorization_header(request.headers.get('Authorization'))
        if not credentails:
            return
        response_hash = response(credentails, passwd, dict(uri=request.path,
                                                           body=request.data,
                                                           method=request.method))
        if credentails['response'] == response_hash:
            return True
    return False
