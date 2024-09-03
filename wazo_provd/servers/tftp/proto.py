# Copyright 2010-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, BinaryIO, Callable, Union

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

from wazo_provd.servers.tftp.connection import RFC1350Connection, RFC2347Connection
from wazo_provd.servers.tftp.packet import (
    ERR_UNDEF,
    OP_RRQ,
    OP_WRQ,
    PacketError,
    RequestPacket,
    build_dgram,
    err_packet,
    oack_packet,
    parse_dgram,
)
from wazo_provd.util import encode_bytes

if TYPE_CHECKING:
    from ...devices.ident import DevTFTPRequest, TFTPRequestProcessingService

logger = logging.getLogger(__name__)

AcceptCallback = Callable[[Union[BinaryIO]], None]
RejectCallback = Callable[[bytes, Union[str, bytes]], None]


class _Response:
    def __init__(self, freject: RejectCallback, faccept: AcceptCallback) -> None:
        self._answered = False
        self._do_reject = freject
        self._do_accept = faccept

    def _raise_if_answered(self) -> None:
        if self._answered:
            raise ValueError('Request has already been answered')
        else:
            self._answered = True

    def ignore(self) -> None:
        self._raise_if_answered()

    def reject(self, errcode: bytes, errmsg: str | bytes) -> None:
        self._raise_if_answered()
        self._do_reject(errcode, errmsg)

    def accept(self, fobj: BinaryIO) -> None:
        self._raise_if_answered()
        self._do_accept(fobj)


class TFTPProtocol(DatagramProtocol):
    def __init__(self) -> None:
        self._service: TFTPRequestProcessingService | None = None

    def set_tftp_request_processing_service(
        self, tftp_request_processing_service: TFTPRequestProcessingService | None
    ) -> None:
        self._service = tftp_request_processing_service

    def _handle_rrq(self, pkt: RequestPacket, addr: str) -> None:
        if self._service is None:
            dgram = build_dgram(err_packet(ERR_UNDEF, b'service unavailable'))
            self.transport.write(dgram, addr)
            return

        # only accept mode octet
        if pkt['mode'] != b'octet':
            logger.warning('TFTP mode not supported: %s', pkt['mode'])
            r_dgram = build_dgram(err_packet(ERR_UNDEF, b'mode not supported'))
            self.transport.write(r_dgram, addr)
        else:

            def on_reject(errcode: bytes, errmsg: bytes | str) -> None:
                # do not format errcode as %s since it's the raw error code
                # sent in the TFTP packet, for example '\x00\x11'
                logger.info('TFTP read request rejected: %s', errmsg)

                self.transport.write(
                    build_dgram(err_packet(errcode, encode_bytes(errmsg))), addr
                )

            def on_accept(fobj: BinaryIO) -> None:
                logger.info('TFTP read request accepted')
                if 'blksize' in pkt['options']:
                    blksize: int = pkt['options']['blksize']  # type: ignore
                    logger.debug('Using TFTP blksize of %s', blksize)
                    oack_dgram = build_dgram(oack_packet({b'blksize': blksize}))
                    connection = RFC2347Connection(addr, fobj, oack_dgram)
                    connection.blksize = blksize
                else:
                    connection = RFC1350Connection(addr, fobj)
                reactor.listenUDP(0, connection)

            request: DevTFTPRequest = {'address': addr, 'packet': pkt}  # type: ignore
            response = _Response(on_reject, on_accept)
            self._service.handle_read_request(request, response)

    def _handle_wrq(self, pkt: RequestPacket, addr: str) -> None:
        # we don't accept WRQ - send an error
        logger.info('TFTP write request not supported')
        dgram = build_dgram(err_packet(ERR_UNDEF, b'WRQ not supported'))
        self.transport.write(dgram, addr)

    def datagramReceived(self, dgram: bytes, addr: str) -> None:
        try:
            pkt = parse_dgram(dgram)
        except PacketError as e:
            # invalid datagram - ignore it
            logger.info('Received invalid TFTP datagram from %s: %s', addr, e)
        else:
            if pkt['opcode'] == OP_WRQ:
                logger.info('TFTP write request from %s', addr)
                request_pkt: RequestPacket = pkt  # type: ignore[assignment]
                self._handle_wrq(request_pkt, addr)
            elif pkt['opcode'] == OP_RRQ:
                logger.info('TFTP read request from %s', addr)
                request_pkt: RequestPacket = pkt  # type: ignore[assignment,no-redef]
                self._handle_rrq(request_pkt, addr)
            else:
                logger.info('Ignoring non-request packet from %s', addr)
