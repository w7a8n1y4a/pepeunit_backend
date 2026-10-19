import hashlib
import math
from collections.abc import Callable
from io import BytesIO
from typing import NamedTuple

from PIL import Image, ImageChops, ImageDraw, UnidentifiedImageError

from app.configs.errors import ValidationError

Rgb = tuple[int, int, int]
_SIDE = 192
_MASK64 = (1 << 64) - 1
# Literals, not math.pi: every instance reduces angles the same way.
_PI = 3.141592653589793
_HALF_PI = 1.5707963267948966
_TAU = 6.283185307179586
_REACH = 0.66

# Material 500, in color-wheel order. Field colors are neighbors on this
# wheel; the sign is the color farthest from that group.
_PALETTE: tuple[Rgb, ...] = (
    (244, 67, 54),
    (233, 30, 99),
    (156, 39, 176),
    (103, 58, 183),
    (63, 81, 181),
    (33, 150, 243),
    (3, 169, 244),
    (0, 188, 212),
    (0, 150, 136),
    (76, 175, 80),
    (139, 195, 74),
    (205, 220, 57),
    (255, 235, 59),
    (255, 193, 7),
    (255, 152, 0),
    (255, 87, 34),
)

_SEAL = 0
_FRAME = 1
_STAR = 2
_KOCH = 3
_GASKET = 4
_RADIAL = 5
_KINDS = 6

_GRADS = (
    (1.0, 1.0),
    (-1.0, 1.0),
    (1.0, -1.0),
    (-1.0, -1.0),
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
)


