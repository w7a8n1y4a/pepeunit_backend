import hashlib
from io import BytesIO
from typing import NamedTuple

from PIL import Image, ImageDraw, UnidentifiedImageError

from app.configs.errors import ValidationError

Rgb = tuple[int, int, int]
_SIDE = 192
_MASK = (1 << 64) - 1
# Mondrian's structural black. Biome color never replaces it.
_RULE = (22, 18, 20)


class IconImage:
    """192x192 PNG. The same seed always draws the same bytes.

    Hard-edge painting: a Minecraft biome palette, one abstract
    composition, and a single concrete thing (tree, cactus, mushroom,
    sail, portal, sun, or block).
    """

    SIDE = _SIDE
    MAX_BYTES = 128 * 1024
    _SIGNATURE = b"\x89PNG\r\n\x1a\n"

    @classmethod
    def generate(cls, seed: str) -> bytes:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return cls._render(digest)

    @classmethod
    def md5(cls, image: bytes) -> str:
        return hashlib.md5(image, usedforsecurity=False).hexdigest()

    @classmethod
    def validate(cls, data: bytes) -> None:
        if len(data) > cls.MAX_BYTES:
            msg = "Image is larger than 128KB"
            raise ValidationError(msg)
        cls._require_header(data)
        cls._require_decoded(data)

    @classmethod
    def _require_header(cls, data: bytes) -> None:
        if (
            len(data) < 24
            or not data.startswith(cls._SIGNATURE)
            or int.from_bytes(data[8:12], "big") != 13
            or data[12:16] != b"IHDR"
        ):
            msg = "Image is not a PNG"
            raise ValidationError(msg)
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if (width, height) != (cls.SIDE, cls.SIDE):
            msg = "Image must be 192x192 px"
            raise ValidationError(msg)

    @classmethod
    def _require_decoded(cls, data: bytes) -> None:
        try:
            with Image.open(BytesIO(data)) as image:
                image.load()
                if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                    msg = "Image is not a PNG"
                    raise ValidationError(msg)
                if image.size != (cls.SIDE, cls.SIDE):
                    msg = "Image must be 192x192 px"
                    raise ValidationError(msg)
        except ValidationError:
            raise
        except (
            UnidentifiedImageError,
            Image.DecompressionBombError,
            OSError,
            ValueError,
            SyntaxError,
        ) as err:
            msg = "Image is not a PNG"
            raise ValidationError(msg) from err

    @classmethod
    def _render(cls, digest: bytes) -> bytes:
        ink = _Ink(digest)
        biome = _Biome.ALL[ink.pick(len(_Biome.ALL))]
        image = Image.new("RGB", (cls.SIDE, cls.SIDE), biome.sky)
        _Picture.ALL[ink.pick(len(_Picture.ALL))](
            ImageDraw.Draw(image), ink, biome
        )
        buffer = BytesIO()
        image.save(buffer, format="PNG", compress_level=9)
        return buffer.getvalue()


class _Ink:
    """Integer stream. The same digest always yields the same numbers."""

    def __init__(self, digest: bytes) -> None:
        state = 0
        for byte in digest:
            state = (state * 131 + byte) & _MASK
        self._state = state or 1

    def u8(self) -> int:
        self._state = (
            self._state * 6364136223846793005 + 1442695040888963407
        ) & _MASK
        return (self._state >> 33) & 255

    def span(self, low: int, high: int) -> int:
        return low + self.u8() % (high - low + 1)

    def pick(self, count: int) -> int:
        return self.u8() % count

    def bit(self) -> bool:
        return bool(self.u8() & 1)


class _Biome(NamedTuple):
    sky: Rgb
    ground: Rgb
    shade: Rgb
    leaf: Rgb
    accent: Rgb
    light: Rgb
    motifs: tuple[int, int, int]


