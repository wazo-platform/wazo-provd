# -*- coding: utf-8 -*-
# Copyright (C) 2010-2014 Avencall
# SPDX-License-Identifier: GPL-3.0+

"""A TFTP server implementation with twisted.

The implementation is not totally RFC1350 (The TFTP protocol) and
RFC2347 (TFTP Option Extension) compliant, but is enough close to
it so that you might not care.

Things to note:
- only read request (RRQ) are supported. There is no support for write
  request (WRQ) as for now.
- netascii mode is not supported -- only octet mode is.
- mail mode is, of course, not supported, since it's deprecated.
- support the blksize option (RFC2348).
- use zero-based wraparound when transferring files taking more than
  65535 blocks to transfer.
- it's not using an adaptive timeout.
- although it would be theorically possible to run the TFTP service on
  a different datagram service than UDP, currently it is not because
  of a hard-coded call to reactor.listenUDP in the code after a request
  is accepted.

"""


from provd.servers.tftp.proto import TFTPProtocol
from provd.servers.tftp.service import *
