# -*- coding: utf-8 -*-
# Copyright 2010-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

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
from provd.rest.server.helpers.tenants import Tenant, Tokens
from provd.app import InvalidIdError
from xivo.tenant_helpers import Users, UnauthorizedTenant
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

    def _extract_tenant_uuid(self, request):
        auth_client = auth.get_auth_client()

        tokens = Tokens(auth_client)
        users = Users(auth_client)
        try:
            tenant_uuid = Tenant.autodetect(request, tokens, users).uuid
        except UnauthorizedTenant as e:
            raise InvalidIdError(e.message)

        return tenant_uuid

    def _build_tenant_list(self, tenant_uuid=None, recurse=False):
        auth_client = auth.get_auth_client()

        if not recurse:
            return [tenant_uuid]

        try:
            tenants = auth_client.tenants.list(tenant_uuid=tenant_uuid)['items']
            logger.debug('Tenant listing got %s', tenants)
        except HTTPError as e:
            response = getattr(e, 'response', None)
            status_code = getattr(response, 'status_code', None)
            if status_code == 401:
                logger.debug('Tenant listing got a 401, returning %s', [tenant_uuid])
                return [tenant_uuid]
            raise

        return [t['uuid'] for t in tenants]

    def _build_tenant_list_from_request(self, request, recurse=False):
        tenant_uuid = self._extract_tenant_uuid(request)
        return self._build_tenant_list(tenant_uuid=tenant_uuid, recurse=recurse)

    @defer.inlineCallbacks
    def _verify_tenant(self, app, request, device_id):
        device = yield app._dev_get_or_raise(device_id)
        tenant_uuid = self._extract_tenant_uuid(request)
        logger.debug('Received tenant: %s', tenant_uuid)

        if device['tenant_uuid'] == tenant_uuid:
            defer.returnValue(tenant_uuid)

        auth_client = auth.get_auth_client()
        tenant_uuids = self._build_tenant_list(tenant_uuid=tenant_uuid, recurse=True)
        provd_tenant_uuid = auth_client.token.get(app.token())['metadata']['tenant_uuid']
        logger.debug('Provd tenant is %s', provd_tenant_uuid)
        logger.debug('Device tenant_uuid: %s', device['tenant_uuid'])
        if device['tenant_uuid'] in tenant_uuids:
            defer.returnValue(tenant_uuid)

        raise InvalidIdError('Invalid tenant for device "%s"', device_id)

    @defer.inlineCallbacks
    def _verify_tenant_on_update(self, app, request, device_id):
        device = yield app._dev_get_or_raise(device_id)
        tenant_uuid = self._extract_tenant_uuid(request)
        logger.debug('Received tenant: %s', tenant_uuid)

        if device['tenant_uuid'] == tenant_uuid:
            defer.returnValue(tenant_uuid)

        auth_client = auth.get_auth_client()
        tenant_uuids = self._build_tenant_list(tenant_uuid=tenant_uuid, recurse=True)
        provd_tenant_uuid = auth_client.token.get(app.token())['metadata']['tenant_uuid']
        logger.debug('Provd tenant is %s', provd_tenant_uuid)
        logger.debug('Device tenant_uuid: %s', device['tenant_uuid'])
        if device['tenant_uuid'] in tenant_uuids or device['tenant_uuid'] == provd_tenant_uuid:
            defer.returnValue(tenant_uuid)

        raise InvalidIdError('Invalid tenant for device "%s"', device_id)


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
