# -*- coding: utf-8 -*-
# Copyright 2014-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
from __future__ import unicode_literals

from mock import Mock
from twisted.internet import defer
from twisted.trial import unittest
from provd import synchronize


class TestStandardSipSynchronize(unittest.TestCase):

    def setUp(self):
        self.sync_service = Mock()
        self.sync_service.TYPE = 'AsteriskAMI'
        self._old_sync_service = synchronize._SYNC_SERVICE
        synchronize._SYNC_SERVICE = self.sync_service

    def tearDown(self):
        synchronize._SYNC_SERVICE = self._old_sync_service

    @defer.inlineCallbacks
    def test_no_sync_service(self):
        synchronize._SYNC_SERVICE = None
        device = {
            'id': 'a',
        }

        try:
            yield synchronize.standard_sip_synchronize(device)
        except synchronize.SynchronizeException:
            pass
        else:
            self.fail('Exception should have been raised')

    @defer.inlineCallbacks
    def test_empty_device(self):
        device = {
            'id': 'a',
        }

        try:
            yield synchronize.standard_sip_synchronize(device)
        except synchronize.SynchronizeException:
            pass
        else:
            self.fail('Exception should have been raised')

    @defer.inlineCallbacks
    def test_device_with_remote_state_sip_username(self):
        device = {
            'id': 'a',
            'remote_state_sip_username': 'foobar',
        }

        yield synchronize.standard_sip_synchronize(device)

        self.sync_service.sip_notify_by_peer.assert_called_once_with('foobar', 'check-sync', None)
