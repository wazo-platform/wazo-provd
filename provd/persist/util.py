# Copyright 2011-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from provd.persist.common import ID_KEY, InvalidIdError, NonDeletableError
from twisted.internet import defer

logger = logging.getLogger(__name__)


def _retrieve_doc_values(s_key, doc):
    # Return an iterator of matched value, i.e. all the value in the
    # doc that matches the select key
    def func(current_s_key, current_doc):
        pre, sep, post = current_s_key.partition('.')
        if not sep:
            assert pre == current_s_key
            if isinstance(current_doc, dict):
                if current_s_key in current_doc:
                    yield current_doc[current_s_key]
            elif isinstance(current_doc, list):
                for elem in current_doc:
                    for result in func(current_s_key, elem):
                        yield result
        else:
            assert pre != current_s_key
            if post is None:
                raise ValueError('invalid selector key "%s"' % s_key)

            if isinstance(current_doc, dict) and pre in current_doc:
                for result in func(post, current_doc[pre]):
                    yield result

    return func(s_key, doc)


def _contains_operator(selector_value):
    # Return true if the value associated with a key of a selector
    # is an operator value, i.e. has an operator semantic.
    if isinstance(selector_value, dict):
        for k in selector_value:
            if k.startswith('$'):
                return True
    return False


def _new_simple_matcher_from_pred(pred):
    # Return a matcher that returns true if there's a value in the document
    # matching the select key for which pred(value) is true
    def func(s_key, doc):
        for doc_value in _retrieve_doc_values(s_key, doc):
            if pred(doc_value):
                return True
        return False

    return func


def _new_simple_inv_matcher_from_pred(pred):
    # Return a matcher that returns true if there's no value in the document
    # matching the select key for which pred(value) is true
    def func(s_key, doc):
        for doc_value in _retrieve_doc_values(s_key, doc):
            if pred(doc_value):
                return False
        return True

    return func


def _new_in_matcher(s_value):
    # Return a matcher that returns true if there's a value in the document
    # matching the select key that is equal to one of the value in s_value
    if not isinstance(s_value, list):
        raise ValueError('selector value for in matcher must be a list: %s is not' % s_value)
    pred = lambda doc_value: doc_value in s_value
    return _new_simple_matcher_from_pred(pred)


def _new_contains_matcher(s_value):
    # Return a matcher that returns true if there's a value in the document
    # matching the select key that one of the value in s_value
    pred = lambda doc_value: hasattr(doc_value, '__contains__') and s_value in doc_value
    return _new_simple_matcher_from_pred(pred)


def _new_nin_matcher(s_value):
    # Return a matcher that returns true if there's no values in the document
    # matching the select key that is equal to one of the value in s_value
    if not isinstance(s_value, list):
        raise ValueError('selector value for nin matcher must be a list: %s is not' % s_value)
    pred = lambda doc_value: doc_value in s_value
    return _new_simple_inv_matcher_from_pred(pred)


def _new_eq_matcher(s_value):
    # Return a matcher that returns true if there's a value in the document
    # matching the select key that is equal to s_value
    pred = lambda doc_value: doc_value == s_value
    return _new_simple_matcher_from_pred(pred)


def _new_ne_matcher(s_value):
    # Return a matcher that returns true if there's no value in the document
    # matching the select key that is equal to s_value
    pred = lambda doc_value: doc_value == s_value
    return _new_simple_inv_matcher_from_pred(pred)


def _new_gt_matcher(s_value):
    # Return a matcher that returns true if there's a value in the document
    # matching the select key that is greater (>) to s_value
    pred = lambda doc_value: doc_value > s_value
    return _new_simple_matcher_from_pred(pred)


def _new_ge_matcher(s_value):
    pred = lambda doc_value: doc_value >= s_value
    return _new_simple_matcher_from_pred(pred)


def _new_lt_matcher(s_value):
    pred = lambda doc_value: doc_value < s_value
    return _new_simple_matcher_from_pred(pred)


def _new_le_matcher(s_value):
    pred = lambda doc_value: doc_value <= s_value
    return _new_simple_matcher_from_pred(pred)


