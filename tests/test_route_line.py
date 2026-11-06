"""Decode RouteLine payloads.

``METRICS_ONLY`` was sent by a real parked car and holds only a float. The
geometry payloads follow the shape real routes arrive in, with invented points,
because a real route would show where the car has been.
"""
from __future__ import annotations

import base64

import pytest
from tesla_drive_tracker_isolated.route_line import decode_polyline, parse_route_line

METRICS_ONLY = "EgUNvXH8Pw=="
# Field 2 again, with the flag real routes carry on their latest length.
FLAGGED_LENGTH = bytes.fromhex("12070dbd71fc3f1001")
POINTS = ((10.1, 20.1), (10.100123, 20.100456), (10.2, -20.3))


def encode_value(value: int) -> str:
    value = ~(value << 1) if value < 0 else value << 1
    out = ""
    while value >= 0x20:
        out += chr((0x20 | (value & 0x1F)) + 63)
        value >>= 5
    return out + chr(value + 63)


def encode_polyline(points) -> str:
    out = ""
    previous = (0, 0)
    for latitude, longitude in points:
        current = (round(latitude * 1e6), round(longitude * 1e6))
        out += encode_value(current[0] - previous[0])
        out += encode_value(current[1] - previous[1])
        previous = current
    return out


def varint(value: int) -> bytes:
    out = b""
    while value >= 0x80:
        out += bytes([value & 0x7F | 0x80])
        value >>= 7
    return out + bytes([value])


def payload(polyline: str, *, metrics: bool = True) -> str:
    text = polyline.encode()
    data = b"\x0a" + varint(len(text)) + text
    if metrics:
        data += base64.b64decode(METRICS_ONLY) + FLAGGED_LENGTH
    return base64.b64encode(data).decode()


def test_polyline_round_trip() -> None:
    assert decode_polyline(encode_polyline(POINTS)) == POINTS


def test_real_metrics_only_payload_has_no_points() -> None:
    assert parse_route_line(METRICS_ONLY).points == ()


def test_geometry_in_field_one() -> None:
    assert parse_route_line(payload(encode_polyline(POINTS))).points == POINTS


def test_a_long_route_survives_multi_byte_lengths() -> None:
    points = tuple((10 + i / 1000, 20 + i / 1000) for i in range(2000))
    assert len(parse_route_line(payload(encode_polyline(points))).points) == 2000


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        "not base64!",
        base64.b64encode(b"\xff\xff\xff").decode(),  # varint runs out
        base64.b64encode(b"\x0a\x05ab").decode(),  # length past the end
        base64.b64encode(b"\x0b\x00").decode(),  # group wire type
    ],
)
def test_bad_payloads_give_no_points(bad) -> None:
    assert parse_route_line(bad).points == ()


def test_truncated_polyline_gives_no_points() -> None:
    text = encode_polyline(POINTS)[:-1] + "_"
    assert parse_route_line(payload(text)).points == ()


def test_coordinates_outside_the_world_give_no_points() -> None:
    text = encode_polyline(((95.0, 20.0),))
    assert parse_route_line(payload(text)).points == ()
