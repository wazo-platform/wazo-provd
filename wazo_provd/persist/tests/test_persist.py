# Copyright 2010-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import unittest
from typing import Any

from wazo_provd.persist.util import (
    _create_pred_from_selector,
    _new_key_fun_from_key,
    _retrieve_doc_values,
)


class TestSelectorSelectValue(unittest.TestCase):
    def test_select_value_simple(self) -> None:
        doc = {'k': 'v'}
        self.assertEqual(['v'], list(_retrieve_doc_values('k', doc)))

    def test_select_value_simple_with_noise(self) -> None:
        doc = {'k': 'v', 'foo': [{'bar': '555'}]}
        self.assertEqual(['v'], list(_retrieve_doc_values('k', doc)))

    def test_select_value_simple_no_match(self) -> None:
        doc: dict[str, Any] = {}
        self.assertEqual([], list(_retrieve_doc_values('k', doc)))

    def test_select_value_dict(self) -> None:
        doc = {'k': {'kk': 'v'}}
        self.assertEqual(['v'], list(_retrieve_doc_values('k.kk', doc)))

    def test_select_value_dict_3depth(self) -> None:
        doc = {'k': {'kk': {'kkk': 'v'}}}
        self.assertEqual(['v'], list(_retrieve_doc_values('k.kk.kkk', doc)))

    def test_select_value_list(self) -> None:
        doc = {'k': ['v1', 'v2']}
        self.assertEqual([['v1', 'v2']], list(_retrieve_doc_values('k', doc)))

    def test_select_value_dict_inside_list(self) -> None:
        doc = {'k': [{'kk': 'v'}]}
        self.assertEqual(['v'], list(_retrieve_doc_values('k.kk', doc)))

    def test_select_value_dict_inside_list_multiple_values(self) -> None:
        doc = {'k': [{'kk': 'v1'}, {'kk': 'v2'}]}
        self.assertEqual(['v1', 'v2'], list(_retrieve_doc_values('k.kk', doc)))


class TestSelectorCreatePredicate(unittest.TestCase):
    def test_empty_selector_match_anything(self) -> None:
        pred = _create_pred_from_selector({})
        self.assertTrue(pred({}))
        self.assertTrue(pred({'k': 'v'}))

    def test_simple_1item_selector_match(self) -> None:
        pred = _create_pred_from_selector({'k1': 'v1'})
        self.assertTrue(pred({'k1': 'v1'}))
        self.assertTrue(pred({'k1': 'v1', 'k2': 'v2'}))

    def test_simple_1item_selector_nomatch(self) -> None:
        pred = _create_pred_from_selector({'k1': 'v1'})
        self.assertFalse(pred({}))
        self.assertFalse(pred({'k2': 'v2'}))
        self.assertFalse(pred({'k1': 'v2'}))

    def test_simple_2item_selector_match(self) -> None:
        pred = _create_pred_from_selector({'k1': 'v1', 'k2': 'v2'})
        self.assertTrue(pred({'k1': 'v1', 'k2': 'v2'}))
        self.assertTrue(pred({'k1': 'v1', 'k2': 'v2', 'k3': 'v3'}))

    def test_simple_2item_selector_nomatch(self) -> None:
        pred = _create_pred_from_selector({'k1': 'v1', 'k2': 'v2'})
        self.assertFalse(pred({}))
        self.assertFalse(pred({'k1': 'v1'}))
        self.assertFalse(pred({'k2': 'v2'}))
        self.assertFalse(pred({'k1': 'v1', 'k2': 'v1'}))

    def test_1item_list_selector_nomatch(self) -> None:
        pred = _create_pred_from_selector({'k1': 'v1'})
        self.assertFalse(pred({'k1': ['v2']}))
        self.assertFalse(pred({'k1': 'v2'}))

    def test_1item_dict_selector_match(self) -> None:
        pred = _create_pred_from_selector({'k.kk': 'v'})
        self.assertTrue(pred({'k': {'kk': 'v'}}))
        self.assertTrue(pred({'k': {'kk': 'v', 'foo': 'bar'}}))
        self.assertTrue(pred({'k': [{'kk': 'v'}]}))

    def test_1item_dict_selector_nomatch(self) -> None:
        pred = _create_pred_from_selector({'k.kk': 'v'})
        self.assertFalse(pred({'k': {'kk': 'v1'}}))
        self.assertFalse(pred({'k': 'v'}))
        self.assertFalse(pred({'k': {'foo': 'bar'}}))
        self.assertFalse(pred({'k': [{'kk': 'v1'}]}))
        self.assertFalse(pred({'k': []}))


class TestUtil(unittest.TestCase):
    def test_new_key_fun_from_key_field_exists(self) -> None:
        # trying to sort on an existing field (string type)
        list_dict_str = [
            {'string_field': 'b'},
            {'string_field': 'a'},
            {'string_field': 'c'},
        ]
        expected_list_dict_str = [
            {'string_field': 'a'},
            {'string_field': 'b'},
            {'string_field': 'c'},
        ]
        list_dict_str.sort(key=_new_key_fun_from_key('string_field'))
        self.assertListEqual(list_dict_str, expected_list_dict_str)

        # trying to sort on an existing field (integer/float type)
        list_dict_float = [
            {'field': 5},
            {'field': 1.5},
            {'field': -3},
            {'field': 1},
            {'field': 0},
        ]
        expected_list_dict_float = [
            {'field': -3},
            {'field': 0},
            {'field': 1},
            {'field': 1.5},
            {'field': 5},
        ]
        list_dict_float.sort(key=_new_key_fun_from_key('field'))
        self.assertListEqual(list_dict_float, expected_list_dict_float)

        # trying to sort on an existing field (None)
        list_dict_optional_str = [
            {'field': 'A'},
            {'field': None},
            {'field': 'B'},
        ]
        expected_list_dict_optional_str = [
            {'field': None},
            {'field': 'A'},
            {'field': 'B'},
        ]
        list_dict_optional_str.sort(key=_new_key_fun_from_key('field'))
        self.assertListEqual(list_dict_optional_str, expected_list_dict_optional_str)

        # trying to sort on an existing field (dict type)
        list_dict = [
            {'field': {'string_field': 'b'}},
            {'field': {'string_field': 'a'}},
            {'field': {'string_field': 'c'}},
        ]
        expected_list_dict = [
            {'field': {'string_field': 'a'}},
            {'field': {'string_field': 'b'}},
            {'field': {'string_field': 'c'}},
        ]
        list_dict.sort(key=_new_key_fun_from_key('field.string_field'))
        self.assertListEqual(list_dict, expected_list_dict)

    def test_new_key_fun_from_key_field_missed(self) -> None:
        # trying to sort on a missing field (string type)
        list_dict_str_empty = [
            {'string_field': 'b'},
            {},
            {'string_field': 'a'},
        ]
        expected_list_dict_str_empty = [
            {},
            {'string_field': 'a'},
            {'string_field': 'b'},
        ]
        list_dict_str_empty.sort(key=_new_key_fun_from_key('string_field'))
        self.assertListEqual(list_dict_str_empty, expected_list_dict_str_empty)

        # trying to sort on a missing field (integer type)
        list_dict_int_empty = [
            {'integer_field': 5},
            {},
            {'integer_field': 1},
        ]
        expected_list_dict_int_empty = [
            {},
            {'integer_field': 1},
            {'integer_field': 5},
        ]
        list_dict_int_empty.sort(key=_new_key_fun_from_key('integer_field'))
        self.assertListEqual(list_dict_int_empty, expected_list_dict_int_empty)
