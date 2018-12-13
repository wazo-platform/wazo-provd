# -*- coding: utf-8 -*-
# Copyright 2010-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

"""This module add support to returning Deferred in Resource getChild/getChildWithDefault.
Only thing you need to do is to use this Site class instead of twisted.web.server.Site.

"""


import copy
import string
import logging
from twisted.internet import defer
from twisted.web import http
from twisted.web import server
from twisted.web import resource
from twisted.python.compat import nativeString
from twisted.web.resource import _computeAllowedMethods
from twisted.web.error import UnsupportedMethod

from provd.rest.server import auth

logger = logging.getLogger(__name__)

auth_verifier = auth.get_auth_verifier()


class Request(server.Request):
    # originally taken from twisted.web.server.Request
    def process(self):
        "Process a request."

        # get site from channel
        self.site = self.channel.site

        corsify_request(self)
        # set various default headers
        self.setHeader('server', server.version)
        self.setHeader('date', http.datetimeToString())
        self.setHeader('content-type', "text/html")

        # Resource Identification
        self.prepath = []
        self.postpath = map(server.unquote, string.split(self.path[1:], '/'))

        # We do not really care about the content if the request is a CORS preflight
        if self.method == 'OPTIONS':
            self.finish()
        else:
            d = self.site.getResourceFor(self)
            d.addCallback(self.render)
            d.addErrback(self.processingFailed)


class Resource(resource.Resource):

    def render(self, request):
        render_method = self._extract_render_method(request)
        try:
            render_method = auth_verifier.verify_token(self, request, render_method)
        except auth.auth_verifier.Unauthorized:
            request.setResponseCode(http.UNAUTHORIZED)
            return 'Unauthorized'

        return render_method(request)

    def _extract_render_method(self, request):
        # from twisted.web.resource.Resource
        render_method = getattr(self, 'render_' + nativeString(request.method), None)
        if not render_method:
            try:
                allowedMethods = self.allowedMethods
            except AttributeError:
                allowedMethods = _computeAllowedMethods(self)
            raise UnsupportedMethod(allowedMethods)
        return render_method

    def render_OPTIONS(self, request):
        return ''


class AuthResource(Resource):

    def __init__(self, *args, **kwargs):
        Resource.__init__(self, *args, **kwargs)


class Site(server.Site):
    # originally taken from twisted.web.server.Site
    requestFactory = Request

    def getResourceFor(self, request):
        """
        Get a deferred that will callback with a resource for a request.

        This iterates through the resource heirarchy, calling
        getChildWithDefault on each resource it finds for a path element,
        stopping when it hits an element where isLeaf is true.
        """
        request.site = self
        # Sitepath is used to determine cookie names between distributed
        # servers and disconnected sites.
        request.sitepath = copy.copy(request.prepath)
        return getChildForRequest(self.resource, request)


@defer.inlineCallbacks
def getChildForRequest(resource, request):
    # originally taken from twisted.web.resource
    """
    Traverse resource tree to find who will handle the request.
    """
    while request.postpath and not resource.isLeaf:
        pathElement = request.postpath.pop(0)
        request.prepath.append(pathElement)
        retval = resource.getChildWithDefault(pathElement, request)
        if isinstance(retval, defer.Deferred):
            resource = yield retval
        else:
            resource = retval
    defer.returnValue(resource)


def corsify_request(request):
    # CORS
    request.setHeader('Access-Control-Allow-Origin', '*')
    request.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    request.setHeader('Access-Control-Allow-Headers', 'origin,x-requested-with,accept,content-type,x-auth-token')
    request.setHeader('Access-Control-Allow-Credentials', 'false')
