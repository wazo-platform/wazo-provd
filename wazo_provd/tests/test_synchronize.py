# Copyright 2014-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Generator
from unittest.mock import Mock

from twisted.internet import defer
from twisted.internet.defer import Deferred
from twisted.trial import unittest

from wazo_provd import synchronize


class TestStandardSipSynchronize(unittest.TestCase):
    def setUp(self) -> None:
        self.sync_service = Mock()
        self.sync_service.TYPE = 'AsteriskAMI'
        self._old_sync_service = synchronize._SYNC_SERVICE
        synchronize._SYNC_SERVICE = self.sync_service

    def tearDown(self) -> None:
        synchronize._SYNC_SERVICE = self._old_sync_service

    @defer.inlineCallbacks
    def test_no_sync_service(self) -> Generator[Deferred, None, None]:
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
    def test_empty_device(self) -> Generator[Deferred, None, None]:
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
    def test_device_with_remote_state_sip_username(
        self,
    ) -> Generator[Deferred, None, None]:
        device = {
            'id': 'a',
            'remote_state_sip_username': 'foobar',
        }

        yield synchronize.standard_sip_synchronize(device)

        self.sync_service.sip_notify_by_peer.assert_called_once_with(
            'foobar', 'check-sync', None
        )
