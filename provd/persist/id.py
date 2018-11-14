# -*- coding: utf-8 -*-
# Copyright (C) 2011-2014 Avencall
# SPDX-License-Identifier: GPL-3.0+

import binascii
import uuid


def numeric_id_generator(prefix=u'', start=0):
    n = start
    while True:
        yield prefix + unicode(n)
        n += 1


def uuid_id_generator():
    while True:
        yield unicode(uuid.uuid4().hex)


def urandom_id_generator(length=12):
    while True:
        f = open('/dev/urandom')
        try:
            id = unicode(binascii.hexlify(f.read(length)))
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
