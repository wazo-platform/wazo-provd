# -*- coding: utf-8 -*-
# Copyright 2011-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import functools
from twisted.web import http

from provd.util import decode_bytes


def numeric_id_generator(prefix='', start=0):
    n = start
    while True:
        yield f'{prefix}{n}'
        n += 1


def parse_accept(value):
    """Take the value of an Accept header and return a list of the acceptable
    mime type.

    """
    # Take q params into account
    tokens = [token.strip() for token in decode_bytes(value).split(',')]
    return [token.split(';', 1)[0] for token in tokens]


def accept_mime_type(mime_type, request):
    """Return true if mime_type is an acceptable mime-mime_type for the response
    for the request.

    """
    if request.getHeader(b'Accept') is None:
        return True
    accept = parse_accept(request.getHeader(b'Accept'))
    if mime_type in accept or '*/*' in accept:
        return True
    if mime_type[:mime_type.index('/')] + '/*' in accept:
        return True
    return False


def accept(mime_types):
    """Decorator to restrict the MIME type a Resource render method
    can accept, i.e. check the Accept header value.

    """
    def in_accept(fun):
        @functools.wraps(fun)
        def aux(self, request):
            for mime_type in mime_types:
                if accept_mime_type(mime_type, request):
                    return fun(self, request)
            else:
                request.setResponseCode(http.NOT_ACCEPTABLE)
                request.setHeader(b'Content-Type', b'text/plain; charset=UTF-8')
                return f"You must accept one of the following MIME type '{mime_types}'.".encode('utf-8')
        return aux
    return in_accept


def content_type(mime_type):
    def in_content_type(fun):
        @functools.wraps(fun)
        def aux(self, request):
            content_type = decode_bytes(request.getHeader(b'Content-Type'))
            if not content_type or content_type not in decode_bytes(mime_type):
                request.setResponseCode(http.UNSUPPORTED_MEDIA_TYPE)
                request.setHeader(b'Content-Type', b'text/plain; charset=UTF-8')
                return f"Entity must be in one of these media types '{mime_type}'.".encode('utf-8')
            return fun(self, request)
        return aux
    return in_content_type
