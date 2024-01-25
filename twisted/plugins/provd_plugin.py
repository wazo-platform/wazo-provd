# Copyright 2013-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

# Twisted Application Plugin (tap) file

from twisted.internet import epollreactor

epollreactor.install()

from wazo_provd.main import ProvisioningServiceMaker  # noqa: E402

service_maker = ProvisioningServiceMaker()
