# -*- coding: utf-8 -*-
# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)

FORWARD_URL_FORMAT = u'{scheme}://{hostname}:{port}/0.1/{vendor}/users/{user_uuid}/forwards/{forward}/{enabled}'
SERVICE_URL_FORMAT = u'{scheme}://{hostname}:{port}/0.1/{vendor}/users/{user_uuid}/services/{service}/{enabled}'


def add_wazo_phoned_user_service_url(
    raw_config,
    vendor,
    service_name,
):
    # NOTE(afournier): phoned is actually exposed as the phonebook.
    hostname = raw_config.get(u'X_xivo_phonebook_ip')
    if not hostname:
        logger.warning('Not adding XX_wazo_phoned_user_service_%s_url: no hostname', service_name)
        return

    user_uuid = raw_config.get(u'X_xivo_user_uuid')
    if not user_uuid:
        logger.warning('Not adding XX_wazo_phoned_user_service_%s_url: no user uuid', service_name)
        return

    scheme = raw_config.get(u'X_xivo_phonebook_scheme', u'http')
    port = raw_config.get(u'X_xivo_phonebook_port', 9498)

    formatted_enabled_url = SERVICE_URL_FORMAT.format(
        scheme=scheme,
        hostname=hostname,
        port=port,
        vendor=vendor,
        service=service_name,
        user_uuid=user_uuid,
        enabled=_enable_string(True),
    )

    formatted_disabled_url = SERVICE_URL_FORMAT.format(
        scheme=scheme,
        hostname=hostname,
        port=port,
        vendor=vendor,
        service=service_name,
        user_uuid=user_uuid,
        enabled=_enable_string(False),
    )
    raw_config[
        u'XX_wazo_phoned_user_service_{}_enabled_url'.format(service_name)
    ] = formatted_enabled_url

    raw_config[
        u'XX_wazo_phoned_user_service_{}_disabled_url'.format(service_name)
    ] = formatted_disabled_url


def add_wazo_phoned_user_forward_url(
    raw_config,
    vendor,
    forward_name,
    destination=None,
):
    # NOTE(afournier): phoned is actually exposed as the phonebook.
    hostname = raw_config.get(u'X_xivo_phonebook_ip')
    if not hostname:
        logger.warning('Not adding XX_wazo_phoned_user_forward_%s_url: no hostname', forward_name)
        return

    user_uuid = raw_config.get(u'X_xivo_user_uuid')
    if not user_uuid:
        logger.warning('Not adding XX_wazo_phoned_user_forward_%s_url: no user uuid', forward_name)
        return

    scheme = raw_config.get(u'X_xivo_phonebook_scheme', u'http')
    port = raw_config.get(u'X_xivo_phonebook_port', 9498)

    formatted_enabled_url = FORWARD_URL_FORMAT.format(
        scheme=scheme,
        hostname=hostname,
        port=port,
        vendor=vendor,
        forward=forward_name,
        user_uuid=user_uuid,
        enabled=_enable_string(True),
    )

    if destination:
        formatted_enabled_url = '{}?destination={}'.format(formatted_enabled_url, destination)

    formatted_disabled_url = FORWARD_URL_FORMAT.format(
        scheme=scheme,
        hostname=hostname,
        port=port,
        vendor=vendor,
        forward=forward_name,
        user_uuid=user_uuid,
        enabled=_enable_string(False),
    )

    raw_config[
        u'XX_wazo_phoned_user_forward_{}_enabled_url'.format(forward_name)
    ] = formatted_enabled_url

    raw_config[
        u'XX_wazo_phoned_user_forward_{}_disabled_url'.format(forward_name)
    ] = formatted_disabled_url


def _enable_string(enabled):
    return 'enable' if enabled else 'disable'
