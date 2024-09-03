# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger(__name__)


def setup_logging() -> None:
    formatter = logging.Formatter('[%(asctime)s] %(message)s')
    handler = logging.FileHandler('/var/log/wazo-provd-fail2ban.log')
    handler.setFormatter(formatter)
    _logger.addHandler(handler)


def log_security_msg(msg: str, *args: Any) -> None:
    _logger.info(msg, *args)