# Motif index: oak spruce cactus mushroom flower blocks
# acacia spike chorus mesa sail fall.
_Biome.ALL = (
    _Biome(
        (126, 166, 246),
        (132, 180, 78),
        (102, 72, 46),
        (58, 114, 46),
        (204, 62, 58),
        (255, 206, 84),
        (0, 4, 5),
    ),
    _Biome(
        (148, 188, 242),
        (216, 198, 124),
        (168, 146, 82),
        (58, 104, 42),
        (186, 96, 48),
        (255, 220, 140),
        (2, 2, 5),
    ),
    _Biome(
        (110, 156, 230),
        (98, 66, 42),
        (52, 36, 24),
        (40, 102, 38),
        (184, 84, 60),
        (190, 210, 146),
        (0, 1, 4),
    ),
    _Biome(
        (132, 170, 210),
        (232, 238, 242),
        (54, 40, 30),
        (30, 62, 44),
        (104, 140, 156),
        (255, 255, 255),
        (1, 7, 5),
    ),
    _Biome(
        (164, 176, 158),
        (58, 78, 60),
        (36, 44, 34),
        (92, 122, 50),
        (70, 104, 46),
        (210, 212, 190),
        (0, 3, 4),
    ),
    _Biome(
        (124, 176, 238),
        (26, 96, 172),
        (10, 42, 108),
        (32, 136, 152),
        (228, 108, 82),
        (224, 236, 242),
        (10, 5, 4),
    ),
    _Biome(
        (92, 152, 224),
        (16, 72, 28),
        (8, 40, 18),
        (46, 148, 50),
        (180, 100, 40),
        (168, 200, 60),
        (0, 0, 4),
    ),
    _Biome(
        (156, 194, 238),
        (182, 164, 68),
        (88, 56, 30),
        (186, 108, 44),
        (78, 102, 42),
        (255, 214, 136),
        (6, 2, 5),
    ),
    _Biome(
        (120, 168, 216),
        (168, 70, 50),
        (88, 42, 36),
        (200, 110, 58),
        (212, 160, 84),
        (228, 186, 146),
        (9, 5, 7),
    ),
    _Biome(
        (170, 160, 192),
        (114, 102, 128),
        (68, 58, 84),
        (146, 106, 68),
        (174, 42, 46),
        (238, 230, 216),
        (3, 3, 5),
    ),
    _Biome(
        (32, 10, 12),
        (148, 52, 44),
        (54, 16, 16),
        (255, 88, 22),
        (255, 172, 44),
        (255, 216, 140),
        (11, 5, 11),
    ),
    _Biome(
        (10, 8, 18),
        (208, 202, 148),
        (42, 36, 58),
        (150, 96, 172),
        (194, 148, 204),
        (238, 234, 198),
        (8, 5, 8),
    ),
    _Biome(
        (248, 206, 218),
        (120, 150, 78),
        (84, 56, 60),
        (234, 124, 164),
        (255, 182, 200),
        (255, 234, 238),
        (0, 4, 4),
    ),
    _Biome(
        (146, 186, 218),
        (238, 246, 252),
        (36, 86, 138),
        (64, 156, 196),
        (150, 214, 232),
        (255, 255, 255),
        (7, 7, 5),
    ),
    _Biome(
        (12, 26, 20),
        (62, 118, 52),
        (22, 32, 26),
        (78, 140, 58),
        (210, 92, 134),
        (238, 182, 56),
        (4, 0, 5),
    ),
    _Biome(
        (8, 10, 14),
        (14, 78, 80),
        (4, 28, 32),
        (18, 120, 112),
        (42, 176, 162),
        (188, 198, 196),
        (5, 7, 5),
    ),
)


