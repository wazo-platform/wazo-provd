# -*- coding: utf-8 -*-
# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


URL_FORMAT = u'{scheme}://{hostname}:{port}/0.1/{vendor}/user_service/{service}?user_uuid={user_uuid}&enabled={enabled}'


def add_wazo_phoned_user_service_url(
    raw_config,
    vendor,
    service_name,
    enabled,
    destination=None,
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

    formatted_url = URL_FORMAT.format(
        scheme=scheme,
        hostname=hostname,
        port=port,
        vendor=vendor,
        service=service_name,
        user_uuid=user_uuid,
        enabled=enabled,
    )
    if destination:
        formatted_url = u'{}&destination={}'.format(formatted_url, destination)

    raw_config[u'XX_wazo_phoned_user_service_{}_url'.format(service_name)] = formatted_url
