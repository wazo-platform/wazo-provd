# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

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

from ..config import DefaultConfigFactory


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
