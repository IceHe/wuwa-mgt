#!/usr/bin/env python3

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"

M_SHAPE = [
    (0.28, 0.75),
    (0.28, 0.25),
    (0.41, 0.25),
    (0.5, 0.444),
    (0.59, 0.25),
    (0.72, 0.25),
    (0.72, 0.75),
    (0.607, 0.75),
    (0.607, 0.467),
    (0.5, 0.662),
    (0.393, 0.467),
    (0.393, 0.75),
]

M_ACCENT = [
    (0.399, 0.281),
    (0.425, 0.281),
    (0.5, 0.439),
    (0.575, 0.281),
    (0.601, 0.281),
    (0.5, 0.491),
]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def alpha_from_signed_distance(distance: float, aa: float) -> float:
    return clamp(0.5 - distance / aa)


def blend(dst: tuple[float, float, float, float], src: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    sr, sg, sb, sa = src
    dr, dg, db, da = dst
    out_a = sa + da * (1.0 - sa)
    if out_a <= 0.0:
        return 0.0, 0.0, 0.0, 0.0
    out_r = (sr * sa + dr * da * (1.0 - sa)) / out_a
    out_g = (sg * sa + dg * da * (1.0 - sa)) / out_a
    out_b = (sb * sa + db * da * (1.0 - sa)) / out_a
    return out_r, out_g, out_b, out_a


def rounded_rect_alpha(x: float, y: float, width: int, height: int, radius: float, aa: float) -> float:
    px = x - width / 2.0
    py = y - height / 2.0
    qx = abs(px) - (width / 2.0 - radius)
    qy = abs(py) - (height / 2.0 - radius)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    distance = outside + inside - radius
    return alpha_from_signed_distance(distance, aa)


def circle_alpha(x: float, y: float, cx: float, cy: float, radius: float, aa: float) -> float:
    distance = math.hypot(x - cx, y - cy) - radius
    return alpha_from_signed_distance(distance, aa)


def scale_points(points: list[tuple[float, float]], size: int) -> list[tuple[float, float]]:
    return [(size * px, size * py) for px, py in points]


def offset_points(points: list[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    return [(px + dx, py + dy) for px, py in points]


def distance_to_segment(
    x: float,
    y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0.0 and dy == 0.0:
        return math.hypot(x - x1, y - y1)
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = clamp(t)
    nearest_x = x1 + dx * t
    nearest_y = y1 + dy * t
    return math.hypot(x - nearest_x, y - nearest_y)


def point_in_polygon(x: float, y: float, points: list[tuple[float, float]]) -> bool:
    inside = False
    prev_x, prev_y = points[-1]
    for curr_x, curr_y in points:
        intersects = (curr_y > y) != (prev_y > y)
        if intersects:
            cross_x = (prev_x - curr_x) * (y - curr_y) / (prev_y - curr_y) + curr_x
            if x < cross_x:
                inside = not inside
        prev_x, prev_y = curr_x, curr_y
    return inside


def polygon_alpha(x: float, y: float, points: list[tuple[float, float]], aa: float) -> float:
    min_distance = min(
        distance_to_segment(x, y, x1, y1, x2, y2)
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )
    signed_distance = -min_distance if point_in_polygon(x, y, points) else min_distance
    return alpha_from_signed_distance(signed_distance, aa)


def to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16) / 255.0,
        int(hex_color[2:4], 16) / 255.0,
        int(hex_color[4:6], 16) / 255.0,
        alpha,
    )


def render_icon(size: int) -> bytes:
    aa = max(0.9, size / 96.0)
    pixels = bytearray()
    m_shape = scale_points(M_SHAPE, size)
    m_shadow = offset_points(m_shape, 0.0, size * 0.03)
    m_accent = scale_points(M_ACCENT, size)

    for y_index in range(size):
        y = y_index + 0.5
        for x_index in range(size):
            x = x_index + 0.5
            px = x / size
            py = y / size

            bg_alpha = rounded_rect_alpha(x, y, size, size, radius=size * 0.25, aa=aa)
            base_mix = clamp(0.5 * px + 0.5 * py)
            highlight = math.exp(-(((px - 0.24) ** 2) / 0.032 + ((py - 0.18) ** 2) / 0.026))
            glow = math.exp(-(((px - 0.86) ** 2) / 0.06 + ((py - 0.9) ** 2) / 0.08))

            start = to_rgba("#0c6f42", bg_alpha)
            end = to_rgba("#58d480", bg_alpha)
            color = (
                start[0] * (1.0 - base_mix) + end[0] * base_mix,
                start[1] * (1.0 - base_mix) + end[1] * base_mix,
                start[2] * (1.0 - base_mix) + end[2] * base_mix,
                bg_alpha,
            )

            if highlight > 0.001:
                color = blend(color, (1.0, 1.0, 1.0, 0.16 * highlight * bg_alpha))
            if glow > 0.001:
                color = blend(color, (0.73, 1.0, 0.82, 0.12 * glow * bg_alpha))

            border = rounded_rect_alpha(x, y, size, size, radius=size * 0.25, aa=aa) - rounded_rect_alpha(
                x, y, size, size, radius=size * 0.235, aa=aa
            )
            if border > 0.0:
                color = blend(color, (0.96, 1.0, 0.97, border * 0.18))

            shadow = polygon_alpha(x, y, m_shadow, aa * 1.15)
            if shadow > 0.0:
                color = blend(color, (0.05, 0.25, 0.13, shadow * 0.17))

            mark = polygon_alpha(x, y, m_shape, aa)
            if mark > 0.0:
                mark_highlight = math.exp(-(((px - 0.37) ** 2) / 0.018 + ((py - 0.3) ** 2) / 0.05))
                fill = (
                    0.94 + 0.04 * mark_highlight,
                    0.99 + 0.01 * mark_highlight,
                    0.95 + 0.03 * mark_highlight,
                    mark * 0.98,
                )
                color = blend(color, fill)

            accent = polygon_alpha(x, y, m_accent, aa * 0.95)
            if accent > 0.0:
                color = blend(color, to_rgba("#bff4cb", accent * 0.72))

            sheen = circle_alpha(x, y, size * 0.24, size * 0.18, size * 0.28, aa * 1.6)
            if sheen > 0.0:
                color = blend(color, (1.0, 1.0, 1.0, sheen * 0.035 * bg_alpha))

            r = round(clamp(color[0]) * 255)
            g = round(clamp(color[1]) * 255)
            b = round(clamp(color[2]) * 255)
            a = round(clamp(color[3]) * 255)
            pixels.extend((r, g, b, a))

    return png_bytes(size, size, bytes(pixels))


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def png_bytes(width: int, height: int, rgba: bytes) -> bytes:
    raw_rows = bytearray()
    row_stride = width * 4
    for offset in range(0, len(rgba), row_stride):
        raw_rows.append(0)
        raw_rows.extend(rgba[offset : offset + row_stride])
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            png_chunk(b"IDAT", zlib.compress(bytes(raw_rows), level=9)),
            png_chunk(b"IEND", b""),
        ]
    )


def write_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    header = struct.pack("<HHH", 0, 1, len(images))
    entry_size = 16
    offset = 6 + entry_size * len(images)
    directory = bytearray()
    payload = bytearray()

    for size, data in images:
        width_byte = 0 if size >= 256 else size
        height_byte = 0 if size >= 256 else size
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                width_byte,
                height_byte,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        payload.extend(data)
        offset += len(data)

    path.write_bytes(header + bytes(directory) + bytes(payload))


def main() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 48, 64]
    rendered = [(size, render_icon(size)) for size in sizes]
    write_ico(PUBLIC_DIR / "favicon.ico", rendered)
    (PUBLIC_DIR / "favicon-256.png").write_bytes(render_icon(256))


if __name__ == "__main__":
    main()
