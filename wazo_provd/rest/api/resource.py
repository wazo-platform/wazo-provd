# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.web.static import File

if TYPE_CHECKING:
    from wazo_provd.servers.http_site import Request


class ResponseFile(File):
    def render(self, request: Request) -> bytes:
        return File.render(self, request)

    def render_OPTIONS(self, request: Request) -> bytes:
        return b''
