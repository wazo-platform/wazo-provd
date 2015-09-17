# -*- coding: utf-8 -*-

# Copyright (C) 2015 Avencall
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

from hamcrest import assert_that, equal_to, is_not, has_key
from provd.phonebook import add_xivo_phonebook_url, add_xivo_phonebook_url_from_format


class TestAddXiVOPhonebookURL(unittest.TestCase):

    def setUp(self):
        self.raw_config = {
            u'config_version': 1,
            u'X_xivo_phonebook_ip': u'8.8.8.8',
            u'X_xivo_phonebook_profile': u'prof',
            u'X_xivo_user_uuid': u'12-345',
        }

    def test_add_xivo_phonebook_url_minimal(self):
        add_xivo_phonebook_url(self.raw_config, u'acme')

        expected = u'http://8.8.8.8:9498/0.1/directories/input/prof/acme?xivo_user_uuid=12-345'
        assert_that(self.raw_config[u'XX_xivo_phonebook_url'], equal_to(expected))

    def test_add_xivo_phonebook_url_full(self):
        add_xivo_phonebook_url(self.raw_config, u'acme', entry_point=u'ep', qs_prefix=u'p=1', qs_suffix=u's=2')

        expected = u'http://8.8.8.8:9498/0.1/directories/ep/prof/acme?p=1&xivo_user_uuid=12-345&s=2'
        assert_that(self.raw_config[u'XX_xivo_phonebook_url'], equal_to(expected))


class TestAddXiVOPhonebookURLFromFormat(unittest.TestCase):

    def setUp(self):
        self.url_format = u'{scheme}://{hostname}:{port}/{profile}?xivo_user_uuid={user_uuid}'
        self.raw_config = {
            u'config_version': 1,
            u'X_xivo_phonebook_ip': u'8.8.8.8',
            u'X_xivo_phonebook_profile': u'prof',
            u'X_xivo_user_uuid': u'12-345',
        }

    def test_add_xivo_phonebook_url_from_format_no_ip(self):
        del self.raw_config[u'X_xivo_phonebook_ip']

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        assert_that(self.raw_config, is_not(has_key(u'XX_xivo_phonebook_url')))

    def test_add_xivo_phonebook_url_from_format_wrong_config_version(self):
        self.raw_config[u'config_version'] = 0

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        assert_that(self.raw_config, is_not(has_key(u'XX_xivo_phonebook_url')))

    def test_add_xivo_phonebook_url_from_format_no_profile(self):
        del self.raw_config[u'X_xivo_phonebook_profile']

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        assert_that(self.raw_config, is_not(has_key(u'XX_xivo_phonebook_url')))

    def test_add_xivo_phonebook_url_from_format_no_user_uuid(self):
        del self.raw_config[u'X_xivo_user_uuid']

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        assert_that(self.raw_config, is_not(has_key(u'XX_xivo_phonebook_url')))

    def test_add_xivo_phonebook_url_from_format_full(self):
        self.raw_config[u'X_xivo_phonebook_scheme'] = u'https'
        self.raw_config[u'X_xivo_phonebook_port'] = 4242

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        expected = u'https://8.8.8.8:4242/prof?xivo_user_uuid=12-345'
        assert_that(self.raw_config[u'XX_xivo_phonebook_url'], equal_to(expected))
