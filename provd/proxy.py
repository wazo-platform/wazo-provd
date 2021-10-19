# -*- coding: utf-8 -*-
# Copyright 2011-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Extension to the urllib2 module that adds a proxy handler that can
be modified after its creation.

"""


from __future__ import absolute_import
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse


class DynProxyHandler(six.moves.urllib.request.ProxyHandler):
    # - this targets cpython 2.6, it might not work on a different version.
    # - this only supports proxy for http, ftp and https. I did not try to
    #   find the exact reason why, but it looks like the list of '*_open'
    #   method is built at opener creation time, so it's impossible to have
    #   something truly dynamic without hacking urllib2 more

    def __init__(self, proxies):
        # do NOT call ProxyHandler.__init__. We still need to
        # inherit from it to fit in urllib2 handlers framework
        self._proxies = proxies

    def _generic_open(self, proto, req):
        if proto in self._proxies:
            try:
                proxy = self._proxies[proto]
            except KeyError:
                # just in case a race condition happens, although it should
                # not in theory
                return None
            else:
                return self.proxy_open(req, proxy, proto)
        else:
            return None

    def http_open(self, req):
        return self._generic_open('http', req)

    def ftp_open(self, req):
        return self._generic_open('ftp', req)

    def https_open(self, req):
        return self._generic_open('https', req)
