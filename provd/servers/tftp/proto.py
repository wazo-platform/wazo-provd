# -*- coding: utf-8 -*-
# Copyright 2010-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
import logging
from provd.servers.tftp.connection import RFC2347Connection, RFC1350Connection
from provd.servers.tftp.packet import *
from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol

logger = logging.getLogger(__name__)


class _Response(object):
    def __init__(self, freject, faccept):
        self._answered = False
        self._do_reject = freject
        self._do_accept = faccept

    def _raise_if_answered(self):
        if self._answered:
            raise ValueError('Request has already been answered')
        else:
            self._answered = True

    def ignore(self):
        self._raise_if_answered()

    def reject(self, errcode, errmsg):
        self._raise_if_answered()
        self._do_reject(errcode, errmsg)

    def accept(self, fobj):
        self._raise_if_answered()
        self._do_accept(fobj)


class TFTPProtocol(DatagramProtocol):
    def __init__(self):
        self._service = None

    def set_tftp_request_processing_service(self, tftp_request_processing_service):
        self._service = tftp_request_processing_service

    def _handle_rrq(self, pkt, addr):
        if self._service is None:
            dgram = build_dgram(err_packet(ERR_UNDEF, 'service unavailable'))
            self.transport.write(dgram, addr)
            return

        # only accept mode octet
        if pkt['mode'] != 'octet':
            logger.warning('TFTP mode not supported: %s', pkt['mode'])
            r_dgram = build_dgram(err_packet(ERR_UNDEF, 'mode not supported'))
            self.transport.write(r_dgram, addr)
        else:
            def on_reject(errcode, errmsg):
                # do not format errcode as %s since it's the raw error code
                # sent in the TFTP packet, for example '\x00\x11'
                logger.info('TFTP read request rejected: %s', errmsg)
                self.transport.write(build_dgram(err_packet(errcode, errmsg)), addr)
            def on_accept(fobj):
                logger.info('TFTP read request accepted')
                if 'blksize' in pkt['options']:
                    blksize = pkt['options']['blksize']
                    logger.debug('Using TFTP blksize of %s', blksize)
                    oack_dgram = build_dgram(oack_packet({'blksize': str(blksize)}))
                    connection = RFC2347Connection(addr, fobj, oack_dgram)
                    connection.blksize = blksize
                else:
                    connection = RFC1350Connection(addr, fobj)
                reactor.listenUDP(0, connection)
            request = {'address': addr, 'packet': pkt}
            response = _Response(on_reject, on_accept)
            self._service.handle_read_request(request, response)

    def _handle_wrq(self, pkt, addr):
        # we don't accept WRQ - send an error
        logger.info('TFTP write request not supported')
        dgram = build_dgram(err_packet(ERR_UNDEF, 'WRQ not supported'))
        self.transport.write(dgram, addr)

    def datagramReceived(self, dgram, addr):
        try:
            pkt = parse_dgram(dgram)
        except PacketError as e:
            # invalid datagram - ignore it
            logger.info('Received invalid TFTP datagram from %s: %s', addr, e)
        else:
            if pkt['opcode'] == OP_WRQ:
                logger.info('TFTP write request from %s', addr)
                self._handle_wrq(pkt, addr)
            elif pkt['opcode'] == OP_RRQ:
                logger.info('TFTP read request from %s', addr)
                self._handle_rrq(pkt, addr)
            else:
                logger.info('Ignoring non-request packet from %s', addr)
