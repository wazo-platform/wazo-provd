# Copyright 2010-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""TFTP service definition module."""

import os
from abc import ABCMeta
from io import StringIO

from provd.servers.tftp.packet import ERR_FNF


class AbstractTFTPReadService(metaclass=ABCMeta):
    """A TFTP read service handles TFTP read requests (RRQ)."""

    def handle_read_request(self, request, response):
        """Handle a TFTP read request (RRQ).

        request is a dictionary with the following keys:
          address -- the address of the client (an (ip, port) tuple)
          packet -- the RRQ packet sent by the client

        response is an object with the following methods:
          accept -- call this method with a file-like object you
            want to transfer if you accept the request.
          reject -- call this method with an errcode (2-byte string)
            and an error message if you reject the request. This will
            send an error packet to the client.
          ignore -- call this method if you want to silently ignore
            the request. You'll get the same behaviour if you call no
            method of the response object.

        Note that it's fine not to call one of the response methods before
        returning the control to the caller, i.e. for an asynchronous use.
        If you never eventually call one of the response methods, it will
        implicitly behave like if you had called the ignore method.

        """


class TFTPNullService:
    """A read service that always reject the requests."""

    def __init__(self, errcode=ERR_FNF, errmsg="File not found"):
        self.errcode = errcode
        self.errmsg = errmsg

    def handle_read_request(self, request, response):
        response.reject(self.errcode, self.errmsg)


class TFTPStringService:
    """A read service that always serve the same string."""
    def __init__(self, msg):
        self._msg = msg

    def handle_read_request(self, request, response):
        response.accept(StringIO(self._msg))


class TFTPFileService:
    """A read service that serve files under a path.

    It strips any leading path separator of the requested filename. For
    example, filename '/foo.txt' is the same as 'foo.txt'.

    It also rejects any request that makes reference to the parent directory
    once normalized. For example, a request for filename 'bar/../../foo.txt'
    will be rejected even if 'foo.txt' exist in the parent directory.

    """
    def __init__(self, path):
        self._path = os.path.abspath(path)

    def handle_read_request(self, request, response):
        rq_orig_path = request['packet']['filename'].decode('ascii')
        rq_stripped_path = rq_orig_path.lstrip(os.sep)
        rq_final_path = os.path.normpath(os.path.join(self._path, rq_stripped_path))
        if not rq_final_path.startswith(self._path):
            response.reject(ERR_FNF, b'Invalid filename')
        else:
            try:
                fobj = open(rq_final_path, 'rb')
            except IOError:
                response.reject(ERR_FNF, b'File not found')
            else:
                response.accept(fobj)


class TFTPHookService:
    """Base class for non-terminal read service.

    Services that only want to inspect the request should derive from this
    class and override the _pre_handle method.

    """
    def __init__(self, service):
        self._service = service

    def _pre_handle(self, request):
        """This MAY be overridden in derived classes."""
        pass

    def handle_read_request(self, request, response):
        self._pre_handle(request)
        self._service.handle_read_request(request, response)


class TFTPLogService(TFTPHookService):
    """A small hook service that permits logging of the requests."""
    def __init__(self, logger, service):
        """
        logger -- a callable object taking a string as argument

        """
        TFTPHookService.__init__(self, service)
        self._logger = logger

    def _pre_handle(self, request):
        packet = request['packet']
        msg = f"TFTP request from {request['address']} - filename '{packet['filename']}' - mode '{packet['mode']}'"
        if packet['options']:
            msg += f"- options '{packet['options']}'"
        self._logger(msg)
