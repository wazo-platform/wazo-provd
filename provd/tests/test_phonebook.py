# -*- coding: utf-8 -*-
# Copyright 2015-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
from __future__ import unicode_literals

import unittest

from hamcrest import assert_that, equal_to, is_not, has_key
from provd.phonebook import add_xivo_phonebook_url, add_xivo_phonebook_url_from_format


class TestAddXiVOPhonebookURL(unittest.TestCase):

    def setUp(self):
        self.raw_config = {
            'X_xivo_phonebook_ip': '8.8.8.8',
            'X_xivo_user_uuid': '12-345',
        }

    def test_add_xivo_phonebook_url_minimal(self):
        add_xivo_phonebook_url(self.raw_config, 'acme')

        expected = 'http://8.8.8.8:9498/0.1/directories/input/default/acme?xivo_user_uuid=12-345'
        assert_that(self.raw_config['XX_xivo_phonebook_url'], equal_to(expected))

    def test_add_xivo_phonebook_url_full(self):
        add_xivo_phonebook_url(self.raw_config, 'acme', entry_point='ep', qs_prefix='p=1', qs_suffix='s=2')

        expected = 'http://8.8.8.8:9498/0.1/directories/ep/default/acme?p=1&xivo_user_uuid=12-345&s=2'
        assert_that(self.raw_config['XX_xivo_phonebook_url'], equal_to(expected))


class TestAddXiVOPhonebookURLFromFormat(unittest.TestCase):

    def setUp(self):
        self.url_format = '{scheme}://{hostname}:{port}/{profile}?xivo_user_uuid={user_uuid}'
        self.raw_config = {
            'X_xivo_phonebook_ip': '8.8.8.8',
            'X_xivo_user_uuid': '12-345',
        }

    def test_add_xivo_phonebook_url_from_format_no_ip(self):
        del self.raw_config['X_xivo_phonebook_ip']

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        assert_that(self.raw_config, is_not(has_key('XX_xivo_phonebook_url')))

    def test_add_xivo_phonebook_url_from_format_no_user_uuid(self):
        del self.raw_config['X_xivo_user_uuid']

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        assert_that(self.raw_config, is_not(has_key('XX_xivo_phonebook_url')))

    def test_add_xivo_phonebook_url_from_format_full(self):
        self.raw_config['X_xivo_phonebook_scheme'] = 'https'
        self.raw_config['X_xivo_phonebook_port'] = 4242

        add_xivo_phonebook_url_from_format(self.raw_config, self.url_format)

        expected = 'https://8.8.8.8:4242/default?xivo_user_uuid=12-345'
        assert_that(self.raw_config['XX_xivo_phonebook_url'], equal_to(expected))
