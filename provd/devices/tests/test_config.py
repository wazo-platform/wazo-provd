# -*- coding: utf-8 -*-

# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
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
