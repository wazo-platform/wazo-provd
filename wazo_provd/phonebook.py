# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_URL_META_FORMAT = (
    '{{scheme}}://{{hostname}}:{{port}}/0.1/directories/{entry_point}/default/{vendor}?'
    '{qs_prefix}xivo_user_uuid={{user_uuid}}{qs_suffix}'
)


def add_xivo_phonebook_url(
    raw_config: dict[str, Any],
    vendor: str,
    entry_point: str = 'input',
    qs_prefix: str = '',
    qs_suffix: str = '',
) -> None:
    url_format = _build_url_format(vendor, entry_point, qs_prefix, qs_suffix)
    add_xivo_phonebook_url_from_format(raw_config, url_format)


def _build_url_format(
    vendor: str, entry_point: str, qs_prefix: str, qs_suffix: str
) -> str:
    if qs_prefix:
        qs_prefix = qs_prefix + '&'
    if qs_suffix:
        qs_suffix = '&' + qs_suffix
    return _URL_META_FORMAT.format(
        vendor=vendor,
        entry_point=entry_point,
        qs_prefix=qs_prefix,
        qs_suffix=qs_suffix,
    )


def add_xivo_phonebook_url_from_format(raw_config, url_format) -> None:
    if not (hostname := raw_config.get('X_xivo_phonebook_ip')):
        return

    if not (user_uuid := raw_config.get('X_xivo_user_uuid')):
        logger.warning('Not adding XX_xivo_phonebook_url: no user uuid')
        return

    scheme = raw_config.get('X_xivo_phonebook_scheme', 'http')
    port = raw_config.get('X_xivo_phonebook_port', 9498)
    raw_config['XX_xivo_phonebook_url'] = url_format.format(
        scheme=scheme,
        hostname=hostname,
        profile='default',
        port=port,
        user_uuid=user_uuid,
    )