class IconImage:
    """192x192 PNG. The same seed always draws the same bytes.

    Background is Perlin noise at several scales, each in its own
    Material color. A parametric fractal is painted on top as a seal,
    a frame closing on the center, or another abstract sign.
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
        noise = _Noise(ink)
        field = _build_field(ink)
        image = Image.new("RGB", (cls.SIDE, cls.SIDE), field.base)
        _paint_field(image, noise, field)
        _paint_mark(image, ink, field.colors)
        buffer = BytesIO()
        image.save(buffer, format="PNG", compress_level=9)
        return buffer.getvalue()


class _Ink:
    """Integer stream. The same digest always yields the same numbers."""

    def __init__(self, digest: bytes) -> None:
        state = 0
        for byte in digest:
            state = (state * 131 + byte) & _MASK64
        self._state = state or 1

    def _step(self) -> int:
        self._state = (
            self._state * 6364136223846793005 + 1442695040888963407
        ) & _MASK64
        return self._state

    def u8(self) -> int:
        return (self._step() >> 33) & 255

    def below(self, limit: int) -> int:
        if limit <= 1:
            return 0
        return (self._step() >> 17) % limit

    def span(self, low: int, high: int) -> int:
        return low + self.below(high - low + 1)

    def bit(self) -> bool:
        return bool(self.u8() & 1)


class _Noise:
    """2D Perlin. Only + and *, so two hosts sample the same field."""

    def __init__(self, ink: _Ink) -> None:
        perm = list(range(256))
        for index in range(255, 0, -1):
            swap = ink.below(index + 1)
            perm[index], perm[swap] = perm[swap], perm[index]
        self._p = [*perm, *perm]

    def at(self, x: float, y: float) -> float:
        x0 = math.floor(x)
        y0 = math.floor(y)
        xf = x - x0
        yf = y - y0
        xi = int(x0) & 255
        yi = int(y0) & 255
        u = _fade(xf)
        v = _fade(yf)
        p = self._p
        aa = p[p[xi] + yi]
        ab = p[p[xi] + yi + 1]
        ba = p[p[xi + 1] + yi]
        bb = p[p[xi + 1] + yi + 1]
        top = _lerp(_grad(aa, xf, yf), _grad(ba, xf - 1.0, yf), u)
        bot = _lerp(
            _grad(ab, xf, yf - 1.0),
            _grad(bb, xf - 1.0, yf - 1.0),
            u,
        )
        return _lerp(top, bot, v)


class _Octave(NamedTuple):
    color: Rgb
    freq: float
    ox: float
    oy: float
    lo: float
    hi: float
    gain: float


class _Field(NamedTuple):
    base: Rgb
    octaves: tuple[_Octave, ...]
    colors: tuple[Rgb, ...]


class _Place(NamedTuple):
    cx: float
    cy: float
    radius: float
    angle: float


class _Form(NamedTuple):
    kind: int
    sides: int
    count: int
    band: float
    gap: float
    aspect: float
    twist: float
    ticks: int
    tall: bool
    points: int
    inner: float
    depth: int
    bulge: float
    arms: int
    end_sides: int
    hollow: bool


def _fade(t: float) -> float:
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _lerp(a: float, b: float, t: float) -> float:
    return a + t * (b - a)


def _grad(h: int, x: float, y: float) -> float:
    gx, gy = _GRADS[h & 7]
    return gx * x + gy * y


def _sin(angle: float) -> float:
    x = angle - math.floor(angle / _TAU + 0.5) * _TAU
    if x > _HALF_PI:
        x = _PI - x
    elif x < -_HALF_PI:
        x = -_PI - x
    x2 = x * x
    return x * (
        1.0
        + x2
        * (
            -1.0 / 6.0
            + x2
            * (
                1.0 / 120.0
                + x2
                * (
                    -1.0 / 5040.0
                    + x2
                    * (
                        1.0 / 362880.0
                        + x2 * (-1.0 / 39916800.0 + x2 * (1.0 / 6227020800.0))
                    )
                )
            )
        )
    )


def _cos(angle: float) -> float:
    return _sin(angle + _HALF_PI)


def _rint(value: float) -> int:
    if value >= 0.0:
        return math.floor(value + 0.5)
    return -math.floor(-value + 0.5)


def _byte(value: float) -> int:
    rounded = _rint(value)
    if rounded < 0:
        return 0
    if rounded > 255:
        return 255
    return rounded


def _smooth(edge0: float, edge1: float, value: float) -> float:
    span = edge1 - edge0
    if span <= 0.0:
        return 1.0 if value >= edge0 else 0.0
    t = (value - edge0) / span
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def _luma(color: Rgb) -> int:
    return (color[0] * 3 + color[1] * 6 + color[2]) // 10


def _apart(left: Rgb, right: Rgb) -> int:
    return (
        abs(left[0] - right[0])
        + abs(left[1] - right[1])
        + abs(left[2] - right[2])
        + abs(_luma(left) - _luma(right))
    )


def _farthest(blocked: tuple[Rgb, ...]) -> Rgb:
    best = _PALETTE[0]
    score = -1
    for color in _PALETTE:
        dist = min(_apart(color, other) for other in blocked)
        if dist > score:
            best = color
            score = dist
    return best


def _turns(ink: _Ink) -> float:
    return ink.span(0, 359) * _TAU / 360.0


def _build_field(ink: _Ink) -> _Field:
    start = ink.below(len(_PALETTE))
    step = 1 if ink.bit() else 2
    colors = tuple(
        _PALETTE[(start + index * step) % len(_PALETTE)] for index in range(4)
    )
    coarse = ink.span(11, 20) / 1000.0
    return _Field(colors[0], _octaves(ink, colors, coarse), colors)


def _octaves(
    ink: _Ink, colors: tuple[Rgb, ...], coarse: float
) -> tuple[_Octave, ...]:
    mid = coarse * ink.span(24, 38) / 10.0
    fine = coarse * ink.span(52, 84) / 10.0
    return (
        _octave(ink, colors[1], coarse, 0.22, 0.58, 1.0),
        _octave(ink, colors[2], mid, 0.46, 0.70, 1.0),
        _octave(ink, colors[3], fine, 0.58, 0.78, ink.span(40, 64) / 100.0),
    )


def _octave(
    ink: _Ink,
    color: Rgb,
    freq: float,
    lo: float,
    hi: float,
    gain: float,
) -> _Octave:
    shift = ink.span(-5, 5) / 100.0
    return _Octave(
        color,
        freq,
        ink.span(0, 5000) / 10.0,
        ink.span(0, 5000) / 10.0,
        lo + shift,
        hi + shift,
        gain,
    )


def _paint_field(image: Image.Image, noise: _Noise, field: _Field) -> None:
    # Sampled on a 2px lattice. Midpoints are integer averages, so the
    # smooth field is the same on every host and cheap to expand.
    image.frombytes(_field_bytes(noise, field))


def _field_bytes(noise: _Noise, field: _Field) -> bytes:
    cells = _SIDE // 2 + 1
    samples = _lattice(noise, field, cells)
    return bytes(_expand(samples, cells))


def _lattice(noise: _Noise, field: _Field, cells: int) -> list[Rgb]:
    samples: list[Rgb] = []
    push = samples.append
    at = noise.at
    octaves = field.octaves
    base = field.base
    for gy in range(cells):
        py = float(gy * 2)
        for gx in range(cells):
            push(_mix(at, octaves, base, float(gx * 2), py))
    return samples


def _mix(
    at: Callable[[float, float], float],
    octaves: tuple[_Octave, ...],
    base: Rgb,
    x: float,
    y: float,
) -> Rgb:
    red, green, blue = float(base[0]), float(base[1]), float(base[2])
    for octave in octaves:
        weight = _amp(at, octave, x, y)
        red += (octave.color[0] - red) * weight
        green += (octave.color[1] - green) * weight
        blue += (octave.color[2] - blue) * weight
    return _byte(red), _byte(green), _byte(blue)


def _amp(
    at: Callable[[float, float], float],
    octave: _Octave,
    x: float,
    y: float,
) -> float:
    unit = (
        at(x * octave.freq + octave.ox, y * octave.freq + octave.oy) + 0.65
    ) / 1.3
    if unit < 0.0:
        unit = 0.0
    elif unit > 1.0:
        unit = 1.0
    return _smooth(octave.lo, octave.hi, unit) * octave.gain


def _expand(samples: list[Rgb], cells: int) -> bytearray:
    span = _SIDE * 3
    raw = bytearray(span * _SIDE)
    tiles = cells - 1
    for gy in range(tiles):
        even, odd = _expand_row(samples, cells, gy)
        start = gy * 2 * span
        raw[start : start + span] = even
        raw[start + span : start + 2 * span] = odd
    return raw


def _expand_row(
    samples: list[Rgb], cells: int, gy: int
) -> tuple[bytearray, bytearray]:
    span = _SIDE * 3
    even = bytearray(span)
    odd = bytearray(span)
    row0 = gy * cells
    row1 = row0 + cells
    cursor = 0
    for gx in range(cells - 1):
        c00 = samples[row0 + gx]
        c10 = samples[row0 + gx + 1]
        c01 = samples[row1 + gx]
        c11 = samples[row1 + gx + 1]
        _store(even, cursor, c00)
        _store(even, cursor + 3, _avg(c00, c10))
        left = _avg(c00, c01)
        _store(odd, cursor, left)
        _store(odd, cursor + 3, _avg(left, _avg(c10, c11)))
        cursor += 6
    return even, odd


def _store(buf: bytearray, cursor: int, color: Rgb) -> None:
    buf[cursor] = color[0]
    buf[cursor + 1] = color[1]
    buf[cursor + 2] = color[2]


def _avg(left: Rgb, right: Rgb) -> Rgb:
    return (
        (left[0] + right[0]) // 2,
        (left[1] + right[1]) // 2,
        (left[2] + right[2]) // 2,
    )


def _mask() -> Image.Image:
    return Image.new("L", (_SIDE, _SIDE), 0)


def _paint_mark(
    image: Image.Image, ink: _Ink, colors: tuple[Rgb, ...]
) -> None:
    place = _place(ink)
    outer = _spec(ink, ink.below(_KINDS), place.radius)
    front = _draw(
        _mask(), place.cx, place.cy, place.radius, place.angle, outer
    )
    back = _inset(ink, place, outer)
    primary = _farthest(colors)
    _blit(image, front, primary, back, _farthest((*colors, primary)))


def _place(ink: _Ink) -> _Place:
    angle = _turns(ink)
    roll = ink.u8()
    if roll < 150:
        return _emblem(ink, angle)
    if roll < 215:
        return _Place(_SIDE / 2, _SIDE / 2, float(ink.span(92, 112)), angle)
    return _corner(ink, angle)


def _corner(ink: _Ink, angle: float) -> _Place:
    """A whole sign sitting in part of the field, noise around it."""
    radius = float(ink.span(48, 68))
    margin = int(radius) + 6
    return _Place(
        float(ink.span(margin, _SIDE - margin)),
        float(ink.span(margin, _SIDE - margin)),
        radius,
        angle,
    )


def _emblem(ink: _Ink, angle: float) -> _Place:
    radius = float(ink.span(64, 84))
    slack = min(16, int(90 - radius))
    return _Place(
        _SIDE / 2 + ink.span(-slack, slack),
        _SIDE / 2 + ink.span(-slack, slack),
        radius,
        angle,
    )


def _inset(ink: _Ink, place: _Place, outer: _Form) -> Image.Image:
    hole = _opening(outer, place.radius)
    if hole < 18.0:
        return _mask()
    inner = _spec(ink, ink.below(_KINDS), hole)
    return _draw(
        _mask(),
        place.cx,
        place.cy,
        hole,
        place.angle + _turns(ink),
        inner,
    )


def _blit(
    image: Image.Image,
    front: Image.Image,
    primary: Rgb,
    back: Image.Image,
    secondary: Rgb,
) -> None:
    image.paste(Image.new("RGB", (_SIDE, _SIDE), primary), mask=front)
    image.paste(Image.new("RGB", (_SIDE, _SIDE), secondary), mask=back)


def _form(
    kind: int,
    sides: int = 4,
    count: int = 1,
    band: float = 0.16,
    gap: float = 0.1,
    aspect: float = 1.0,
    twist: float = 0.0,
    ticks: int = 0,
    tall: bool = False,
    points: int = 5,
    inner: float = 0.4,
    depth: int = 1,
    bulge: float = 0.86,
    arms: int = 5,
    end_sides: int = 4,
    hollow: bool = False,
) -> _Form:
    return _Form(
        kind,
        sides,
        count,
        band,
        gap,
        aspect,
        twist,
        ticks,
        tall,
        points,
        inner,
        depth,
        bulge,
        arms,
        end_sides,
        hollow,
    )


def _spec(ink: _Ink, kind: int, radius: float) -> _Form:
    if kind == _SEAL:
        return _seal_spec(ink)
    if kind == _FRAME:
        return _frame_spec(ink)
    if kind == _STAR:
        return _star_spec(ink)
    if kind == _KOCH:
        return _koch_spec(ink, radius)
    if kind == _GASKET:
        return _gasket_spec(ink, radius)
    return _radial_spec(ink, radius)


def _seal_spec(ink: _Ink) -> _Form:
    sides = ink.span(12, 18) if ink.u8() < 120 else ink.span(5, 8)
    ticks = ink.span(5, 9) * 2 if ink.bit() else 0
    return _form(
        _SEAL,
        sides=sides,
        count=ink.span(2, 3),
        band=ink.span(15, 24) / 100.0,
        gap=ink.span(7, 13) / 100.0,
        aspect=ink.span(100, 124) / 100.0,
        twist=ink.span(0, 22) * _TAU / 360.0,
        ticks=ticks,
        tall=ink.bit(),
    )


def _frame_spec(ink: _Ink) -> _Form:
    roll = ink.u8()
    if roll < 150:
        sides = 4
    elif roll < 210:
        sides = 3
    else:
        sides = ink.span(5, 6)
    twist = 0.0 if ink.u8() < 110 else ink.span(7, 16) * _TAU / 360.0
    return _form(
        _FRAME,
        sides=sides,
        count=ink.span(4, 6),
        band=ink.span(12, 18) / 100.0,
        gap=ink.span(6, 11) / 100.0,
        aspect=ink.span(108, 150) / 100.0,
        twist=twist,
        tall=ink.bit(),
    )


def _star_spec(ink: _Ink) -> _Form:
    return _form(
        _STAR,
        points=ink.span(4, 8),
        inner=ink.span(32, 46) / 100.0,
        hollow=ink.u8() < 80,
    )


def _koch_spec(ink: _Ink, radius: float) -> _Form:
    bulge = ink.span(-100, 120) / 100.0
    if -0.4 < bulge < 0.4:
        bulge = 0.86 if bulge >= 0.0 else -0.72
    if radius < 40.0:
        depth = 1
    elif radius < 96.0:
        depth = 2
    else:
        depth = ink.span(2, 3)
    return _form(
        _KOCH,
        sides=ink.span(3, 6),
        depth=depth,
        bulge=bulge,
        hollow=bulge > 0.0 and ink.u8() < 70,
        aspect=ink.span(100, 118) / 100.0,
        tall=ink.bit(),
    )


def _gasket_spec(ink: _Ink, radius: float) -> _Form:
    if radius < 42.0 or not ink.bit():
        depth = 1
    elif radius > 90.0 and ink.bit():
        depth = 3
    else:
        depth = 2
    return _form(
        _GASKET,
        sides=ink.span(3, 5),
        depth=depth,
        twist=ink.span(0, 18) * _TAU / 360.0,
        hollow=ink.bit(),
    )


def _radial_spec(ink: _Ink, radius: float) -> _Form:
    arms = ink.span(3, 6)
    depth = 2 if radius > 100.0 and arms <= 4 and ink.bit() else 1
    return _form(
        _RADIAL,
        arms=arms,
        end_sides=ink.span(3, 6),
        depth=depth,
        twist=ink.span(-18, 18) * _TAU / 360.0,
        band=ink.span(7, 12) / 100.0,
    )


def _draw(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
) -> Image.Image:
    if form.kind in {_SEAL, _FRAME}:
        return _draw_concentric(mask, cx, cy, radius, angle, form)
    if form.kind == _STAR:
        return _draw_star(mask, cx, cy, radius, angle, form)
    if form.kind == _KOCH:
        return _draw_koch(mask, cx, cy, radius, angle, form)
    if form.kind == _GASKET:
        return _gasket_at(mask, cx, cy, radius, angle, form, form.depth)
    return _radial_node(mask, cx, cy, radius, angle, form, form.depth, True)


def _opening(form: _Form, radius: float) -> float:
    if form.kind in {_SEAL, _FRAME}:
        return _concentric_hole(form, radius) / form.aspect * 0.84
    if form.kind == _STAR:
        return radius * form.inner * 0.78
    if form.kind == _KOCH:
        scale = 0.50 if form.hollow else 0.44
        return radius * scale
    if form.kind == _GASKET:
        return radius * 0.22
    return radius * 0.26


def _band_shrink(form: _Form, radius: float) -> tuple[float, float]:
    band = form.band
    floor = 5.5 / radius if radius > 0.0 else band
    band = min(max(band, floor), 0.4)
    shrink = max(1.0 - band - form.gap, 0.5)
    return band, shrink


def _concentric_hole(form: _Form, radius: float) -> float:
    band, shrink = _band_shrink(form, radius)
    ring = radius
    hole = ring * (1.0 - band)
    for _ in range(form.count):
        if ring < 12.0:
            break
        hole = ring * (1.0 - band)
        ring *= shrink
    return hole


def _draw_concentric(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
) -> Image.Image:
    band, shrink = _band_shrink(form, radius)
    ring = radius
    for index in range(form.count):
        if ring < 12.0:
            break
        ang = angle + form.twist * index
        mask = _cut(
            mask,
            _ngon(cx, cy, ring, form, ang),
            _ngon(cx, cy, ring * (1.0 - band), form, ang),
        )
        ring *= shrink
    if form.ticks:
        mask = _ticks(mask, cx, cy, radius, angle, form.ticks)
    return mask


def _draw_star(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
) -> Image.Image:
    outer = _star(cx, cy, radius, angle, form.points, form.inner)
    if not form.hollow:
        return _fill(mask, outer)
    inner = _star(cx, cy, radius * 0.62, angle, form.points, form.inner)
    return _cut(mask, outer, inner)


def _draw_koch(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
) -> Image.Image:
    rx, ry = _axes(radius, form.aspect, form.tall)
    outer = _koch(cx, cy, rx, ry, angle, form.sides, form.depth, form.bulge)
    if not form.hollow:
        return _fill(mask, outer)
    inner = _koch(
        cx,
        cy,
        rx * 0.58,
        ry * 0.58,
        angle,
        form.sides,
        form.depth,
        form.bulge,
    )
    return _cut(mask, outer, inner)


def _gasket_at(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
    level: int,
) -> Image.Image:
    if level <= 0 or radius < 8.0:
        return _gasket_leaf(mask, cx, cy, radius, angle, form)
    step = _TAU / form.sides
    for index in range(form.sides):
        arm = angle + step * index
        mask = _gasket_at(
            mask,
            cx + _cos(arm) * radius * 0.5,
            cy + _sin(arm) * radius * 0.5,
            radius * 0.5,
            angle + form.twist,
            form,
            level - 1,
        )
    return mask


def _gasket_leaf(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
) -> Image.Image:
    outer = _ngon_r(cx, cy, radius, angle, form.sides)
    if form.hollow and radius >= 12.0:
        inner = _ngon_r(cx, cy, radius * 0.52, angle, form.sides)
        return _cut(mask, outer, inner)
    return _fill(mask, outer)


def _radial_node(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
    level: int,
    root: bool,
) -> Image.Image:
    if not root:
        mask = _fill(
            mask,
            _ngon_r(
                cx,
                cy,
                max(6.0, radius * 0.34),
                angle,
                form.end_sides,
            ),
        )
    if root:
        mask = _spokes(mask, cx, cy, radius, angle, form)
    if level <= 0 or radius < 22.0:
        return mask
    return _radial_arms(mask, cx, cy, radius, angle, form, level)


def _spokes(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
) -> Image.Image:
    width = max(4.0, radius * form.band)
    step = _TAU / form.arms
    for index in range(form.arms):
        mask = _fill(
            mask,
            _bar(
                cx,
                cy,
                angle + step * index,
                radius * 0.30,
                radius * _REACH,
                width,
            ),
        )
    return mask


def _radial_arms(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    form: _Form,
    level: int,
) -> Image.Image:
    step = _TAU / form.arms
    dist = radius * _REACH
    child = radius * 0.42
    for index in range(form.arms):
        arm = angle + step * index + form.twist
        mask = _radial_node(
            mask,
            cx + _cos(arm) * dist,
            cy + _sin(arm) * dist,
            child,
            arm,
            form,
            level - 1,
            False,
        )
    return mask


def _axes(radius: float, aspect: float, tall: bool) -> tuple[float, float]:
    minor = radius / aspect
    if tall:
        return minor, radius
    return radius, minor


def _vertices(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    angle: float,
    sides: int,
) -> list[tuple[float, float]]:
    step = _TAU / sides
    return [
        (cx + rx * _cos(angle + step * i), cy + ry * _sin(angle + step * i))
        for i in range(sides)
    ]


def _ngon(
    cx: float, cy: float, radius: float, form: _Form, angle: float
) -> list[tuple[int, int]]:
    rx, ry = _axes(radius, form.aspect, form.tall)
    return _ints(_vertices(cx, cy, rx, ry, angle, form.sides))


def _ngon_r(
    cx: float, cy: float, radius: float, angle: float, sides: int
) -> list[tuple[int, int]]:
    return _ints(_vertices(cx, cy, radius, radius, angle, sides))


def _star(
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    points: int,
    inner: float,
) -> list[tuple[int, int]]:
    step = _PI / points
    pts: list[tuple[int, int]] = []
    for index in range(points * 2):
        reach = radius if index % 2 == 0 else radius * inner
        arm = angle + step * index
        pts.append(
            (_rint(cx + reach * _cos(arm)), _rint(cy + reach * _sin(arm)))
        )
    return pts


def _koch(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    angle: float,
    sides: int,
    depth: int,
    bulge: float,
) -> list[tuple[int, int]]:
    raw = _vertices(cx, cy, rx, ry, angle, sides)
    acc: list[tuple[float, float]] = []
    count = len(raw)
    for index in range(count):
        ax, ay = raw[index]
        bx, by = raw[(index + 1) % count]
        acc.extend(_koch_edge(ax, ay, bx, by, depth, bulge))
    return _ints(acc)


def _koch_edge(
    ax: float, ay: float, bx: float, by: float, depth: int, bulge: float
) -> list[tuple[float, float]]:
    if depth <= 0:
        return [(ax, ay)]
    dx = bx - ax
    dy = by - ay
    p1 = (ax + dx / 3.0, ay + dy / 3.0)
    p2 = (ax + 2.0 * dx / 3.0, ay + 2.0 * dy / 3.0)
    peak = (
        (p1[0] + p2[0]) / 2.0 + (-dy) * bulge / 3.0,
        (p1[1] + p2[1]) / 2.0 + dx * bulge / 3.0,
    )
    return [
        *_koch_edge(ax, ay, p1[0], p1[1], depth - 1, bulge),
        *_koch_edge(p1[0], p1[1], peak[0], peak[1], depth - 1, bulge),
        *_koch_edge(peak[0], peak[1], p2[0], p2[1], depth - 1, bulge),
        *_koch_edge(p2[0], p2[1], bx, by, depth - 1, bulge),
    ]


def _bar(
    cx: float,
    cy: float,
    angle: float,
    r0: float,
    r1: float,
    width: float,
) -> list[tuple[int, int]]:
    c = _cos(angle)
    s = _sin(angle)
    nx = -s * width / 2.0
    ny = c * width / 2.0
    x0 = cx + c * r0
    y0 = cy + s * r0
    x1 = cx + c * r1
    y1 = cy + s * r1
    return [
        (_rint(x0 + nx), _rint(y0 + ny)),
        (_rint(x1 + nx), _rint(y1 + ny)),
        (_rint(x1 - nx), _rint(y1 - ny)),
        (_rint(x0 - nx), _rint(y0 - ny)),
    ]


def _ticks(
    mask: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    angle: float,
    count: int,
) -> Image.Image:
    length = max(7.0, radius * 0.13)
    width = max(4.0, length * 0.42)
    step = _TAU / count
    for index in range(count):
        mask = _fill(
            mask,
            _bar(
                cx,
                cy,
                angle + step * index,
                radius * 0.90,
                radius + length,
                width,
            ),
        )
    return mask


def _ints(raw: list[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(_rint(x), _rint(y)) for x, y in raw]


def _fill(mask: Image.Image, pts: list[tuple[int, int]]) -> Image.Image:
    if len(pts) >= 3:
        ImageDraw.Draw(mask).polygon(pts, fill=255)
    return mask


def _cut(
    mask: Image.Image,
    outer: list[tuple[int, int]],
    inner: list[tuple[int, int]],
) -> Image.Image:
    if len(outer) < 3:
        return mask
    band = Image.new("L", (_SIDE, _SIDE), 0)
    pen = ImageDraw.Draw(band)
    pen.polygon(outer, fill=255)
    if len(inner) >= 3:
        pen.polygon(inner, fill=0)
    return ImageChops.lighter(mask, band)
