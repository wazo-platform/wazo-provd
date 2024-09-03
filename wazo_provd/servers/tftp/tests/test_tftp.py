# Copyright 2010-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest

from wazo_provd.servers.tftp.packet import OP_RRQ, PacketError, parse_dgram


class TestTFTP(unittest.TestCase):
    def test_parse_valid_rrq_dgram_correctly(self) -> None:
        self.assertEqual(
            {'opcode': OP_RRQ, 'filename': b'fname', 'mode': b'mode', 'options': {}},
            parse_dgram(b'\x00\x01fname\x00mode\x00'),
        )

    def test_parse_invalid_rrq_yield_packeterror(self) -> None:
        self.assertRaises(PacketError, parse_dgram, b'\x00\x01fname\x00mode')
        self.assertRaises(PacketError, parse_dgram, b'')
        self.assertRaises(PacketError, parse_dgram, b'\x01')
        self.assertRaises(PacketError, parse_dgram, b'\x00\x01')

    def test_parse_invalid_error_datagram_raise_error(self) -> None:
        datagram = b'\x00\x05\x00\x01'

        self.assertRaises(PacketError, parse_dgram, datagram)
