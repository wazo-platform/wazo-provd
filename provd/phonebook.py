# -*- coding: utf-8 -*-
# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


_URL_META_FORMAT = u'{{scheme}}://{{hostname}}:{{port}}/0.1/directories/{entry_point}/default/{vendor}?{qs_prefix}xivo_user_uuid={{user_uuid}}{qs_suffix}'


def add_xivo_phonebook_url(raw_config, vendor, entry_point=u'input', qs_prefix=u'', qs_suffix=u''):
    url_format = _build_url_format(vendor, entry_point, qs_prefix, qs_suffix)
    add_xivo_phonebook_url_from_format(raw_config, url_format)


def _build_url_format(vendor, entry_point, qs_prefix, qs_suffix):
    if qs_prefix:
        qs_prefix = qs_prefix + u'&'
    if qs_suffix:
        qs_suffix = u'&' + qs_suffix
    return _URL_META_FORMAT.format(vendor=vendor,
                                   entry_point=entry_point,
                                   qs_prefix=qs_prefix,
                                   qs_suffix=qs_suffix)


def add_xivo_phonebook_url_from_format(raw_config, url_format):
    hostname = raw_config.get(u'X_xivo_phonebook_ip')
    if not hostname:
        return

    user_uuid = raw_config.get(u'X_xivo_user_uuid')
    if not user_uuid:
        logger.warning('Not adding XX_xivo_phonebook_url: no user uuid')
        return

    scheme = raw_config.get(u'X_xivo_phonebook_scheme', u'http')
    port = raw_config.get(u'X_xivo_phonebook_port', 9498)
    raw_config[u'XX_xivo_phonebook_url'] = url_format.format(scheme=scheme,
                                                             hostname=hostname,
                                                             port=port,
                                                             user_uuid=user_uuid)
