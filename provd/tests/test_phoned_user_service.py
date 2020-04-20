# -*- coding: utf-8 -*-
# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from hamcrest import assert_that, equal_to, has_key, not_
from provd.phoned_user_service import add_wazo_phoned_user_service_url


class TestAddWazoPhonedUserServiceURL(unittest.TestCase):

    def setUp(self):
        self.raw_config = {
            u'X_xivo_phonebook_ip': u'8.8.8.8',
            u'X_xivo_user_uuid': u'12-345',
        }

    def test_add_wazo_phoned_user_service_url_minimal(self):
        add_wazo_phoned_user_service_url(self.raw_config, u'acme', u'dnd')

        expected = u'http://8.8.8.8:9498/0.1/acme/user_service/dnd?user_uuid=12-345&enabled=True'
        assert_that(self.raw_config[u'XX_wazo_phoned_user_service_dnd_enabled_url'], equal_to(expected))

        expected = u'http://8.8.8.8:9498/0.1/acme/user_service/dnd?user_uuid=12-345&enabled=False'
        assert_that(self.raw_config[u'XX_wazo_phoned_user_service_dnd_disabled_url'], equal_to(expected))

    def test_add_wazo_phoned_user_service_url_full(self):
        self.raw_config[u'X_xivo_phonebook_scheme'] = u'https'
        self.raw_config[u'X_xivo_phonebook_port'] = 1234
        add_wazo_phoned_user_service_url(self.raw_config, u'acme', u'fwdall', destination=u'1234')

        expected = u'https://8.8.8.8:1234/0.1/acme/user_service/fwdall?user_uuid=12-345&enabled=True&destination=1234'
        assert_that(self.raw_config[u'XX_wazo_phoned_user_service_fwdall_enabled_url'], equal_to(expected))

        expected = u'https://8.8.8.8:1234/0.1/acme/user_service/fwdall?user_uuid=12-345&enabled=False'
        assert_that(self.raw_config[u'XX_wazo_phoned_user_service_fwdall_disabled_url'], equal_to(expected))

    def test_no_user_uuid_no_url(self):
        del self.raw_config[u'X_xivo_user_uuid']
        add_wazo_phoned_user_service_url(self.raw_config, u'acme', u'dnd')
        assert_that(self.raw_config, not_(has_key(u'XX_wazo_phoned_user_service_dnd_enabled_url')))
        assert_that(self.raw_config, not_(has_key(u'XX_wazo_phoned_user_service_dnd_disabled_url')))

    def test_no_hostname_no_url(self):
        del self.raw_config[u'X_xivo_phonebook_ip']
        add_wazo_phoned_user_service_url(self.raw_config, u'acme', u'dnd')
        assert_that(self.raw_config, not_(has_key(u'XX_wazo_phoned_user_service_dnd_enabled_url')))
        assert_that(self.raw_config, not_(has_key(u'XX_wazo_phoned_user_service_dnd_disabled_url')))
