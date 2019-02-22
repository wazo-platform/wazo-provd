# -*- coding: utf-8 -*-
# Copyright 2010-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""This module add support to returning Deferred in Resource getChild/getChildWithDefault.
Only thing you need to do is to use this Site class instead of twisted.web.server.Site.

"""


import copy
import string
import logging

from collections import namedtuple
from twisted.internet import defer
from twisted.web import http
from twisted.web import server
from twisted.web import resource
from twisted.python.compat import nativeString
from twisted.web.resource import _computeAllowedMethods
from twisted.web.error import UnsupportedMethod

from provd.rest.server import auth
from provd.rest.server.helpers.tenants import Tenant, Tokens
from provd.app import InvalidIdError
from xivo.tenant_helpers import Users
from requests.exceptions import HTTPError

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


class AuthResource(resource.Resource):

    def render(self, request):
        render_method = self._extract_render_method(request)
        decorated_render_method = auth_verifier.verify_token(self, request, render_method)
        try:
            return decorated_render_method(request)
        except auth.auth_verifier.Unauthorized:
            request.setResponseCode(http.UNAUTHORIZED)
            return 'Unauthorized'

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

    def _build_tenant(self, request):
        auth_client = auth.get_auth_client()
        TenantInfo = namedtuple('TenantInfo', ('tenant_uuid', 'tokens', 'users'))

        tokens = Tokens(auth_client)
        users = Users(auth_client)
        tenant = Tenant.autodetect(request, tokens, users).uuid

        return TenantInfo(tenant, tokens, users)

    def _build_tenant_list(self, request, tenant_info=None, recurse=False):
        params = request.args

        auth_client = auth.get_auth_client()
        tenant, tokens, users = tenant_info or self._build_tenant(request)

        # request.args is a dict of list, but since we expect recurse to be present
        # only one time in the request arguments we take the first value
        recurse = recurse or params.get('recurse', [False])[0] in ['true', 'True']
        if not recurse:
            return [tenant]

        tenants = []

        try:
            tenants = auth_client.tenants.list(tenant_uuid=tenant)['items']
            logger.debug('Tenant listing got %s', tenants)
        except HTTPError as e:
            response = getattr(e, 'response', None)
            status_code = getattr(response, 'status_code', None)
            if status_code == 401:
                logger.debug('Tenant listing got a 401, returning %s', [tenant])
                return [tenant]
            raise

        return [t['uuid'] for t in tenants]

    @defer.inlineCallbacks
    def _verify_tenant(self, app, device_id, request):
        original_device = yield app._dev_get_or_raise(device_id)
        try:
            tenant_info = self._build_tenant(request)
        except Exception as e:
            raise InvalidIdError(e.message)

        tenant, tokens, users = tenant_info
        tenant_uuid = tenant_info.tenant_uuid
        logger.debug('Received tenant: %s', tenant_uuid)

        # No tenant change, so it is valid
        if original_device['tenant_uuid'] == tenant_uuid:
            defer.returnValue(tenant_uuid)

        auth_client = auth.get_auth_client()
        tenant_uuids = self._build_tenant_list(request, tenant_info=tenant_info, recurse=True)
        provd_tenant_uuid = auth_client.token.get(app.token())['metadata']['tenant_uuid']

        if (
            original_device['tenant_uuid'] in tenant_uuids
            or original_device['tenant_uuid'] == provd_tenant_uuid
        ):
            defer.returnValue(tenant_uuid)
        else:
            raise InvalidIdError('Invalid tenant for device "%s"', id)


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
    request.setHeader('Access-Control-Allow-Headers', 'origin,x-requested-with,accept,content-type,x-auth-token,Wazo-Tenant')
    request.setHeader('Access-Control-Allow-Credentials', 'false')
