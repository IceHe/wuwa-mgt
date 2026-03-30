#!/usr/bin/env python3

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    t = clamp((value - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


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


def circle_alpha(x: float, y: float, cx: float, cy: float, radius: float, aa: float) -> float:
    distance = math.hypot(x - cx, y - cy) - radius
    return alpha_from_signed_distance(distance, aa)


def ring_alpha(x: float, y: float, cx: float, cy: float, radius: float, thickness: float, aa: float) -> float:
    distance = abs(math.hypot(x - cx, y - cy) - radius) - thickness / 2.0
    return alpha_from_signed_distance(distance, aa)


def rounded_rect_alpha(x: float, y: float, width: int, height: int, radius: float, aa: float) -> float:
    px = x - width / 2.0
    py = y - height / 2.0
    qx = abs(px) - (width / 2.0 - radius)
    qy = abs(py) - (height / 2.0 - radius)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    distance = outside + inside - radius
    return alpha_from_signed_distance(distance, aa)


def in_arc(angle: float, start: float, end: float) -> bool:
    angle = (angle + math.tau) % math.tau
    start = (start + math.tau) % math.tau
    end = (end + math.tau) % math.tau
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


def arc_ring_alpha(
    x: float,
    y: float,
    cx: float,
    cy: float,
    radius: float,
    thickness: float,
    start_deg: float,
    end_deg: float,
    aa: float,
) -> float:
    angle = math.atan2(y - cy, x - cx)
    if not in_arc(angle, math.radians(start_deg), math.radians(end_deg)):
        return 0.0
    return ring_alpha(x, y, cx, cy, radius, thickness, aa)


def to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16) / 255.0,
        int(hex_color[2:4], 16) / 255.0,
        int(hex_color[4:6], 16) / 255.0,
        alpha,
    )


def render_icon(size: int) -> bytes:
    aa = max(0.85, size / 96.0)
    pixels = bytearray()
    width = size
    height = size

    for y_index in range(height):
        y = y_index + 0.5
        for x_index in range(width):
            x = x_index + 0.5
            px = x / width
            py = y / height

            bg_alpha = rounded_rect_alpha(x, y, width, height, radius=size * 0.22, aa=aa)
            base_mix = clamp(0.58 * px + 0.42 * py)
            highlight = math.exp(-(((px - 0.2) ** 2) / 0.03 + ((py - 0.16) ** 2) / 0.022))
            glow = math.exp(-(((px - 0.8) ** 2) / 0.05 + ((py - 0.9) ** 2) / 0.08))

            base_start = to_rgba("#0f4fb5", bg_alpha)
            base_end = to_rgba("#5aa8ff", bg_alpha)
            bg_color = (
                base_start[0] * (1.0 - base_mix) + base_end[0] * base_mix,
                base_start[1] * (1.0 - base_mix) + base_end[1] * base_mix,
                base_start[2] * (1.0 - base_mix) + base_end[2] * base_mix,
                bg_alpha,
            )
            if highlight > 0.001:
                bg_color = blend(bg_color, (1.0, 1.0, 1.0, 0.14 * highlight * bg_alpha))
            if glow > 0.001:
                bg_color = blend(bg_color, (0.12, 0.83, 1.0, 0.16 * glow * bg_alpha))

            color = bg_color

            shadow_alpha = ring_alpha(x, y, size * 0.49, size * 0.51, size * 0.24, size * 0.15, aa * 1.2) * 0.16
            if shadow_alpha > 0.0:
                color = blend(color, (0.0, 0.07, 0.18, shadow_alpha))

            ring = ring_alpha(x, y, size * 0.48, size * 0.5, size * 0.22, size * 0.135, aa)
            if ring > 0.0:
                color = blend(color, to_rgba("#f8fbff", ring))

            accent = arc_ring_alpha(x, y, size * 0.48, size * 0.5, size * 0.22, size * 0.145, -28, 64, aa)
            if accent > 0.0:
                color = blend(color, to_rgba("#69e3ff", accent * 0.96))

            inner = circle_alpha(x, y, size * 0.48, size * 0.5, size * 0.105, aa)
            if inner > 0.0:
                inner_color = (
                    0.87 + 0.06 * highlight,
                    0.94 + 0.03 * highlight,
                    1.0,
                    inner * 0.92,
                )
                color = blend(color, inner_color)

            core_glow = circle_alpha(x, y, size * 0.48, size * 0.5, size * 0.045, aa * 1.1)
            if core_glow > 0.0:
                color = blend(color, (0.08, 0.62, 1.0, core_glow * 0.4))

            alert_shadow = circle_alpha(x, y, size * 0.77, size * 0.25, size * 0.08, aa * 1.15) * 0.18
            if alert_shadow > 0.0:
                color = blend(color, (0.0, 0.08, 0.2, alert_shadow))

            alert = circle_alpha(x, y, size * 0.765, size * 0.24, size * 0.075, aa)
            if alert > 0.0:
                color = blend(color, to_rgba("#ffb347", alert))

            alert_shine = circle_alpha(x, y, size * 0.748, size * 0.223, size * 0.026, aa)
            if alert_shine > 0.0:
                color = blend(color, (1.0, 0.98, 0.92, alert_shine * 0.68))

            r = round(clamp(color[0]) * 255)
            g = round(clamp(color[1]) * 255)
            b = round(clamp(color[2]) * 255)
            a = round(clamp(color[3]) * 255)
            pixels.extend((r, g, b, a))

    return png_bytes(width, height, bytes(pixels))


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
