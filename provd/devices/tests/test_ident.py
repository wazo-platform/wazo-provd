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

from hamcrest import assert_that, equal_to, has_entry
from mock import Mock
from provd.devices.ident import LastSeenUpdater, VotingUpdater, _RequestHelper,\
    RemoveOutdatedIpDeviceUpdater
from twisted.internet import defer
from twisted.trial import unittest


class TestLastSeenUpdater(unittest.TestCase):

    def setUp(self):
        self.updater = LastSeenUpdater()

    def test_last_seen_updater_set_on_conflict(self):
        dev_infos = [
            {'k1': 'v1'},
            {'k1': 'v2'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v2'})

    def test_last_seen_updater_noop_on_nonconflict(self):
        dev_infos = [
            {'k1': 'v1'},
            {'k2': 'v2'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1', 'k2': 'v2'})


class TestVotingUpdater(unittest.TestCase):

    def setUp(self):
        self.updater = VotingUpdater()

    def test_voting_updater_votes_for_only_if_only_one(self):
        dev_infos = [
            {'k1': 'v1'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1'})

    def test_voting_updater_votes_for_highest_1(self):
        dev_infos = [
            {'k1': 'v1'},
            {'k1': 'v1'},
            {'k1': 'v2'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1'})

    def test_voting_updater_votes_for_highest_2(self):
        dev_infos = [
            {'k1': 'v2'},
            {'k1': 'v1'},
            {'k1': 'v1'},
        ]

        for dev_info in dev_infos:
            self.updater.update(dev_info)

        self.assertEqual(self.updater.dev_info, {'k1': 'v1'})


class TestRemoveOutdatedIpDeviceUpdater(unittest.TestCase):

    def setUp(self):
        self.app = Mock()
        self.app.nat = 0
        self.dev_updater = RemoveOutdatedIpDeviceUpdater(self.app)

    @defer.inlineCallbacks
    def test_nat_disabled(self):
        device = {
            u'id': u'abc',
        }
        dev_info = {
            u'ip': u'1.1.1.1',
        }
        self.app.dev_find.return_value = defer.succeed([])

        yield self.dev_updater.update(device, dev_info, 'http', Mock())

        self.app.dev_find.assert_called_once_with({u'ip': u'1.1.1.1', u'id': {'$ne': u'abc'}})

    @defer.inlineCallbacks
    def test_nat_enabled(self):
        device = {
            u'id': u'abc',
        }
        dev_info = {
            u'ip': u'1.1.1.1',
        }
        self.app.nat = 1

        yield self.dev_updater.update(device, dev_info, 'http', Mock())

        self.assertFalse(self.app.dev_find.called)


class TestRequestHelper(unittest.TestCase):

    def setUp(self):
        self.app = Mock()
        self.request = Mock()
        self.request_type = Mock()
        self.helper = _RequestHelper(self.app, self.request, self.request_type, 1)

    @defer.inlineCallbacks
    def test_extract_device_info_no_info(self):
        extractor = self._new_dev_info_extractor_mock(None)

        dev_info = yield self.helper.extract_device_info(extractor)

        extractor.extract.assert_called_once_with(self.request, self.request_type)
        assert_that(dev_info, equal_to({}))

    @defer.inlineCallbacks
    def test_extract_device_info_with_info(self):
        expected = {'a': 1}
        extractor = self._new_dev_info_extractor_mock(expected)

        dev_info = yield self.helper.extract_device_info(extractor)

        extractor.extract.assert_called_once_with(self.request, self.request_type)
        assert_that(dev_info, equal_to(expected))

    @defer.inlineCallbacks
    def test_retrieve_device_no_device(self):
        retriever = self._new_dev_retriever_mock(None)
        dev_info = {}

        device = yield self.helper.retrieve_device(retriever, dev_info)

        retriever.retrieve.assert_called_once_with(dev_info)
        assert_that(device, equal_to(None))

    @defer.inlineCallbacks
    def test_retrieve_device_with_device(self):
        expected = {u'id': u'a'}
        retriever = self._new_dev_retriever_mock(expected)
        dev_info = Mock()

        device = yield self.helper.retrieve_device(retriever, dev_info)

        retriever.retrieve.assert_called_once_with(dev_info)
        assert_that(device, equal_to(expected))

    @defer.inlineCallbacks
    def test_update_device_no_device(self):
        dev_updater = self._new_dev_updater_mock()
        device = None
        dev_info = {}

        yield self.helper.update_device(dev_updater, device, dev_info)

        self.assertFalse(dev_updater.update.called)

    @defer.inlineCallbacks
    def test_update_device_on_no_device_change_and_no_remote_state_update(self):
        dev_updater = self._new_dev_updater_mock()
        device = {u'id': u'a'}
        dev_info = {}

        yield self.helper.update_device(dev_updater, device, dev_info)

        dev_updater.update.assert_called_once_with(device, dev_info, self.request, self.request_type)
        self.assertFalse(self.app.cfg_retrieve.called)
        self.assertFalse(self.app.dev_update.called)

    @defer.inlineCallbacks
    def test_update_device_on_no_device_change_and_remote_state_update(self):
        dev_updater = self._new_dev_updater_mock()
        device = {
            u'id': u'a',
            u'configured': True,
            u'plugin': u'foo',
            u'config': u'a',
        }
        dev_info = {}
        self.request = Mock()
        self.request.path = '001122334455.cfg'
        self.request_type = 'http'
        plugin = Mock()
        plugin.get_remote_state_trigger_filename.return_value = '001122334455.cfg'
        self.app.pg_mgr.get.return_value = plugin
        self.app.cfg_retrieve.return_value = {
            u'raw_config': {
                u'sip_lines': {
                    u'1': {
                        u'username': 'foobar',
                    }
                }
            }
        }
        self.helper = _RequestHelper(self.app, self.request, self.request_type, 1)

        yield self.helper.update_device(dev_updater, device, dev_info)

        dev_updater.update.assert_called_once_with(device, dev_info, self.request, self.request_type)
        self.app.cfg_retrieve.assert_called_once_with(device[u'config'])
        self.app.dev_update.assert_called_once_with(device)
        assert_that(device, has_entry(u'remote_state_sip_username', u'foobar'))

    @defer.inlineCallbacks
    def test_update_device_on_device_change_and_remote_state_update(self):
        dev_updater = self._new_dev_updater_mock({u'vendor': u'xivo'})
        device = {
            u'id': u'a',
            u'configured': True,
            u'plugin': u'foo',
            u'config': u'a',
        }
        dev_info = {}
        self.request = Mock()
        self.request.path = '001122334455.cfg'
        self.request_type = 'http'
        plugin = Mock()
        plugin.get_remote_state_trigger_filename.return_value = '001122334455.cfg'
        self.app.pg_mgr.get.return_value = plugin
        self.app.cfg_retrieve.return_value = {
            u'raw_config': {
                u'sip_lines': {
                    u'1': {
                        u'username': 'foobar',
                    }
                }
            }
        }
        self.helper = _RequestHelper(self.app, self.request, self.request_type, 1)

        yield self.helper.update_device(dev_updater, device, dev_info)

        dev_updater.update.assert_called_once_with(device, dev_info, self.request, self.request_type)
        self.app.dev_update.assert_called_once_with(device, pre_update_hook=self.helper._pre_update_hook)

    def test_get_plugin_id_no_device(self):
        device = None

        pg_id = self.helper.get_plugin_id(device)

        assert_that(pg_id, equal_to(None))

    def test_get_plugin_id_no_plugin_key(self):
        device = {u'id': u'a'}

        pg_id = self.helper.get_plugin_id(device)

        assert_that(pg_id, equal_to(None))

    def test_get_plugin_id_ok(self):
        device = {u'id': u'a', u'plugin': u'xivo-foo'}

        pg_id = self.helper.get_plugin_id(device)

        assert_that(pg_id, equal_to(u'xivo-foo'))

    def _new_dev_info_extractor_mock(self, return_value):
        dev_info_extractor = Mock()
        dev_info_extractor.extract.return_value = defer.succeed(return_value)
        return dev_info_extractor

    def _new_dev_retriever_mock(self, return_value):
        dev_retriever = Mock()
        dev_retriever.retrieve.return_value = defer.succeed(return_value)
        return dev_retriever

    def _new_dev_updater_mock(self, device_update={}):
        dev_updater = Mock()
        def update_fun(device, dev_info, request, request_type):
            device.update(device_update)
            return defer.succeed(None)

        dev_updater.update.side_effect = update_fun
        return dev_updater
