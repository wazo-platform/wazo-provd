# -*- coding: utf-8 -*-
# Copyright 2010-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
import unittest
from provd.servers.tftp.packet import parse_dgram, PacketError, OP_RRQ


class TestTFTP(unittest.TestCase):

    def test_parse_valid_rrq_dgram_correctly(self):
        self.assertEqual({'opcode': OP_RRQ, 'filename': 'fname', 'mode': 'mode', 'options': {}},
                         parse_dgram('\x00\x01fname\x00mode\x00'))

    def test_parse_invalid_rrq_yield_packeterror(self):
        self.assertRaises(PacketError, parse_dgram, '\x00\x01fname\x00mode')
        self.assertRaises(PacketError, parse_dgram, '')
        self.assertRaises(PacketError, parse_dgram, '\x01')
        self.assertRaises(PacketError, parse_dgram, '\x00\x01')

    def test_parse_invalid_error_datagram_raise_error(self):
        datagram = '\x00\x05\x00\x01'

        self.assertRaises(PacketError, parse_dgram, datagram)
