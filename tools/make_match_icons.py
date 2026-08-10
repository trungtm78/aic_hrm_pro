# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Generate the module icons for the staffing app and its two connectors.

Committed as a generator rather than as three opaque PNGs: an icon that can be
regenerated from tokens is an icon that stays in step with the design system,
and a reviewer can read what it draws instead of opening a binary.

The mark is literally the product: a field of candidates, one selected. No
gradients, no glow, no sparkle iconography - see design.md "Hard bans".

Usage:  python tools/make_match_icons.py
"""
import pathlib

from PIL import Image, ImageDraw

# Semantic colours resolved from tokens.css (hue 235 throughout). Kept as sRGB
# here because PIL has no OKLCH; the conversion is recorded next to each value
# so a token change can be traced to the pixel it produces.
INK = (32, 41, 57)            # --steel-20   oklch(20% 0.010 235)
PAPER = (246, 248, 250)       # --steel-98   oklch(98% 0.005 235)
MUTED = (108, 122, 141)       # --steel-50   oklch(50% 0.010 235)
ACCENT = (26, 96, 158)        # --ink-blue-45 oklch(45% 0.14 235)

SIZE = 140
SCALE = 8                     # draw large, downsample once: crisp edges, no blur filter


def _draw_candidate_field(draw, selected, accent):
    """A 4x4 field of tiles with exactly one picked out.

    Rows are people, the highlighted tile is the match. The selected tile is the
    only element allowed to carry the accent colour, which keeps accent well
    under the 5% area budget the design system sets.
    """
    margin, gap, cols = 26 * SCALE, 6 * SCALE, 4
    span = SIZE * SCALE - 2 * margin
    tile = (span - gap * (cols - 1)) / cols
    for index in range(cols * cols):
        row, column = divmod(index, cols)
        x = margin + column * (tile + gap)
        y = margin + row * (tile + gap)
        colour = accent if index == selected else MUTED
        draw.rounded_rectangle(
            [x, y, x + tile, y + tile],
            radius=tile * 0.28, fill=colour)


def build(path, selected, accent=ACCENT, background=INK):
    canvas = Image.new('RGB', (SIZE * SCALE, SIZE * SCALE), background)
    draw = ImageDraw.Draw(canvas)
    _draw_candidate_field(draw, selected, accent)
    canvas = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, 'PNG', optimize=True)
    return path


def build_banner(path, selected=6):
    """Store cover, 1200x628. Same mark, left-weighted, with breathing room."""
    width, height = 1200, 628
    canvas = Image.new('RGB', (width * 2, height * 2), INK)
    draw = ImageDraw.Draw(canvas)
    margin, gap, cols = 150, 22, 4
    tile = 96
    origin_x, origin_y = margin, (height * 2 - (tile * cols + gap * (cols - 1))) / 2
    for index in range(cols * cols):
        row, column = divmod(index, cols)
        x = origin_x + column * (tile + gap)
        y = origin_y + row * (tile + gap)
        colour = ACCENT if index == selected else MUTED
        draw.rounded_rectangle([x, y, x + tile, y + tile],
                               radius=tile * 0.28, fill=colour)
    # A single hairline rule, the same device the app uses to separate a figure
    # from its label. No text: the store renders the title above the cover.
    rule_x = origin_x + cols * (tile + gap) + 90
    draw.line([rule_x, origin_y, rule_x, origin_y + tile * cols + gap * (cols - 1)],
              fill=PAPER, width=3)
    canvas.resize((width, height), Image.LANCZOS).save(path, 'PNG', optimize=True)
    return path


ICONS = {
    'aic_hrm_match': 6,            # centre of the field: the app itself
    'aic_hrm_match_okr': 3,        # top-right: a connector reaching outward
    'aic_hrm_match_timesheet': 12,  # bottom-left: the other connector
}


if __name__ == '__main__':
    root = pathlib.Path(__file__).resolve().parents[1] / 'addons_hrm'
    for module, selected in ICONS.items():
        target = root / module / 'static' / 'description' / 'icon.png'
        build(target, selected)
        print('icon   %s' % target.relative_to(root.parent))
    banner = root / 'aic_hrm_match' / 'static' / 'description' / 'banner.png'
    build_banner(banner)
    print('banner %s' % banner.relative_to(root.parent))
