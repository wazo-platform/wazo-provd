# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""HTTP service definition module.

Note that while we often talk in 'service', since we are using twisted.web
and its built around the concept of resource, a service is in fact an object
implementing twisted.web.resource.IResource.

"""
from __future__ import annotations

from twisted.internet import defer
from twisted.web import http, resource, static

IHTTPService = resource.IResource
"""An HTTP service is exactly the same thing as an IResource."""


class BaseHTTPHookService(resource.Resource):
    """Base class for HTTPHookService. Not made to be instantiated directly."""

    def __init__(self, service):
        super().__init__()
        self._service = service

    def _next_service(self, path, request):
        # should be called in getChild method
        resrc = self._service
        if resrc.isLeaf:
            request.postpath.insert(0, request.prepath.pop())
            return resrc
        return resrc.getChildWithDefault(path, request)


class HTTPHookService(BaseHTTPHookService):
    """Base class for synchronous non-terminal service."""

    def _pre_handle(self, path, request):
        """This SHOULD be overridden in derived classes."""
        pass

    def getChild(self, path, request):
        self._pre_handle(path, request)
        return self._next_service(path, request)


class HTTPAsyncHookService(BaseHTTPHookService):
    """Base class for asynchronous non-terminal service.

    This is useful if you have a hook service that modify the state of the
    application but needs to wait for a callback to fire before the service
    chain can continue, because other services below this hook depends on some
    yet to come side effect.

    The callback is only used for flow control -- it should fire with a None
    value, since this value is going to be ignored.

    IT CAN ONLY BE USED WITH A NON STANDARD IMPLEMENTATION OF SITE (see
    provd.servers.http_site.Site).

    """

    def _pre_handle(self, path, request):
        """This SHOULD be overridden in derived classes and must return a
        deferred that will eventually fire.

        """
        return defer.succeed(None)

    def getChild(self, path, request):
        d = self._pre_handle(path, request)
        d.addCallback(lambda _: self._next_service(path, request))
        return d


class HTTPLogService(HTTPHookService):
    """A small hook service that permits logging of the request."""

    def __init__(self, logger, service):
        """
        logger -- a callable object taking a string as argument

        """
        super().__init__(service)
        self._logger = logger

    def _pre_handle(self, path, request):
        self._logger(f'{path} ---- {request}')


class HTTPNoListingFileService(static.File):
    """Similar to twisted.web.static.File except that instead of listing the
    content of directories, it returns a 403 Forbidden.
    """

    _FORBIDDEN_RESOURCE = resource.ErrorPage(
        http.FORBIDDEN, 'Forbidden', 'Directory listing not permitted.'
    )
    _NOT_ALLOWED_RESOURCE = resource.ErrorPage(
        http.NOT_ALLOWED, 'Method Not Allowed', 'Method not allowed.'
    )

    def directoryListing(self):
        return self._FORBIDDEN_RESOURCE

    def getChild(self, path, request):
        if request.method != b'GET':
            return self._NOT_ALLOWED_RESOURCE
        return static.File.getChild(self, path, request)
