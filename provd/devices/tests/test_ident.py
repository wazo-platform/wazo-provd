# Copyright 2010-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, equal_to, has_entry
from unittest.mock import Mock, patch
from provd.devices import ident
from provd.devices.ident import LastSeenUpdater, VotingUpdater, _RequestHelper, \
    RemoveOutdatedIpDeviceUpdater, AddDeviceRetriever, RequestType
from twisted.internet import defer
from twisted.trial import unittest


class TestAddDeviceRetriever(unittest.TestCase):

    def setUp(self):
        self.app = Mock()
        self.dev_retriever = AddDeviceRetriever(self.app)

    @patch('provd.devices.ident.log_security_msg')
    @defer.inlineCallbacks
    def test_retrieve_log_security_event(self, mock_log_security_msg):
        device_id = 'some-id'
        device_ip = '169.254.1.1'
        dev_info = {
            'ip': device_ip,
        }
        self.app.dev_insert.return_value = defer.succeed(device_id)

        device = yield self.dev_retriever.retrieve(dev_info)

        mock_log_security_msg.assert_called_once_with('New device created automatically from %s: %s', device_ip, device_id)
        expected_device = dict(dev_info)
        expected_device['added'] = 'auto'
        assert_that(device, equal_to(expected_device))


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
            'id': 'abc',
        }
        dev_info = {
            'ip': '1.1.1.1',
        }
        self.app.dev_find.return_value = defer.succeed([])

        yield self.dev_updater.update(device, dev_info, 'http', Mock())

        self.app.dev_find.assert_called_once_with({'ip': '1.1.1.1', 'id': {'$ne': 'abc'}})

    @defer.inlineCallbacks
    def test_nat_enabled(self):
        device = {
            'id': 'abc',
        }
        dev_info = {
            'ip': '1.1.1.1',
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
        expected = {'id': 'a'}
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
        device = {'id': 'a'}
        dev_info = {}

        yield self.helper.update_device(dev_updater, device, dev_info)

        dev_updater.update.assert_called_once_with(device, dev_info, self.request, self.request_type)
        self.assertFalse(self.app.cfg_retrieve.called)
        self.assertFalse(self.app.dev_update.called)

    @defer.inlineCallbacks
    def test_update_device_on_no_device_change_and_remote_state_update(self):
        dev_updater = self._new_dev_updater_mock()
        device = {
            'id': 'a',
            'configured': True,
            'plugin': 'foo',
            'config': 'a',
        }
        dev_info = {}
        self.request = Mock()
        self.request.path = '001122334455.cfg'
        self.request_type = RequestType.HTTP
        plugin = Mock()
        plugin.get_remote_state_trigger_filename.return_value = '001122334455.cfg'
        self.app.pg_mgr.get.return_value = plugin
        self.app.cfg_retrieve.return_value = {
            'raw_config': {
                'sip_lines': {
                    '1': {
                        'username': 'foobar',
                    }
                }
            }
        }
        self.helper = _RequestHelper(self.app, self.request, self.request_type, 1)

        yield self.helper.update_device(dev_updater, device, dev_info)

        dev_updater.update.assert_called_once_with(device, dev_info, self.request, self.request_type)
        self.app.cfg_retrieve.assert_called_once_with(device['config'])
        self.app.dev_update.assert_called_once_with(device)
        assert_that(device, has_entry('remote_state_sip_username', 'foobar'))

    @defer.inlineCallbacks
    def test_update_device_on_device_change_and_remote_state_update(self):
        dev_updater = self._new_dev_updater_mock({'vendor': 'xivo'})
        device = {
            'id': 'a',
            'configured': True,
            'plugin': 'foo',
            'config': 'a',
        }
        dev_info = {}
        self.request = Mock()
        self.request.path = '001122334455.cfg'
        self.request_type = RequestType.HTTP
        plugin = Mock()
        plugin.get_remote_state_trigger_filename.return_value = '001122334455.cfg'
        self.app.pg_mgr.get.return_value = plugin
        self.app.cfg_retrieve.return_value = {
            'raw_config': {
                'sip_lines': {
                    '1': {
                        'username': 'foobar',
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
        device = {'id': 'a'}

        pg_id = self.helper.get_plugin_id(device)

        assert_that(pg_id, equal_to(None))

    def test_get_plugin_id_ok(self):
        device = {'id': 'a', 'plugin': 'xivo-foo'}

        pg_id = self.helper.get_plugin_id(device)

        assert_that(pg_id, equal_to('xivo-foo'))

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


class TestLogSensitiveRequest(unittest.TestCase):

    def setUp(self):
        self.ip = '169.254.0.1'
        self.filename = 'foobar.cfg'
        self.request_type = ident.RequestType.HTTP
        self.request = Mock()
        self.request.getClientIP.return_value = self.ip
        self.request.path = f'/{self.filename}'
        self.plugin = Mock()

    @patch('provd.devices.ident.log_security_msg')
    def test_no_log_when_plugin_doesnt_have_method(self, mock_log_security_msg):
        del self.plugin.is_sensitive_filename

        ident._log_sensitive_request(self.plugin, self.request, self.request_type)

        assert_that(mock_log_security_msg.called, equal_to(False))

    @patch('provd.devices.ident.log_security_msg')
    def test_log_when_sensitive_filename(self, mock_log_security_msg):
        self.plugin.is_sensitive_filename.return_value = True

        ident._log_sensitive_request(self.plugin, self.request, self.request_type)

        self.plugin.is_sensitive_filename.assert_called_once_with(self.filename)
        mock_log_security_msg.assert_called_once_with('Sensitive file requested from %s: %s',
                                                      self.ip, self.filename)
