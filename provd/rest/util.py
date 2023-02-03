# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from provd.util import decode_bytes

PROV_MIME_TYPE = 'application/vnd.proformatique.provd+json'


def uri_append_path(base: bytes | str, *path: bytes | str) -> str:
    """Append path to base URI.

    >>> uri_append_path('http://localhost/', 'foo')
    'http://localhost/foo
    >>> uri_append_path('http://localhost/bar', 'foo')
    'http://localhost/bar/foo'
    >>> uri_append_path('http://localhost/bar', 'foo', 'bar')
    'http://localhost/bar/foo/bar'

    """
    if not path:
        return decode_bytes(base)
    base = decode_bytes(base)
    path_to_append = '/'.join(decode_bytes(p) for p in path)
    if base.endswith('/'):
        fmt = '%s%s'
    else:
        fmt = '%s/%s'
    return fmt % (base, path_to_append)
