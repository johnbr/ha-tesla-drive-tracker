"""Decode the car's ``RouteLine`` signal.

Tesla documents it as a base64 polyline at precision 6. What the car actually
sends is a base64 protobuf: a metrics-only payload has been seen on a real car
as ``field 2 { field 1: float }``, and a third-party decoder reports the polyline
in field 1 when a route has geometry.

No schema is published, so the protobuf is walked by wire type. Anything that
doesn't parse, or any coordinate outside the world, gives no points: no line
beats a wrong line.

This module imports nothing from Home Assistant.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

GEOMETRY_FIELD = 1
PRECISION = 1e6

_VARINT = 0
_FIXED64 = 1
_LENGTH = 2
_FIXED32 = 5


@dataclass(frozen=True, slots=True)
class RouteLine:
    """The route's points as ``(latitude, longitude)``, empty when none came."""

    points: tuple[tuple[float, float], ...] = ()


def _varint(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, index


def _length_fields(data: bytes) -> dict[int, bytes]:
    """Every length-delimited field at the top level of a protobuf message.

    Raises ``ValueError`` or ``IndexError`` on bytes that aren't one.
    """
    fields: dict[int, bytes] = {}
    index = 0
    while index < len(data):
        tag, index = _varint(data, index)
        number, wire = tag >> 3, tag & 7
        if number == 0:
            raise ValueError("field number 0")
        if wire == _VARINT:
            _, index = _varint(data, index)
        elif wire == _FIXED64:
            index += 8
        elif wire == _FIXED32:
            index += 4
        elif wire == _LENGTH:
            size, index = _varint(data, index)
            fields[number] = data[index : index + size]
            index += size
        else:
            raise ValueError(f"wire type {wire}")
        if index > len(data):
            raise ValueError("truncated")
    return fields


def decode_polyline(text: str) -> tuple[tuple[float, float], ...]:
    """Decode an encoded polyline at precision 6.

    Raises ``ValueError`` when it runs out mid-value or leaves the world.
    """
    points: list[tuple[float, float]] = []
    index = 0
    latitude = 0
    longitude = 0
    while index < len(text):
        deltas = []
        for _ in range(2):
            value = 0
            shift = 0
            while True:
                if index >= len(text):
                    raise ValueError("truncated polyline")
                chunk = ord(text[index]) - 63
                index += 1
                if not 0 <= chunk < 64:
                    raise ValueError("not a polyline")
                value |= (chunk & 0x1F) << shift
                shift += 5
                if chunk < 0x20:
                    break
            deltas.append(~(value >> 1) if value & 1 else value >> 1)
        latitude += deltas[0]
        longitude += deltas[1]
        point = (latitude / PRECISION, longitude / PRECISION)
        if abs(point[0]) > 90 or abs(point[1]) > 180:
            raise ValueError("outside the world")
        points.append(point)
    return tuple(points)


def parse_route_line(payload: str | None) -> RouteLine:
    """The route in a ``RouteLine`` payload, or no points when it has none."""
    if not payload:
        return RouteLine()
    try:
        data = base64.b64decode(payload, validate=True)
        geometry = _length_fields(data).get(GEOMETRY_FIELD)
        if not geometry:
            return RouteLine()
        return RouteLine(decode_polyline(geometry.decode("ascii")))
    except (binascii.Error, ValueError, IndexError, UnicodeDecodeError):
        return RouteLine()
