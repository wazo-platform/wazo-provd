# -*- coding: utf-8 -*-
# Copyright 2010-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from provd.persist.util import (
    _retrieve_doc_values,
    _create_pred_from_selector,
    _new_key_fun_from_key,
)


class TestSelectorSelectValue(unittest.TestCase):
    def test_select_value_simple(self):
        doc = {'k': 'v'}
        self.assertEqual(['v'], list(_retrieve_doc_values('k', doc)))

    def test_select_value_simple_with_noise(self):
        doc = {'k': 'v', 'foo': [{'bar': '555'}]}
        self.assertEqual(['v'], list(_retrieve_doc_values('k', doc)))

    def test_select_value_simple_no_match(self):
        doc = {}
        self.assertEqual([], list(_retrieve_doc_values('k', doc)))

    def test_select_value_dict(self):
        doc = {'k': {'kk': 'v'}}
        self.assertEqual(['v'], list(_retrieve_doc_values('k.kk', doc)))

    def test_select_value_dict_3depth(self):
        doc = {'k': {'kk': {'kkk': 'v'}}}
        self.assertEqual(['v'], list(_retrieve_doc_values('k.kk.kkk', doc)))

    def test_select_value_list(self):
        doc = {'k': ['v1', 'v2']}
        self.assertEqual([['v1', 'v2']], list(_retrieve_doc_values('k', doc)))

    def test_select_value_dict_inside_list(self):
        doc = {'k': [{'kk': 'v'}]}
        self.assertEqual(['v'], list(_retrieve_doc_values('k.kk', doc)))

    def test_select_value_dict_inside_list_multiple_values(self):
        doc = {'k': [{'kk': 'v1'}, {'kk': 'v2'}]}
        self.assertEqual(['v1', 'v2'], list(_retrieve_doc_values('k.kk', doc)))


class TestSelectorCreatePredicate(unittest.TestCase):
    def test_empty_selector_match_anything(self):
        pred = _create_pred_from_selector({})
        self.assertTrue(pred({}))
        self.assertTrue(pred({'k': 'v'}))

    def test_simple_1item_selector_match(self):
        pred = _create_pred_from_selector({'k1': 'v1'})
        self.assertTrue(pred({'k1': 'v1'}))
        self.assertTrue(pred({'k1': 'v1', 'k2': 'v2'}))

    def test_simple_1item_selector_nomatch(self):
        pred = _create_pred_from_selector({'k1': 'v1'})
        self.assertFalse(pred({}))
        self.assertFalse(pred({'k2': 'v2'}))
        self.assertFalse(pred({'k1': 'v2'}))

    def test_simple_2item_selector_match(self):
        pred = _create_pred_from_selector({'k1': 'v1', 'k2': 'v2'})
        self.assertTrue(pred({'k1': 'v1', 'k2': 'v2'}))
        self.assertTrue(pred({'k1': 'v1', 'k2': 'v2', 'k3': 'v3'}))

    def test_simple_2item_selector_nomatch(self):
        pred = _create_pred_from_selector({'k1': 'v1', 'k2': 'v2'})
        self.assertFalse(pred({}))
        self.assertFalse(pred({'k1': 'v1'}))
        self.assertFalse(pred({'k2': 'v2'}))
        self.assertFalse(pred({'k1': 'v1', 'k2': 'v1'}))

    def test_1item_list_selector_nomatch(self):
        pred = _create_pred_from_selector({'k1': 'v1'})
        self.assertFalse(pred({'k1': ['v2']}))
        self.assertFalse(pred({'k1': 'v2'}))

    def test_1item_dict_selector_match(self):
        pred = _create_pred_from_selector({'k.kk': 'v'})
        self.assertTrue(pred({'k': {'kk': 'v'}}))
        self.assertTrue(pred({'k': {'kk': 'v', 'foo': 'bar'}}))
        self.assertTrue(pred({'k': [{'kk': 'v'}]}))

    def test_1item_dict_selector_nomatch(self):
        pred = _create_pred_from_selector({'k.kk': 'v'})
        self.assertFalse(pred({'k': {'kk': 'v1'}}))
        self.assertFalse(pred({'k': 'v'}))
        self.assertFalse(pred({'k': {'foo': 'bar'}}))
        self.assertFalse(pred({'k': [{'kk': 'v1'}]}))
        self.assertFalse(pred({'k': []}))


class TestUtil(unittest.TestCase):
    def test_new_key_fun_from_key_field_exists(self):
        # trying to sort on an existing field (string type)
        l = [
            {'string_field': 'b'},
            {'string_field': 'a'},
            {'string_field': 'c'},
        ]
        expected_l = [
            {'string_field': 'a'},
            {'string_field': 'b'},
            {'string_field': 'c'},
        ]
        l.sort(key=_new_key_fun_from_key('string_field'))
        self.assertListEqual(l, expected_l)

        # trying to sort on an existing field (integer type)
        l = [
            {'integer_field': 5},
            {'integer_field': -3},
            {'integer_field': 1},
            {'integer_field': 0},
        ]
        expected_l = [
            {'integer_field': -3},
            {'integer_field': 0},
            {'integer_field': 1},
            {'integer_field': 5},
        ]
        l.sort(key=_new_key_fun_from_key('integer_field'))
        self.assertListEqual(l, expected_l)

        # trying to sort on an existing field (None)
        l = [
            {'field': 'A'},
            {'field': None},
            {'field': 'B'},
        ]
        expected_l = [
            {'field': 'A'},
            {'field': 'B'},
            {'field': None},
        ]
        l.sort(key=_new_key_fun_from_key('field'))
        self.assertListEqual(l, expected_l)

        # trying to sort on an existing field (dict type)
        l = [
            {'field': {'string_field': 'b'}},
            {'field': {'string_field': 'a'}},
            {'field': {'string_field': 'c'}},
        ]
        expected_l = [
            {'field': {'string_field': 'a'}},
            {'field': {'string_field': 'b'}},
            {'field': {'string_field': 'c'}},
        ]
        l.sort(key=_new_key_fun_from_key('field.string_field'))
        self.assertListEqual(l, expected_l)

    def test_new_key_fun_from_key_field_missed(self):
        # trying to sort on a missing field (string type)
        l = [
            {'string_field': 'b'},
            {},
            {'string_field': 'a'},
        ]
        expected_l = [
            {'string_field': 'a'},
            {'string_field': 'b'},
            {},
        ]
        l.sort(key=_new_key_fun_from_key('string_field'))
        self.assertListEqual(l, expected_l)

        # trying to sort on a missing field (integer type)
        l = [
            {'integer_field': 5},
            {},
            {'integer_field': 1},
        ]
        expected_l = [
            {'integer_field': 1},
            {'integer_field': 5},
            {},
        ]
        l.sort(key=_new_key_fun_from_key('integer_field'))
        self.assertListEqual(l, expected_l)

    def test_new_key_fun_from_key_types_not_allowed(self):
        # trying to sort on a field having not allowed types
        l = [
            {'field': {}},
            {'field': 'a'},
            {'field': []},
            {'field': 'b'},
        ]
        expected_l = [
            {'field': 'a'},
            {'field': 'b'},
            {'field': []},
            {'field': {}},
        ]
        l.sort(key=_new_key_fun_from_key('field'))
        self.assertListEqual(l, expected_l)
