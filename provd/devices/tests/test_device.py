# -*- coding: utf-8 -*-
# Copyright (C) 2010-2014 Avencall
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, equal_to

import unittest
from provd.devices.device import copy, needs_reconfiguration


class TestDevice(unittest.TestCase):

    def test_copy_is_a_copy(self):
        device_orig = {u'id': u'1', u'mac': u'00:11:22:33:44:55'}

        device_copy = copy(device_orig)

        assert_that(device_copy, equal_to(device_orig))

    def test_copy_has_no_reference_to_orig(self):
        device_orig = {u'id': u'1', u'foo': [1]}

        device_copy = copy(device_orig)
        device_copy[u'foo'].append(2)

        assert_that(device_orig, equal_to({u'id': u'1', u'foo': [1]}))

    def test_is_reconfigured_needed_same_device(self):
        device = {u'id': u'1', u'config': u'a'}

        self.assertFalse(needs_reconfiguration(device, device))

    def test_is_reconfigured_needed_different_significant_key(self):
        old_device = {u'id': u'1', u'config': u'a'}
        new_device = {u'id': u'1', u'config': u'b'}

        self.assertTrue(needs_reconfiguration(old_device, new_device))

    def test_is_reconfigured_needed_different_unsignificant_key(self):
        old_device = {u'id': u'1', u'foo': u'a'}
        new_device = {u'id': u'1', u'foo': u'b'}

        self.assertFalse(needs_reconfiguration(old_device, new_device))
