# -*- coding: utf-8 -*-

# Copyright (C) 2010-2014 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

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
