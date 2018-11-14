# -*- coding: utf-8 -*-

"""Plugin that offers no configuration service and serves TFTP/HTTP requests
in its var/tftpboot directory.

"""

__version__ = "$Revision: 10355 $ $Date: 2011-03-08 14:38:11 -0500 (Tue, 08 Mar 2011) $"
__license__ = """
    Copyright 2010-2018 The Wazo Authors  (see the AUTHORS file)
    SPDX-License-Identifier: GPL-3.0+
"""

from provd.plugins import StandardPlugin
from provd.servers.http import HTTPNoListingFileService
from provd.servers.tftp.service import TFTPFileService


class ZeroPlugin(StandardPlugin):
    IS_PLUGIN = True

    def __init__(self, app, plugin_dir, gen_cfg, spec_cfg):
        StandardPlugin.__init__(self, app, plugin_dir, gen_cfg, spec_cfg)
        self.tftp_service = TFTPFileService(self._tftpboot_dir)
        self.http_service = HTTPNoListingFileService(self._tftpboot_dir)
