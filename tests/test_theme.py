"""The warm palette must stay readable. Colours are read from the CSS itself, so editing a colour re-runs these checks.

Thresholds are WCAG 2.x: 4.5:1 for normal text, 3:1 for large text and graphics.
"""
import itertools
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
CARD = (ROOT / "server" / "ui" / "card.html").read_text(encoding="utf-8")


def light_vars(html):
    """CSS custom properties of the default (light) theme: the first :root block."""
    block = re.search(r":root\s*\{(.*?)\}", html, re.S).group(1)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})\s*;", block))


def luminance(hex_colour):
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


PAGE_VARS, CARD_VARS = light_vars(PAGE), light_vars(CARD)

PAGE_PAIRS = [
    ("text", "bg"), ("text", "panel"), ("text", "panel2"), ("text", "brand-soft"),           # body, panels, chat bubbles
    ("muted", "bg"), ("muted", "panel"), ("muted", "panel2"),                                 # small grey text
    ("brand-ink", "brand"), ("brand-strong", "brand-soft"), ("brand-strong", "panel"),        # button, chips, headings
    ("brown", "brown-soft"), ("bad", "bad-soft"), ("bad", "panel"),                           # icon buttons, recording state
    ("trace-text", "trace-bg"), ("muted", "trace-bg"), ("brand-strong", "trace-bg"),          # behind-the-scenes panel
]
CARD_PAIRS = [
    ("text", "panel"), ("muted", "panel"), ("muted", "panel2"), ("brand-strong", "panel"),
    ("good", "panel"), ("good", "good-soft"), ("warn", "panel"), ("warn", "warn-soft"),
    ("bad", "panel"), ("bad", "bad-soft"), ("info", "info-soft"),
]


@pytest.mark.parametrize("fg,bg", PAGE_PAIRS)
def test_simulator_page_text_is_readable(fg, bg):
    assert contrast(PAGE_VARS[fg], PAGE_VARS[bg]) >= 4.5, f"{fg} on {bg}"


@pytest.mark.parametrize("fg,bg", CARD_PAIRS)
def test_card_text_is_readable(fg, bg):
    assert contrast(CARD_VARS[fg], CARD_VARS[bg]) >= 4.5, f"{fg} on {bg}"


def test_header_text_on_the_screen_title_bar_is_readable():
    assert contrast(PAGE_VARS["brand-strong"], "#EAF1DF") >= 4.5  # the Echo Show bar background is a literal in the CSS
    assert "#EAF1DF" in PAGE


def test_the_two_files_share_one_palette():
    shared = set(PAGE_VARS) & set(CARD_VARS)
    assert {"text", "muted", "brand", "brand-strong", "good", "warn", "bad", "panel"} <= shared
    assert {k: PAGE_VARS[k] for k in shared} == {k: CARD_VARS[k] for k in shared}


def test_chart_segments_differ_in_lightness_not_only_hue():
    """Borrowed / interest / fees must be told apart by people who cannot separate green from red."""
    bars = {k: CARD_VARS[k] for k in ("borrowed", "interest", "fees")}
    for (a, ca), (b, cb) in itertools.combinations(bars.items(), 2):
        assert contrast(ca, cb) >= 1.5, f"{a} and {b} are too close in lightness"
    assert contrast(bars["borrowed"], CARD_VARS["panel"]) >= 3 and contrast(bars["interest"], CARD_VARS["panel"]) >= 3


def test_card_still_supports_a_dark_host():
    assert ':root[data-theme="dark"]' in CARD
    assert "theme: 'light'" in PAGE  # the simulator asks for the light theme
