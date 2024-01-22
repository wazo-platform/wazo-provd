# Copyright 2010-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Low-level functions to manipulate packets and datagrams.

A packet is a dictionary object. A dgram (datagram) is a string object.

"""
from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict, Union

from wazo_provd.app import logger

PacketOptions = dict[bytes, Union[bytes, int]]


class BasePacket(TypedDict):
    opcode: bytes


class RequestPacket(BasePacket):
    filename: bytes
    mode: bytes
    options: PacketOptions


class AckPacket(BasePacket):
    blkno: bytes


class OptionAckPacket(BasePacket):
    options: dict[bytes, Union[bytes, int]]


class ByteOptionAckPacket(BasePacket):
    options: dict[bytes, bytes]


class DataPacket(BasePacket):
    blkno: bytes
    data: bytes


class ErrorPacket(BasePacket):
    errcode: bytes
    errmsg: bytes


Packet = Union[AckPacket, DataPacket, ErrorPacket, OptionAckPacket, RequestPacket]

OP_RRQ = b'\x00\x01'
OP_WRQ = b'\x00\x02'
OP_DATA = b'\x00\x03'
OP_ACK = b'\x00\x04'
OP_ERR = b'\x00\x05'
OP_OACK = b'\x00\x06'

ERR_UNDEF = b'\x00\x00'  # Not defined, see error message (if any)
ERR_FNF = b'\x00\x01'  # File not found
ERR_ACCESS = b'\x00\x02'  # Access violation
ERR_ALLOC = b'\x00\x03'  # Disk full or allocation exceeded
ERR_ILL = b'\x00\x04'  # Illegal TFTP operation
ERR_UNKNWN_TID = b'\x00\x05'  # Unknown transfer ID
ERR_FEXIST = b'\x00\x06'  # File already exists
ERR_NO_USER = b'\x00\x07'  # No such user


class PacketError(Exception):
    """Raise when a problem with parsing/building a datagram arise."""

    pass


def _parse_option_blksize(string: bytes) -> int:
    try:
        blksize = int(string)
    except ValueError:
        raise PacketError('invalid blksize value - not a number')

    if blksize < 8 or blksize > 65464:
        raise PacketError('invalid blksize value - out of range')
    return blksize


_PARSE_OPT_MAP: dict[bytes, Callable[[bytes], int]] = {
    b'blksize': _parse_option_blksize,
}


def _parse_request(opcode: bytes, dgram: bytes) -> RequestPacket:
    """dgram is the original datagram with the first 2 bytes removed.

    TFTP option extension is supported.

    """
    # XXX RFC2347 (TFTP Option Extension) says request should not be longer
    #     than 512 byte, but we omit this check since I don't think we care
    # Note: 'file\x00mode\x00'.split('\x00') == ['file', 'mode', '']
    tokens = dgram.split(b'\x00')
    if len(tokens) < 3:
        raise PacketError('too small')
    if dgram[-1:] != b'\x00':
        assert tokens[-1]
        raise PacketError('last dgram byte not null')
    if len(tokens) % 2 == 0:
        raise PacketError('invalid number of field')

    options: PacketOptions = {}
    for i in range(2, len(tokens) - 1, 2):
        opt = tokens[i].lower()
        val = tokens[i + 1].lower()
        if opt in options:
            # An option may only be specified once
            raise PacketError('same option specified more than once')
        opt_fct = _PARSE_OPT_MAP.get(opt, lambda x: x)
        options[opt] = opt_fct(val)
        logger.error(
            'Filename: %s, mode: %s, Options: %s',
            tokens[0],
            tokens[1].lower(),
            options,
        )
    return {
        'filename': tokens[0],
        'mode': tokens[1].lower(),
        'options': options,
        'opcode': opcode,
    }


def _parse_data(opcode: bytes, dgram: bytes) -> DataPacket:
    if len(dgram) < 2:
        raise PacketError('too small')
    return {'blkno': dgram[:2], 'data': dgram[2:], 'opcode': opcode}


def _parse_ack(opcode: bytes, dgram: bytes) -> AckPacket:
    if len(dgram) != 2:
        raise PacketError('incorrect size')
    return {'blkno': dgram, 'opcode': opcode}


def _parse_err(opcode: bytes, dgram: bytes) -> ErrorPacket:
    if len(dgram) < 3:
        raise PacketError('too small')
    if dgram[-1:] != b'\x00':
        raise PacketError('last datagram byte not null')
    return {'errcode': dgram[:2], 'errmsg': dgram[2:-1], 'opcode': opcode}


_PARSE_MAP: dict[bytes, Callable[[bytes, bytes], Packet]] = {
    OP_RRQ: _parse_request,
    OP_WRQ: _parse_request,
    OP_DATA: _parse_data,
    OP_ACK: _parse_ack,
    OP_ERR: _parse_err,
}


def parse_dgram(dgram: bytes) -> Packet:
    """Return a packet object (a dictionary) from a datagram (a string).

    Raise a PacketError if the datagram is not parsable (i.e. invalid). Else,
    return a dictionary with the following keys:
      opcode -- the opcode of the packet as a 2-byte string

    The others keys in the dictionary depends on the type of the packet.

    Read/write request:
      filename -- the filename
      mode -- the mode
      options -- a possibly empty dictionary of option/value in bytes

    Data packet:
      blkno -- the block number as a 2-byte string
      data -- the data

    Ack packet:
      blkno -- the block number as a 2-byte string

    Error packet:
      errcode -- the error code as a 2-byte string
      errmsg -- the error message

    Option acknowledgement datagrams are currently not supported. Also,
    case-insensitive field (mode field of request packet and option name)
    are returned in lowercase.

    """
    opcode = dgram[:2]
    try:
        fct = _PARSE_MAP[opcode]
    except KeyError:
        raise PacketError('invalid opcode')

    return fct(opcode, dgram[2:])


def _build_data(packet: DataPacket) -> bytes:
    if len(packet['blkno']) != 2:
        raise PacketError('invalid blkno length')
    return packet['blkno'] + packet['data']


def _build_error(packet: ErrorPacket) -> bytes:
    if len(packet['errcode']) != 2:
        raise PacketError('invalid errcode length')
    elif b'\x00' in packet['errmsg']:
        raise PacketError('null byte in errmsg')
    return packet['errcode'] + packet['errmsg'] + b'\x00'


def _build_oack(packet: ByteOptionAckPacket) -> bytes:
    for opt, val in packet['options'].items():
        if b'\x00' in opt or b'\x00' in val:
            raise PacketError('null byte in option/value')
    return (
        b'\x00'.join(elem for pair in packet['options'].items() for elem in pair)
        + b'\x00'
    )


BuildCallbacks = Union[
    Callable[[DataPacket], bytes],
    Callable[[ErrorPacket], bytes],
    Callable[[ByteOptionAckPacket], bytes],
]

_BUILD_MAP: dict[bytes, BuildCallbacks] = {
    OP_DATA: _build_data,
    OP_ERR: _build_error,
    OP_OACK: _build_oack,
}


def build_dgram(packet: Packet) -> bytes:
    """Return a datagram (bytes) from a packet objet (a dictionary).

    Raise KeyError if a key is missing from the packet object. A PacketError
    is raised if the datagram can't be build (invalid field in the packet).

    Look at parse_dgram for the keys that must be in the packet objects.

    Only OACK, DATA and ERROR packet are supported.

    """
    opcode = packet['opcode']
    try:
        fct = _BUILD_MAP[opcode]
    except KeyError:
        raise PacketError('invalid opcode')
    return opcode + fct(packet)  # type: ignore[arg-type]


def err_packet(errcode: bytes, errmsg: bytes = b'') -> ErrorPacket:
    """Return a new error packet.

    errcode is a 2-byte string and errmsg is a NVT ASCII string.

    """
    return {'opcode': OP_ERR, 'errcode': errcode, 'errmsg': errmsg}


def data_packet(blk_no: bytes, data: bytes) -> DataPacket:
    """Return a new data packet.

    blk_no is a 2-byte string and data is a string.

    """
    return {'opcode': OP_DATA, 'blkno': blk_no, 'data': data}


def oack_packet(options: PacketOptions) -> OptionAckPacket:
    """Return a new option acknowledgement packet.

    Options is a dictionary of option/value.

    """
    return {'opcode': OP_OACK, 'options': options}
