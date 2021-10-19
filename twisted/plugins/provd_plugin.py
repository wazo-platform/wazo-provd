# -*- coding: utf-8 -*-
# Copyright 2013-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

# Twisted Application Pluguin (tap) file

from __future__ import absolute_import
from twisted.internet import epollreactor
epollreactor.install()

from provd.main import ProvisioningServiceMaker

service_maker = ProvisioningServiceMaker()
