# -*- coding: utf-8 -*-
# Copyright 2018-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
import unittest

from hamcrest import (
    all_of,
    assert_that,
    equal_to,
    has_entries,
    is_,
    none,
    not_,
    starts_with,
)

from ..config import DefaultConfigFactory, _remove_none_values


class TestDefaultConfigFactory(unittest.TestCase):

    def setUp(self):
        self.factory = DefaultConfigFactory()

    def test_sip_line(self):
        config = {'raw_config': {}}

        result = self.factory(config)

        assert_that(result, is_(none()))

    def test_with_a_valid_sip_configuration(self):
        id_ = 'ap'
        username = 'anonymous'
        config = {
            'id': id_,
            'raw_config': {
                'sip_lines': {
                    '1': {
                        'username': username,
                    }
                }
            }
        }

        result = self.factory(config)

        assert_that(
            result,
            has_entries(
                id=all_of(
                    starts_with(id_),
                    not_(equal_to(id_)),
                ),
                raw_config=has_entries(
                    sip_lines=has_entries(
                        '1', has_entries(
                            username=username,
                        )
                    )
                )
            )
        )


class TestRemoveNoneValues(unittest.TestCase):

    def test_empty_dict(self):
        empty_dict = {}
        expected_result = {}

        result = _remove_none_values(empty_dict)
        assert_that(
            result,
            is_(equal_to(expected_result)),
        )

    def test_with_simple_dict(self):
        dict_with_nones = {
            'key1': None,
            'key2': '123',
            'key3': 123,
            'key4': False,
        }

        expected_result = {
            'key2': '123',
            'key3': 123,
            'key4': False,
        }

        result = _remove_none_values(dict_with_nones)
        assert_that(
            result,
            is_(equal_to(expected_result)),
        )

    def test_with_nested_dict(self):
        dict_with_nones = {
            'key1': {'nkey1': 123, 'nkey2': None},
        }

        expected_result = {
            'key1': {'nkey1': 123},
        }

        result = _remove_none_values(dict_with_nones)
        assert_that(
            result,
            is_(equal_to(expected_result)),
        )

    def test_with_list(self):
        dict_with_list = {
            'key1': [123, None],
        }

        expected_result = {
            'key1': [123, None],
        }

        result = _remove_none_values(dict_with_list)
        assert_that(
            result,
            is_(equal_to(expected_result)),
        )

    def test_with_dict_in_list(self):
        dict_with_list = {
            'key1': [{'nkey1': 123, 'nkey2': None}, {'nkey1': None, 'nkey2': '123'}],
        }

        expected_result = {
            'key1': [{'nkey1': 123}, {'nkey2': '123'}],
        }

        result = _remove_none_values(dict_with_list)
        assert_that(
            result,
            is_(equal_to(expected_result)),
        )