class _Pen:
    """Integer marks and the colors that contrast with the field under them."""

    @staticmethod
    def dist(left: Rgb, right: Rgb) -> int:
        return (
            abs(left[0] - right[0])
            + abs(left[1] - right[1])
            + abs(left[2] - right[2])
        )

    @staticmethod
    def focal(
        biome: _Biome, background: Rgb, count: int = 3
    ) -> tuple[Rgb, ...]:
        ranked = sorted(
            (
                biome.sky,
                biome.ground,
                biome.shade,
                biome.leaf,
                biome.accent,
                biome.light,
            ),
            key=lambda color: _Pen.dist(background, color),
            reverse=True,
        )
        return tuple(ranked[:count])

    @staticmethod
    def sun_color(biome: _Biome) -> Rgb:
        if _Pen.dist(biome.sky, biome.light) >= 150:
            return biome.light
        return _Pen.focal(biome, biome.sky)[0]

    @staticmethod
    def fill(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Rgb,
    ) -> None:
        # Integer corners only, so two hosts fill the same pixels.
        if width <= 0 or height <= 0:
            return
        draw.rectangle((x, y, x + width - 1, y + height - 1), fill=color)

    @staticmethod
    def disc(
        draw: ImageDraw.ImageDraw,
        cx: int,
        cy: int,
        rx: int,
        ry: int,
        color: Rgb,
    ) -> None:
        if rx <= 0 or ry <= 0:
            return
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=color)

    @staticmethod
    def cube(
        draw: ImageDraw.ImageDraw,
        x: int,
        y: int,
        side: int,
        outer: Rgb,
        inner: Rgb,
    ) -> None:
        _Pen.fill(draw, x, y, side, side, outer)
        margin = max(4, side // 5)
        _Pen.fill(
            draw,
            x + margin,
            y + margin,
            side - 2 * margin,
            side - 2 * margin,
            inner,
        )

    @staticmethod
    def sun(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        low: int,
        high: int,
    ) -> None:
        size = ink.span(48, 76)
        cx = ink.span(10, _SIDE - 10)
        cy = ink.span(low, max(low, high))
        color = _Pen.sun_color(biome)
        if ink.bit():
            _Pen.fill(draw, cx - size // 2, cy - size // 2, size, size, color)
            return
        _Pen.disc(draw, cx, cy, size // 2, size // 2, color)

    @staticmethod
    def contrast_pair(biome: _Biome) -> tuple[Rgb, Rgb]:
        colors = (
            biome.sky,
            biome.ground,
            biome.shade,
            biome.leaf,
            biome.accent,
            biome.light,
        )
        best = (colors[0], colors[1])
        score = -1
        for index, left in enumerate(colors):
            for right in colors[index + 1 :]:
                dist = _Pen.dist(left, right)
                if dist <= score:
                    continue
                best = (left, right)
                score = dist
        return best

    @staticmethod
    def banner_colors(biome: _Biome) -> tuple[Rgb, Rgb, Rgb]:
        pair = _Pen.contrast_pair(biome)
        for color in (biome.sky, biome.shade, biome.ground, biome.leaf):
            if color not in pair:
                return color, pair[0], pair[1]
        return biome.shade, pair[0], pair[1]

    @staticmethod
    def stamp_colors(biome: _Biome, dark: Rgb, light: Rgb) -> tuple[Rgb, Rgb]:
        rest = [
            color
            for color in (
                biome.sky,
                biome.ground,
                biome.shade,
                biome.leaf,
                biome.accent,
                biome.light,
            )
            if color not in (dark, light)
        ]
        outer = max(
            rest,
            key=lambda color: _Pen.dist(color, dark) + _Pen.dist(color, light),
        )
        inner = (
            dark
            if _Pen.dist(outer, dark) >= _Pen.dist(outer, light)
            else light
        )
        return outer, inner


class _Motif:
    """One concrete object: tree, cactus, mushroom, sail, block."""

    @staticmethod
    def oak(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        trunk_h = ink.span(28, 44)
        radius = ink.span(26, 38)
        _Pen.fill(draw, x - 6, ground - trunk_h, 12, trunk_h + 4, biome.shade)
        _Pen.disc(
            draw, x, ground - trunk_h - radius + 14, radius, radius, biome.leaf
        )

    @staticmethod
    def spruce(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        height = ink.span(64, 98)
        half = ink.span(22, 32)
        draw.polygon(
            [
                (x, ground - height),
                (x - half, ground - 8),
                (x + half, ground - 8),
            ],
            fill=biome.leaf,
        )
        _Pen.fill(draw, x - 4, ground - 18, 8, 18, biome.shade)

    @staticmethod
    def cactus(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        body_h = ink.span(68, 100)
        body_w = 18
        left = x - body_w // 2
        top = ground - body_h
        _Pen.fill(draw, left, top, body_w, body_h, biome.leaf)
        arm_y = top + ink.span(16, 28)
        _Pen.fill(draw, left - 22, arm_y, 22, 12, biome.leaf)
        _Pen.fill(draw, left - 22, arm_y - 24, 12, 24, biome.leaf)
        if not ink.bit():
            return
        arm_y = top + ink.span(36, 52)
        _Pen.fill(draw, left + body_w, arm_y, 20, 12, biome.leaf)
        _Pen.fill(draw, left + body_w + 8, arm_y - 20, 12, 20, biome.leaf)

    @staticmethod
    def mushroom(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        stem_h = ink.span(18, 30)
        _Pen.fill(draw, x - 7, ground - stem_h, 14, stem_h, biome.light)
        cap_y = ground - stem_h + 4
        rx = ink.span(22, 32)
        _Pen.disc(draw, x, cap_y, rx, max(12, rx // 2), biome.accent)
        _Pen.disc(draw, x - rx // 3, cap_y - 2, 5, 4, biome.light)
        _Pen.disc(draw, x + rx // 3, cap_y - 1, 4, 3, biome.light)

    @staticmethod
    def flower(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        height = ink.span(34, 54)
        draw.line((x, ground, x, ground - height), fill=biome.leaf, width=5)
        radius = ink.span(12, 18)
        _Pen.disc(draw, x, ground - height, radius, radius, biome.accent)
        _Pen.disc(
            draw,
            x,
            ground - height,
            max(3, radius // 3),
            max(3, radius // 3),
            biome.light,
        )

    @staticmethod
    def blocks(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        side = ink.span(30, 44)
        outer, inner, third = _Pen.focal(biome, biome.ground)
        _Pen.cube(draw, x - side // 2, ground - side, side, outer, inner)
        _Pen.cube(
            draw,
            x - side // 5,
            ground - 2 * side + 3,
            side,
            third,
            biome.light,
        )

    @staticmethod
    def acacia(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        trunk_h = ink.span(32, 48)
        top_y = ground - trunk_h
        crown = x + ink.span(8, 20)
        _Pen.fill(draw, x - 4, top_y + 8, 8, trunk_h - 6, biome.shade)
        draw.polygon(
            [
                (crown - 52, top_y + 10),
                (crown + 24, top_y - 4),
                (crown + 42, top_y + 8),
                (crown - 38, top_y + 18),
            ],
            fill=biome.leaf,
        )

    @staticmethod
    def spike(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        tall = ink.span(72, 114)
        short = ink.span(40, 70)
        _Pen.fill(draw, x - 8, ground - tall, 16, tall, biome.leaf)
        _Pen.fill(draw, x + 14, ground - short, 12, short, biome.accent)

    @staticmethod
    def chorus(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        height = ink.span(36, 58)
        size = ink.span(18, 28)
        _Pen.fill(draw, x - 4, ground - height, 8, height, biome.leaf)
        _Pen.fill(
            draw,
            x - size,
            ground - height - size + 4,
            size,
            size,
            biome.accent,
        )
        _Pen.fill(
            draw, x + 4, ground - height - size - 8, size, size, biome.light
        )

    @staticmethod
    def mesa(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        width = ink.span(52, 80)
        height = ink.span(52, 84)
        band = ink.span(10, 16)
        _Pen.fill(
            draw,
            x - width // 2,
            ground - height,
            width,
            height + 4,
            biome.leaf,
        )
        _Pen.fill(
            draw,
            x - width // 2 - 8,
            ground - height + 16,
            width + 16,
            band,
            biome.accent,
        )

    @staticmethod
    def sail(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        height = ink.span(52, 76)
        width = ink.span(28, 42)
        draw.polygon(
            [
                (x, ground - height),
                (x, ground - 6),
                (x + width, ground - height // 2),
            ],
            fill=biome.light,
        )
        _Pen.fill(draw, x - 2, ground - height - 4, 4, height + 4, biome.shade)

    @staticmethod
    def fall(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        x: int,
        ground: int,
    ) -> None:
        width = ink.span(16, 28)
        _Pen.fill(draw, x - width // 2, 0, width, max(ground, 1), biome.leaf)

    @staticmethod
    def place(
        draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome, ground: int
    ) -> None:
        motif = biome.motifs[ink.pick(len(biome.motifs))]
        _Motif.ALL[motif](draw, ink, biome, ink.span(36, _SIDE - 36), ground)


class _Picture:
    """One abstract composition for the whole icon."""

    @staticmethod
    def horizon(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        horizon = ink.span(82, 112)
        tilt = ink.span(-14, 14)
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, biome.sky)
        draw.polygon(
            [
                (0, horizon),
                (_SIDE, horizon + tilt),
                (_SIDE, _SIDE),
                (0, _SIDE),
            ],
            fill=biome.ground,
        )
        crust = ink.span(16, 28)
        _Pen.fill(draw, 0, _SIDE - crust, _SIDE, crust, biome.shade)
        _Pen.sun(draw, ink, biome, -8, min(horizon, horizon + tilt) - 18)
        x = ink.span(40, _SIDE - 40)
        _Motif.ALL[biome.motifs[ink.pick(3)]](
            draw, ink, biome, x, horizon + tilt * x // _SIDE
        )

    @staticmethod
    def _cuts(ink: _Ink) -> tuple[int, int]:
        first = ink.span(42, 78)
        return first, ink.span(first + 34, 154)

    @staticmethod
    def mondrian(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        paper = max((biome.sky, biome.ground, biome.light), key=sum)
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, paper)
        xs = (0, *_Picture._cuts(ink), _SIDE)
        ys = (0, *_Picture._cuts(ink), _SIDE)
        _Picture._panes(draw, ink, biome, paper, xs, ys)
        _Picture._rules(draw, xs, ys)
        _Picture._medallion(draw, ink, biome, xs, ys)

    @staticmethod
    def _panes(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        paper: Rgb,
        xs: tuple[int, ...],
        ys: tuple[int, ...],
    ) -> None:
        choices = (
            biome.sky,
            biome.ground,
            biome.leaf,
            biome.accent,
            biome.shade,
        )
        for top, bottom in zip(ys, ys[1:], strict=False):
            for left, right in zip(xs, xs[1:], strict=False):
                _Picture._pane(
                    draw, ink, paper, choices, left, top, right, bottom
                )

    @staticmethod
    def _pane(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        paper: Rgb,
        choices: tuple[Rgb, ...],
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> None:
        if ink.u8() % 4 == 0:
            return
        color = choices[ink.pick(len(choices))]
        if color == paper:
            color = choices[-1]
        _Pen.fill(draw, left, top, right - left, bottom - top, color)

    @staticmethod
    def _rules(
        draw: ImageDraw.ImageDraw, xs: tuple[int, ...], ys: tuple[int, ...]
    ) -> None:
        for x in xs[1:-1]:
            _Pen.fill(draw, x - 3, 0, 7, _SIDE, _RULE)
        for y in ys[1:-1]:
            _Pen.fill(draw, 0, y - 3, _SIDE, 7, _RULE)

    @staticmethod
    def _medallion(
        draw: ImageDraw.ImageDraw,
        ink: _Ink,
        biome: _Biome,
        xs: tuple[int, ...],
        ys: tuple[int, ...],
    ) -> None:
        col = ink.pick(3)
        row = ink.pick(3)
        left, right = xs[col], xs[col + 1]
        top, bottom = ys[row], ys[row + 1]
        room = min(right - left, bottom - top)
        radius = min(24, max(12, room // 3))
        cx = (left + right) // 2
        cy = (top + bottom) // 2
        _Pen.disc(draw, cx, cy, radius, radius, biome.accent)
        _Pen.disc(
            draw, cx, cy, max(3, radius // 3), max(3, radius // 3), biome.light
        )

    @staticmethod
    def suprematist(
        draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome
    ) -> None:
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, biome.sky)
        outer, inner, bar = _Pen.focal(biome, biome.sky)
        side = ink.span(84, 112)
        on_left = ink.bit()
        x = (
            ink.span(-16, 28)
            if on_left
            else ink.span(_SIDE - side - 28, _SIDE - side + 16)
        )
        y = ink.span(_SIDE - side - 8, _SIDE - side + 20)
        _Pen.cube(draw, x, y, side, outer, inner)
        bar_y = y + side // 3 if ink.bit() else ink.span(18, 46)
        _Pen.fill(draw, 0, bar_y, _SIDE, ink.span(12, 18), bar)
        small = ink.span(18, 28)
        sx = _SIDE - small - 18 if on_left else 18
        _Pen.fill(draw, sx, ink.span(70, 120), small, small, outer)
        _Pen.disc(
            draw,
            sx + small // 2,
            ink.span(14, 36),
            12,
            12,
            _Pen.sun_color(biome),
        )

    @staticmethod
    def kandinsky(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, biome.sky)
        primary, secondary, tertiary = _Pen.focal(biome, biome.sky)
        _Pen.disc(
            draw,
            ink.span(-40, 60),
            ink.span(120, 230),
            ink.span(78, 104),
            ink.span(78, 104),
            primary,
        )
        spots = _Picture._orbits(ink, secondary, tertiary, primary)
        line = biome.light if sum(biome.sky) < 380 else biome.shade
        for start, end in zip(spots, spots[1:], strict=False):
            draw.line((*start[0], *end[0]), fill=line, width=4)
        for center, radius, color in spots:
            _Pen.disc(draw, center[0], center[1], radius, radius, color)
        _Picture._wedge(draw, ink, tertiary)
        _Pen.cube(
            draw,
            ink.span(16, _SIDE - 40),
            ink.span(16, _SIDE - 40),
            18,
            secondary,
            biome.light,
        )

    @staticmethod
    def _orbits(
        ink: _Ink, secondary: Rgb, tertiary: Rgb, primary: Rgb
    ) -> list[tuple[tuple[int, int], int, Rgb]]:
        spots = []
        for radius, color in (
            (ink.span(22, 34), secondary),
            (ink.span(12, 18), tertiary),
            (ink.span(16, 26), primary),
        ):
            spots.append(
                (
                    (ink.span(28, _SIDE - 28), ink.span(28, _SIDE - 28)),
                    radius,
                    color,
                )
            )
        return spots

    @staticmethod
    def _wedge(draw: ImageDraw.ImageDraw, ink: _Ink, color: Rgb) -> None:
        x = ink.span(16, 110)
        y = ink.span(16, 80)
        draw.polygon(
            [
                (x, y),
                (x + ink.span(30, 54), y + ink.span(6, 18)),
                (x + ink.span(4, 16), y + ink.span(34, 58)),
            ],
            fill=color,
        )

    @staticmethod
    def strata(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        colors = (
            biome.sky,
            biome.ground,
            biome.shade,
            biome.leaf,
            biome.accent,
            biome.light,
        )
        shift = ink.pick(len(colors))
        ordered = colors[shift:] + colors[:shift]
        y = 0
        for height, color in zip(_Picture._bands(ink), ordered, strict=True):
            _Pen.fill(draw, 0, y, _SIDE, height, color)
            y += height
        if ink.bit():
            _Picture._butte(draw, ink, biome)
            return
        _Pen.sun(draw, ink, biome, -10, 70)

    @staticmethod
    def _bands(ink: _Ink) -> list[int]:
        raw = [ink.span(18, 46) for _ in range(6)]
        total = sum(raw)
        heights = [_SIDE * item // total for item in raw[:-1]]
        heights.append(_SIDE - sum(heights))
        return heights

    @staticmethod
    def _butte(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        width = ink.span(48, 80)
        x = ink.span(16, _SIDE - width - 16)
        top = ink.span(28, 76)
        _Pen.fill(draw, x, top, width, _SIDE - top, biome.shade)
        span = _SIDE - top
        _Pen.fill(draw, x - 10, top + span // 3, width + 20, 14, biome.light)
        _Pen.fill(
            draw,
            x + 6,
            top + 2 * span // 3,
            max(width - 12, 8),
            12,
            biome.accent,
        )

    @staticmethod
    def arcs(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, biome.shade)
        anchors = (
            (0, 0),
            (_SIDE, 0),
            (0, _SIDE),
            (_SIDE, _SIDE),
            (_SIDE // 2, _SIDE // 2),
        )
        cx, cy = anchors[ink.pick(len(anchors))]
        colors = (
            biome.sky,
            biome.ground,
            biome.leaf,
            biome.accent,
            biome.light,
        )
        for radius, color in zip((128, 96, 68, 44, 22), colors, strict=True):
            _Pen.disc(draw, cx, cy, radius, radius, color)
        band = ink.span(12, 18)
        focal = _Pen.focal(biome, biome.light)[0]
        if ink.bit():
            _Pen.fill(draw, 0, ink.span(40, _SIDE - 60), _SIDE, band, focal)
        else:
            _Pen.fill(draw, ink.span(40, _SIDE - 60), 0, band, _SIDE, focal)
        _Pen.cube(
            draw,
            ink.span(76, 108),
            ink.span(76, 108),
            24,
            biome.shade,
            biome.light,
        )

    @staticmethod
    def peaks(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, biome.sky)
        back, mid, front = _Pen.focal(biome, biome.sky)
        _Picture._ridge(draw, ink, back, 124, 170)
        _Picture._ridge(draw, ink, mid, 96, 142)
        _Picture._ridge(draw, ink, front, 62, 112)
        _Pen.sun(draw, ink, biome, -6, 52)
        _Motif.place(draw, ink, biome, _SIDE)

    @staticmethod
    def _ridge(
        draw: ImageDraw.ImageDraw, ink: _Ink, color: Rgb, low: int, high: int
    ) -> None:
        height = ink.span(low, high)
        half = ink.span(60, 98)
        apex = ink.span(28, _SIDE - 28)
        draw.polygon(
            [
                (apex, _SIDE - height),
                (apex - half, _SIDE + 8),
                (apex + half, _SIDE + 8),
            ],
            fill=color,
        )

    @staticmethod
    def portal(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, biome.sky)
        frame = (
            biome.shade
            if _Pen.dist(biome.sky, biome.shade) >= 48
            else _Pen.focal(biome, biome.sky)[0]
        )
        margin = ink.span(34, 48)
        ox = ink.span(-6, 6)
        oy = ink.span(-6, 6)
        _Pen.fill(
            draw,
            margin + ox,
            margin + oy,
            _SIDE - 2 * margin,
            _SIDE - 2 * margin,
            frame,
        )
        inset = 18
        opening = _SIDE - 2 * margin - 2 * inset
        _Picture._stripes(
            draw, biome, margin + inset + ox, margin + inset + oy, opening
        )
        corners = (
            (28, 28),
            (_SIDE - 28, 28),
            (28, _SIDE - 28),
            (_SIDE - 28, _SIDE - 28),
        )
        moon_x, moon_y = corners[ink.pick(len(corners))]
        _Pen.disc(draw, moon_x, moon_y, 20, 20, _Pen.sun_color(biome))

    @staticmethod
    def _stripes(
        draw: ImageDraw.ImageDraw,
        biome: _Biome,
        left: int,
        top: int,
        opening: int,
    ) -> None:
        stripe_a, stripe_b = biome.leaf, biome.accent
        count = 5
        stripe = opening // count
        colors = (stripe_a, stripe_b)
        for index in range(count):
            width = (
                opening - stripe * (count - 1)
                if index == count - 1
                else stripe
            )
            _Pen.fill(
                draw,
                left + index * stripe,
                top,
                width,
                opening,
                colors[index % 2],
            )

    @staticmethod
    def quilt(draw: ImageDraw.ImageDraw, ink: _Ink, biome: _Biome) -> None:
        grout, left, right = _Pen.banner_colors(biome)
        _Pen.fill(draw, 0, 0, _SIDE, _SIDE, grout)
        _Picture._banner(draw, ink, left, right)
        side = ink.span(36, 50)
        outer, inner = _Pen.stamp_colors(biome, left, right)
        _Pen.cube(
            draw,
            (_SIDE - side) // 2 + ink.span(-12, 12),
            (_SIDE - side) // 2 + ink.span(-12, 12),
            side,
            outer,
            inner,
        )

    @staticmethod
    def _banner(
        draw: ImageDraw.ImageDraw, ink: _Ink, left: Rgb, right: Rgb
    ) -> None:
        rows = 3
        cols = 3
        gap = 10
        row_h = (_SIDE - gap * (rows + 1)) // rows
        brick_w = (_SIDE - gap * (cols + 1)) // cols
        shift = (brick_w + gap) // 2 if ink.bit() else 0
        for row in range(rows):
            y = gap + row * (row_h + gap)
            offset = shift if row % 2 else 0
            for col in range(cols + 1):
                x = gap + col * (brick_w + gap) - offset
                color = left if (row + col) % 2 == 0 else right
                _Pen.fill(draw, x, y, brick_w, row_h, color)


_Motif.ALL = (
    _Motif.oak,
    _Motif.spruce,
    _Motif.cactus,
    _Motif.mushroom,
    _Motif.flower,
    _Motif.blocks,
    _Motif.acacia,
    _Motif.spike,
    _Motif.chorus,
    _Motif.mesa,
    _Motif.sail,
    _Motif.fall,
)

_Picture.ALL = (
    _Picture.horizon,
    _Picture.mondrian,
    _Picture.suprematist,
    _Picture.kandinsky,
    _Picture.strata,
    _Picture.arcs,
    _Picture.peaks,
    _Picture.portal,
    _Picture.quilt,
)
