# Copyright 2010-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""TFTP service definition module."""
from __future__ import annotations

import os
from abc import ABCMeta
from collections.abc import Callable
from io import BytesIO
from typing import TYPE_CHECKING, TypedDict

from ...servers.tftp.packet import ERR_FNF, RequestPacket

if TYPE_CHECKING:
    from ...servers.tftp.proto import _Response


class TFTPRequest(TypedDict):
    # Comments say it should be `tuple[str, int]`, but it seems to always receive a string
    address: str
    packet: RequestPacket


class AbstractTFTPReadService(metaclass=ABCMeta):
    """A TFTP read service handles TFTP read requests (RRQ)."""

    def handle_read_request(self, request: TFTPRequest, response: _Response) -> None:
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


class TFTPNullService(AbstractTFTPReadService):
    """A read service that always reject the requests."""

    def __init__(
        self, errcode: bytes = ERR_FNF, errmsg: str = "File not found"
    ) -> None:
        self.errcode = errcode
        self.errmsg = errmsg

    def handle_read_request(self, request: TFTPRequest, response: _Response):
        response.reject(self.errcode, self.errmsg)


class TFTPStringService(AbstractTFTPReadService):
    """A read service that always serve the same string."""

    def __init__(self, msg: str) -> None:
        self._msg = msg

    def handle_read_request(self, request: TFTPRequest, response: _Response) -> None:
        response.accept(BytesIO(self._msg.encode()))


class TFTPFileService(AbstractTFTPReadService):
    """A read service that serve files under a path.

    It strips any leading path separator of the requested filename. For
    example, filename '/foo.txt' is the same as 'foo.txt'.

    It also rejects any request that makes reference to the parent directory
    once normalized. For example, a request for filename 'bar/../../foo.txt'
    will be rejected even if 'foo.txt' exist in the parent directory.

    """

    def __init__(self, path: str) -> None:
        self._path = os.path.abspath(path)

    def handle_read_request(self, request: TFTPRequest, response: _Response) -> None:
        rq_orig_path = request['packet']['filename'].decode('ascii')
        rq_stripped_path = rq_orig_path.lstrip(os.sep)
        rq_final_path = os.path.normpath(os.path.join(self._path, rq_stripped_path))
        if not rq_final_path.startswith(self._path):
            response.reject(ERR_FNF, b'Invalid filename')
        else:
            try:
                fobj = open(rq_final_path, 'rb')
            except OSError:
                response.reject(ERR_FNF, b'File not found')
            else:
                response.accept(fobj)


class TFTPHookService(AbstractTFTPReadService):
    """Base class for non-terminal read service.

    Services that only want to inspect the request should derive from this
    class and override the _pre_handle method.

    """

    def __init__(self, service: AbstractTFTPReadService) -> None:
        self._service = service

    def _pre_handle(self, request: TFTPRequest) -> None:
        """This MAY be overridden in derived classes."""
        pass

    def handle_read_request(self, request: TFTPRequest, response: _Response) -> None:
        self._pre_handle(request)
        self._service.handle_read_request(request, response)


class TFTPLogService(TFTPHookService):
    """A small hook service that permits logging of the requests."""

    def __init__(
        self, logger: Callable[[str], None], service: AbstractTFTPReadService
    ) -> None:
        """
        logger -- a callable object taking a string as argument

        """
        super().__init__(service)
        self._logger = logger

    def _pre_handle(self, request: TFTPRequest) -> None:
        packet = request['packet']
        msg = (
            f"TFTP request from {request['address']!r} - "
            f"filename '{packet['filename']!r}' - mode '{packet['mode']!r}'"
        )
        if packet['options']:
            msg += f"- options '{packet['options']!r}'"
        self._logger(msg)
