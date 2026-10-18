import colorsys
import hashlib
from io import BytesIO

from PIL import Image, ImageDraw, UnidentifiedImageError

from app.configs.errors import ValidationError

Rgb = tuple[int, int, int]


class IconImage:
    """192x192 PNG. The same seed always draws the same bytes."""

    SIDE = 192
    MAX_BYTES = 128 * 1024
    _SIGNATURE = b"\x89PNG\r\n\x1a\n"
    _GRID = 6
    _CELL = SIDE // _GRID
    _CENTER = SIDE // 2
    # Integer points only, so two hosts fill the same pixels.
    _CORNERS = (
        (0, 0),
        (_CENTER, 0),
        (SIDE - 1, 0),
        (SIDE - 1, _CENTER),
        (SIDE - 1, SIDE - 1),
        (_CENTER, SIDE - 1),
        (0, SIDE - 1),
        (0, _CENTER),
    )
    _ORBIT = (
        (96, 28),
        (148, 48),
        (164, 96),
        (148, 144),
        (96, 164),
        (44, 144),
        (28, 96),
        (44, 48),
    )

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
        background, colors = cls._palette(digest)
        image = Image.new("RGB", (cls.SIDE, cls.SIDE), background)
        draw = ImageDraw.Draw(image)
        (
            cls._draw_mosaic,
            cls._draw_rings,
            cls._draw_shards,
            cls._draw_bands,
        )[digest[3] % 4](draw, digest, colors)
        buffer = BytesIO()
        image.save(buffer, format="PNG", compress_level=9)
        return buffer.getvalue()

    @classmethod
    def _rgb(cls, hue: float, light: float, saturation: float) -> Rgb:
        red, green, blue = colorsys.hls_to_rgb(hue % 1, light, saturation)
        return (round(red * 255), round(green * 255), round(blue * 255))

    @classmethod
    def _palette(cls, digest: bytes) -> tuple[Rgb, tuple[Rgb, Rgb, Rgb]]:
        hue = int.from_bytes(digest[0:2], "big") / 65535
        dark = bool(digest[2] & 1)
        background = cls._rgb(
            hue, 0.16 if dark else 0.94, 0.45 if dark else 0.28
        )
        lights = (0.62, 0.74, 0.50) if dark else (0.38, 0.46, 0.32)
        saturations = (0.75, 0.68, 0.70) if dark else (0.78, 0.72, 0.66)
        colors = tuple(
            cls._rgb(hue + shift, light, saturation)
            for shift, light, saturation in zip(
                (0.0, 0.31, 0.62), lights, saturations, strict=True
            )
        )
        return background, colors

    @classmethod
    def _cell(
        cls, col: int, row: int, pad: int = 0
    ) -> tuple[int, int, int, int]:
        return (
            col * cls._CELL + pad,
            row * cls._CELL + pad,
            (col + 1) * cls._CELL - 1 - pad,
            (row + 1) * cls._CELL - 1 - pad,
        )

    @classmethod
    def _shape(
        cls,
        draw: ImageDraw.ImageDraw,
        col: int,
        row: int,
        kind: int,
        color: Rgb,
    ) -> None:
        box = cls._cell(col, row)
        left, top, right, bottom = box
        mid_x = (left + right) // 2
        mid_y = (top + bottom) // 2
        match kind:
            case 1:
                draw.rectangle(box, fill=color)
            case 2:
                draw.ellipse(box, fill=color)
            case 3:
                draw.polygon(
                    [
                        (mid_x, top),
                        (right, mid_y),
                        (mid_x, bottom),
                        (left, mid_y),
                    ],
                    fill=color,
                )
            case 4:
                draw.polygon(
                    [(left, bottom), (mid_x, top), (right, bottom)],
                    fill=color,
                )
            case 5:
                draw.polygon(
                    [(left, top), (right, top), (mid_x, bottom)], fill=color
                )
            case 6:
                draw.rectangle(cls._cell(col, row, cls._CELL // 5), fill=color)
            case _:
                draw.ellipse(box, outline=color, width=6)

    @classmethod
    def _paint_pair(
        cls,
        draw: ImageDraw.ImageDraw,
        row: int,
        col: int,
        mirror_row: int,
        mirror_col: int,
        kind: int,
        color: Rgb,
    ) -> None:
        cls._shape(draw, col, row, kind, color)
        cls._shape(draw, mirror_col, mirror_row, kind, color)

    @classmethod
    def _draw_mosaic(
        cls,
        draw: ImageDraw.ImageDraw,
        digest: bytes,
        colors: tuple[Rgb, Rgb, Rgb],
    ) -> None:
        vertical = bool(digest[22] & 1)
        for major in range(3):
            for minor in range(cls._GRID):
                byte = digest[4 + major * cls._GRID + minor]
                kind = byte & 7
                if kind == 0:
                    continue
                color = colors[(byte >> 3) % 3]
                if vertical:
                    cls._paint_pair(
                        draw,
                        major,
                        minor,
                        cls._GRID - 1 - major,
                        minor,
                        kind,
                        color,
                    )
                else:
                    cls._paint_pair(
                        draw,
                        minor,
                        major,
                        minor,
                        cls._GRID - 1 - major,
                        kind,
                        color,
                    )

    @classmethod
    def _draw_rings(
        cls,
        draw: ImageDraw.ImageDraw,
        digest: bytes,
        colors: tuple[Rgb, Rgb, Rgb],
    ) -> None:
        center = cls._CENTER
        draw.ellipse((56, 56, 136, 136), fill=colors[digest[9] % 3])
        for index in range(5):
            byte = digest[4 + index]
            radius = 18 + (byte % 76)
            draw.ellipse(
                (
                    center - radius,
                    center - radius,
                    center + radius,
                    center + radius,
                ),
                outline=colors[index % 3],
                width=4 + (byte % 8),
            )
        for index, point in enumerate(cls._ORBIT):
            if (digest[10] & (1 << index)) == 0:
                continue
            radius = 8 + digest[11 + index] % 10
            point_x, point_y = point
            draw.ellipse(
                (
                    point_x - radius,
                    point_y - radius,
                    point_x + radius,
                    point_y + radius,
                ),
                fill=colors[index % 3],
            )

    @classmethod
    def _draw_shards(
        cls,
        draw: ImageDraw.ImageDraw,
        digest: bytes,
        colors: tuple[Rgb, Rgb, Rgb],
    ) -> None:
        center = (cls._CENTER, cls._CENTER)
        for index, point in enumerate(cls._CORNERS):
            draw.polygon(
                [center, point, cls._CORNERS[(index + 1) % len(cls._CORNERS)]],
                fill=colors[digest[4 + index] % 3],
            )
        inset = 28 + digest[12] % 24
        draw.rectangle(
            (inset, inset, cls.SIDE - 1 - inset, cls.SIDE - 1 - inset),
            fill=colors[digest[13] % 3],
        )

    @classmethod
    def _draw_bands(
        cls,
        draw: ImageDraw.ImageDraw,
        digest: bytes,
        colors: tuple[Rgb, Rgb, Rgb],
    ) -> None:
        vertical = bool(digest[4] & 1)
        cursor = 0
        index = 0
        while cursor < cls.SIDE:
            thickness = 8 + digest[5 + (index % 24)] % 24
            end = min(cls.SIDE - 1, cursor + thickness)
            color = colors[digest[6 + (index % 24)] % 3]
            if vertical:
                draw.rectangle((cursor, 0, end, cls.SIDE - 1), fill=color)
            else:
                draw.rectangle((0, cursor, cls.SIDE - 1, end), fill=color)
            if end == cls.SIDE - 1:
                break
            cursor = end + 1
            index += 1
        side = 40 + digest[30] % 48
        origin = (cls.SIDE - side) // 2
        draw.ellipse(
            (origin, origin, origin + side - 1, origin + side - 1),
            fill=colors[digest[31] % 3],
        )
