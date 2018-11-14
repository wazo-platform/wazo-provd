# -*- coding: utf-8 -*-
# Copyright (C) 2010-2014 Avencall
# SPDX-License-Identifier: GPL-3.0+

PROV_MIME_TYPE = 'application/vnd.proformatique.provd+json'


def uri_append_path(base, *path):
    """Append path to base URI.
    
    >>> uri_append_path('http://localhost/', 'foo')
    'http://localhost/foo
    >>> uri_append_path('http://localhost/bar', 'foo')
    'http://localhost/bar/foo'
    >>> uri_append_path('http://localhost/bar', 'foo', 'bar')
    'http://localhost/bar/foo/bar'
    
    """
    if not path:
        return base
    else:
        path_to_append = '/'.join(path)
        if base.endswith('/'):
            fmt = '%s%s'
        else:
            fmt = '%s/%s'
        return fmt % (base, path_to_append)