def _new_exists_matcher(s_value):
    s_value = bool(s_value)

    def aux(s_key, doc):
        it = iter(_retrieve_doc_values(s_key, doc))
        try:
            next(it)
        except StopIteration:
            return not s_value
        return s_value

    return aux


def _new_and_matcher(matchers):
    # Return true if all the given matchers returns true.
    def func(s_key, doc):
        for matcher in matchers:
            if not matcher(s_key, doc):
                return False
        return True

    return func


_MATCHER_FACTORIES = {
    '$in': _new_in_matcher,
    '$nin': _new_nin_matcher,
    '$contains': _new_contains_matcher,
    '$gt': _new_gt_matcher,
    '$ge': _new_ge_matcher,
    '$lt': _new_lt_matcher,
    '$le': _new_le_matcher,
    '$ne': _new_ne_matcher,
    '$exists': _new_exists_matcher,
}


def _new_operator_matcher(operator_key, operator_value):
    try:
        matcher_factory = _MATCHER_FACTORIES[operator_key]
    except KeyError:
        raise ValueError('invalid operator: %s' % operator_key)
    else:
        return matcher_factory(operator_value)


def _new_matcher(s_value):
    # Return a predicate taking a select key and a document that returns true
    # if the document value matches it, else false.
    if _contains_operator(s_value):
        matchers = [_new_operator_matcher(k, v) for k, v in s_value.items()]
        if len(matchers) == 1:
            return matchers[0]
        return _new_and_matcher(matchers)
    return _new_eq_matcher(s_value)


def _create_pred_from_selector(selector):
    # Return a predicate taking a document as argument and returning
    # true if the selector matches it, else false.
    selector_matchers = [(k, _new_matcher(v)) for k, v in selector.items()]

    def aux(document):
        for s_key, matcher in selector_matchers:
            if not matcher(s_key, document):
                return False
        return True

    return aux


