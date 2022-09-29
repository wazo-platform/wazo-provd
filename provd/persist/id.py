# -*- coding: utf-8 -*-
# Copyright 2011-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import binascii
import uuid
import six


def numeric_id_generator(prefix='', start=0):
    n = start
    while True:
        yield prefix + six.text_type(n)
        n += 1


def uuid_id_generator():
    while True:
        yield six.text_type(uuid.uuid4().hex)


def urandom_id_generator(length=12):
    while True:
        f = open('/dev/urandom')
        try:
            id = six.text_type(binascii.hexlify(f.read(length)))
        finally:
            f.close()
        yield id


default_id_generator = uuid_id_generator


def get_id_generator_factory(generator_name):
    """Return an ID generator factory from a generator name, or raise
    ValueError if the name is unknown.
    
    Currently accepted generator name are: default, numeric, uuid and
    urandom.
    
    """
    try:
        return globals()[generator_name + '_id_generator']
    except KeyError:
        raise ValueError('unknown generator name "%s"' % generator_name)
