# -*- coding: utf-8 -*-

"""Plugin that offers no configuration service and rejects TFTP/HTTP requests
by returning file not found errors.

"""

__version__ = "$Revision: 10355 $ $Date: 2011-03-08 14:38:11 -0500 (Tue, 08 Mar 2011) $"
__license__ = """
    Copyright 2010-2018 The Wazo Authors  (see the AUTHORS file)
    SPDX-License-Identifier: GPL-3.0+
"""

from provd.plugins import Plugin
from provd.servers.tftp.service import TFTPNullService
from twisted.web.resource import NoResource

_MSG = 'Null plugin always reject requests'


class NullPlugin(Plugin):
    IS_PLUGIN = True

    http_service = NoResource(_MSG)
    tftp_service = TFTPNullService(errmsg=_MSG)