class SimpleBackendDocumentCollection:
    def __init__(self, backend, generator):
        self._backend = backend
        self._generator = generator
        self._indexes = {}
        self.closed = False

    def close(self):
        self._backend.close()
        self.closed = True

    def _generate_new_id(self):
        for document_id in self._generator:
            if document_id not in self._backend:
                return document_id

    def insert(self, document):
        if ID_KEY in document:
            document_id = document[ID_KEY]
            if document_id in self._backend:
                raise InvalidIdError(document_id)
        else:
            document_id = self._generate_new_id()
            document[ID_KEY] = document_id

        assert document_id == document[ID_KEY]
        assert document_id not in self._backend
        self._backend[document_id] = document
        self._add_document_update_indexes(document)
        return defer.succeed(document_id)

    def update(self, document):
        try:
            document_id = document[ID_KEY]
        except KeyError:
            return defer.fail(ValueError(f'no {ID_KEY} key found in document {document}'))
        else:
            if document_id not in self._backend:
                return defer.fail(InvalidIdError(document_id))
            old_document = self._backend[document_id]
            self._backend[document_id] = document
            self._update_document_update_indexes(document, old_document)
            return defer.succeed(None)

    def delete(self, document_id: str):
        try:
            old_document = self._backend[document_id]
            if old_document.get('deletable', True):
                self._del_document_update_indexes(old_document)
                del self._backend[document_id]
            else:
                return defer.fail(NonDeletableError(document_id))
        except KeyError:
            return defer.fail(InvalidIdError(document_id))
        else:
            return defer.succeed(None)

    def retrieve(self, document_id: str):
        try:
            return defer.succeed(self._backend[document_id])
        except KeyError:
            return defer.succeed(None)

    def _new_key_fun_from_key(self, key):
        # Return a function usable for the key parameter of the sorted function
        # from a [sort] key
        split_key = key.split('.')

        def func(document):
            cur_elem = document
            try:
                for cur_key in split_key:
                    cur_elem = cur_elem[cur_key]
            except (KeyError, TypeError):
                # document does not have the given key -- return None
                return None
            return cur_elem

        return func

    def _reverse_from_direction(self, direction):
        # Return the reverse value for the reverse parameter of the sorted
        # function from a [sort] direction
        if direction == 1:
            return False
        elif direction == -1:
            return True
        else:
            # XXX should probably create a more meaningful exception class
            raise Exception(f'invalid direction {direction}')

    def _do_find_sorted(self, selector, fields, skip, limit, sort):
        documents = list(self._do_find_unsorted(selector, fields, 0, 0))
        key, direction = sort
        key_fun = self._new_key_fun_from_key(key)
        reverse = self._reverse_from_direction(direction)
        documents.sort(key=key_fun, reverse=reverse)
        documents = list(self._new_skip_iterator(skip, documents))
        documents = list(self._new_limit_iterator(limit, documents))
        return iter(documents)

    def _new_fields_map_function(self, fields):
        if not fields:
            return lambda x: x

        split_keys = [field.split('.') for field in fields]

        def aux(document):
            result = {ID_KEY: document[ID_KEY]}
            for split_key in split_keys:
                cur_elem = document
                try:
                    for cur_key in split_key:
                        cur_elem = cur_elem[cur_key]
                except (KeyError, TypeError):
                    # element does not have the given key or is not a dictionary -- ignore
                    pass
                else:
                    cur_result = result
                    for cur_key in split_key[:-1]:
                        cur_result = cur_result.setdefault(cur_key, {})
                    cur_result[split_key[-1]] = cur_elem
            return result

        return aux

    def _new_skip_iterator(self, skip, documents):
        try:
            documents = iter(documents)
            while skip > 0:
                skip -= 1
                next(documents)
        except StopIteration:
            # skip is larger than the number of elements -- do nothing
            pass
        return documents

    def _new_limit_iterator(self, limit, documents):
        if not limit:
            return documents
        else:
            def func(limit):
                # limit is an argument to aux, else it will raise an
                # UnboundLocalVariable exception (since we are using python 2)
                try:
                    while limit > 0:
                        limit -= 1
                        yield next(documents)
                except StopIteration:
                    # limit is larger than the number of elements -- do nothing
                    pass

            return func(limit)

    def _new_iterator(self, selector, documents):
        # Return an iterator that will return every documents matching
        # the given "regular" selector
        pred = _create_pred_from_selector(selector)
        return list(filter(pred, documents))

    def _new_indexes_iterator(self, indexes_selector):
        # Return an iterator that will return every document in the backend
        # matching the given "indexes" selector. Note that an indexes selector
        # can't be empty.
        document_ids = set()
        first_loop = True
        for selector_key, selector_value in indexes_selector.items():
            index = self._indexes[selector_key]
            index_entry = index.get(selector_value, [])
            if first_loop:
                first_loop = False
                document_ids.update(index_entry)
            else:
                document_ids.intersection_update(index_entry)
        for document_id in document_ids:
            yield self._backend[document_id]

    def _new_iterator_over_matching_documents(self, selector):
        # Return an iterator that will yield every document in the backend
        # matching the given selector. This may or may not use indices.
        # 1. check if there's some key-value in the selector usable by the
        #    indexes
        indexes_selector = {}
        regular_selector = {}
        for selector_key, selector_value in selector.items():
            if (selector_key in self._indexes and
                    not _contains_operator(selector_value)):
                indexes_selector[selector_key] = selector_value
            else:
                regular_selector[selector_key] = selector_value
        # 2. use indexes selector if possible
        if indexes_selector:
            documents = self._new_indexes_iterator(indexes_selector)
        else:
            documents = self._backend.values()
        # 3. use regular selector if possible
        if regular_selector:
            documents = self._new_iterator(regular_selector, documents)
        return documents

    def _do_find_unsorted(self, selector, fields, skip, limit):
        # common case optimization when only ID_KEY is present
        if ID_KEY in selector and len(selector) == 1 and not _contains_operator(selector[ID_KEY]):
            try:
                documents = [self._backend[selector[ID_KEY]]]
            except KeyError:
                documents = []
        else:
            documents = self._new_iterator_over_matching_documents(selector)
        documents = self._new_skip_iterator(skip, documents)
        documents = self._new_limit_iterator(limit, documents)
        documents = list(map(self._new_fields_map_function(fields), documents))
        return iter(documents)

    def _do_find(self, selector, fields, skip, limit, sort):
        # Return an iterator over the documents
        if sort:
            return self._do_find_sorted(selector, fields, skip, limit, sort)
        else:
            return self._do_find_unsorted(selector, fields, skip, limit)

    def find(self, selector, fields=None, skip=0, limit=0, sort=None):
        logger.debug('Executing find in backend based collection with:\n'
                     '  selector: %s\n'
                     '  fields: %s\n'
                     '  skip: %s\n'
                     '  limit: %s\n'
                     '  sort: %s',
                     selector, fields, skip, limit, sort)
        return defer.succeed(self._do_find(selector, fields, skip, limit, sort))

    def find_one(self, selector):
        it = self._do_find(selector, None, 0, 1, None)
        try:
            result = next(it)
        except StopIteration:
            result = None
        return defer.succeed(result)

    def _add_document_update_indexes(self, document):
        # Update the indexes after adding a document to the backend.
        document_id = document[ID_KEY]
        for complex_key, index in self._indexes.items():
            has_key, value = self._get_value_from_complex_key(complex_key, document)
            if has_key:
                self._new_value_for_index(index, document_id, value)

    def _update_document_update_indexes(self, document, old_document):
        # Update the indexes after updating a document to the backend.
        self._del_document_update_indexes(old_document)
        self._add_document_update_indexes(document)

    def _del_document_update_indexes(self, old_document):
        # Update the indexes after removing document from the backend.
        document_id = old_document[ID_KEY]
        for complex_key, index in self._indexes.items():
            has_key, value = self._get_value_from_complex_key(complex_key, old_document)
            if has_key:
                self._del_value_for_index(index, document_id, value)

    def _new_value_for_index(self, index, document_id, value):
        # Add the value belonging to the document with the given id to the
        # given index.
        def func(value):
            if value in index:
                index_entry = index[value]
                if document_id not in index_entry:
                    index_entry.append(document_id)
            else:
                index[value] = [document_id]

        func(value)
        if isinstance(value, list):
            for list_item in value:
                func(list_item)

    def _del_value_for_index(self, index, document_id, value):
        # Delete the value belonging to the document with the given id to
        # the given index.
        def func(inner_value):
            index_entry = index[inner_value]
            index_entry.remove(document_id)
            if not index_entry:
                del index[inner_value]

        func(value)
        if isinstance(value, list):
            for list_item in value:
                func(list_item)

    def _get_value_from_complex_key(self, complex_key, document):
        get_value_fun = self._new_get_value_fun_from_complex_key(complex_key)
        return get_value_fun(document)

    def _new_get_value_fun_from_complex_key(self, complex_key):
        # Return a function that takes a document and return a tuple where
        # the first element is true if the document has the complex key, and
        # the second element is the value of the complex key for this document
        key_tokens = complex_key.split('.')

        def func(document):
            value = document
            for key_token in key_tokens:
                try:
                    if key_token in value:
                        value = value[key_token]
                    else:
                        break
                except TypeError:
                    break
            else:
                # document has the key and value is the value of this key for
                # this document
                return True, value
            return False, None

        return func

    def _new_id_and_value_iterator(self, complex_key):
        # Return an iterator that yield (id, value) tuple for each document
        # in the backend that has the given complex key.
        get_value_fun = self._new_get_value_fun_from_complex_key(complex_key)
        for document in self._backend.values():
            has_key, value = get_value_fun(document)
            if has_key:
                yield document[ID_KEY], value

    def _create_index(self, complex_key):
        logger.info('Creating index on complex key %s', complex_key)
        index = {}
        for key, value in self._new_id_and_value_iterator(complex_key):
            self._new_value_for_index(index, key, value)
        self._indexes[complex_key] = index

    def ensure_index(self, complex_key):
        if complex_key not in self._indexes:
            self._create_index(complex_key)
        return defer.succeed(None)


def new_backend_based_collection(backend, generator):
    return SimpleBackendDocumentCollection(backend, generator)


class ForwardingDocumentCollection:
    def __init__(self, collection):
        self._collection = collection

    def __getattr__(self, name):
        return getattr(self._collection, name)
