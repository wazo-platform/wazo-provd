# -*- coding: utf-8 -*-
# Copyright 2016-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import
import logging

_logger = logging.getLogger(__name__)


def setup_logging():
    formatter = logging.Formatter('[%(asctime)s] %(message)s')
    handler = logging.FileHandler('/var/log/wazo-provd-fail2ban.log')
    handler.setFormatter(formatter)
    _logger.addHandler(handler)


def log_security_msg(msg, *args):
    _logger.info(msg, *args)
