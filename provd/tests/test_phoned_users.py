# -*- coding: utf-8 -*-
# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from hamcrest import assert_that, equal_to, has_key, not_
from provd.phoned_users import add_wazo_phoned_user_service_url


class TestAddWazoPhonedUserServiceURL(unittest.TestCase):

    def setUp(self):
        self.raw_config = {
            u'X_xivo_phonebook_ip': u'8.8.8.8',
            u'X_xivo_user_uuid': u'12-345',
        }

    def test_add_wazo_phoned_user_service_url(self):
        add_wazo_phoned_user_service_url(self.raw_config, u'acme', u'dnd')

        expected = u'http://8.8.8.8:9498/0.1/acme/users/12-345/services/dnd/enable'
        assert_that(self.raw_config[u'XX_wazo_phoned_user_service_dnd_enabled_url'], equal_to(expected))

        expected = u'http://8.8.8.8:9498/0.1/acme/users/12-345/services/dnd/disable'
        assert_that(self.raw_config[u'XX_wazo_phoned_user_service_dnd_disabled_url'], equal_to(expected))

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
