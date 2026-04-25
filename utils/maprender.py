"""
V.I.C.T.O.R.I.A. — Hex Map Renderer
Generates a Victorian-era map image from the database hex grid.
Uses Pillow + optional numpy. Outputs a BytesIO PNG for Discord.
"""
import math
import io
import random
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────
# CONSTANTS & THEME
# ─────────────────────────────────────────

HEX_SIZE    = 22
GRID_RADIUS = 9
PADDING     = 80

COLOURS = {
    "plains":           "#c8b97a",
    "hills":            "#a89060",
    "forest":           "#5a7a4a",
    "coast":            "#8ab4c8",
    "mountain":         "#888070",
    "sea":              "#5878a0",
    "player_nation":    "#d4401a",
    "npc_friendly":     "#3a7a3a",
    "npc_neutral":      "#888888",
    "npc_hostile":      "#7a1a1a",
    "background":       "#1a1208",
    "border":           "#3a2a10",
    "text_light":       "#f0e8c8",
    "hex_border":       "#2a1a08",
    "hex_border_player":"#ff6030",
    "hex_border_npc":   "#606060",
    "title_bg":         "#0e0a04",
    "legend_bg":        "#120e06",
}

TERRAIN_SYMBOLS = {
    "plains":   "·",
    "hills":    "∧",
    "forest":   "♣",
    "coast":    "≈",
    "mountain": "▲",
    "sea":      "~",
}

FONT_PATH_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_PATH_MONO  = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"
FONT_PATH_SANS  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _load_font(path, size):
    for p in [path, FONT_PATH_SANS, FONT_PATH_MONO]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _hex_to_rgb(hex_col: str):
    h = hex_col.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def hex_to_pixel(q: int, r: int, size: int, ox: int, oy: int):
    """Axial → pixel centre (flat-top)."""
    x = size * (3/2 * q)
    y = size * (math.sqrt(3)/2 * q + math.sqrt(3) * r)
    return int(x + ox), int(y + oy)


def hex_corners(cx: int, cy: int, size: int):
    return [
        (cx + size * math.cos(math.radians(60 * i)),
         cy + size * math.sin(math.radians(60 * i)))
        for i in range(6)
    ]


# ─────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────

def render_map(
    hexes: list,
    npc_nations: list,
    nation_name: str = "The Empire",
    at_war_with: list = None,
    turn_number: int = 1,
) -> io.BytesIO:

    at_war_with = at_war_with or []

    grid_w   = int(HEX_SIZE * 3 * (GRID_RADIUS + 1))
    grid_h   = int(HEX_SIZE * math.sqrt(3) * (GRID_RADIUS * 2 + 1))
    legend_h = 120
    title_h  = 60
    img_w    = grid_w + PADDING * 2
    img_h    = grid_h + PADDING * 2 + title_h + legend_h
    ox       = img_w // 2
    oy       = PADDING + title_h + grid_h // 2

    # ── Create RGBA canvas ──
    bg_rgb = _hex_to_rgb(COLOURS["background"])
    img = Image.new("RGBA", (img_w, img_h), bg_rgb + (255,))

    # ── Optional parchment noise (numpy) ──
    try:
        import numpy as np
        arr = np.array(img)
        rng = np.random.default_rng(42)
        noise = rng.integers(0, 13, size=(img_h, img_w), dtype=np.uint8)
        arr[:, :, 0] = np.clip(arr[:, :, 0].astype(np.int16) + noise, 0, 255).astype(np.uint8)
        arr[:, :, 1] = np.clip(arr[:, :, 1].astype(np.int16) + noise // 2, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr, mode="RGBA")
    except ImportError:
        pass

    # ── ALWAYS re-acquire draw after any img reassignment ──
    draw = ImageDraw.Draw(img)

    font_title   = _load_font(FONT_PATH_SERIF, 20)
    font_symbol  = _load_font(FONT_PATH_MONO,  9)
    font_legend  = _load_font(FONT_PATH_SANS,  10)
    font_capital = _load_font(FONT_PATH_SANS,  7)

    disposition_map = {n["name"]: n.get("disposition", "neutral") for n in npc_nations}

    # ── Draw hexes ──
    for h in hexes:
        q, r = h["q"], h["r"]
        cx, cy = hex_to_pixel(q, r, HEX_SIZE, ox, oy)

        # Skip hexes that are off-canvas
        if not (0 < cx < img_w and 0 < cy < img_h):
            continue

        corners = hex_corners(cx, cy, HEX_SIZE - 1)
        terrain      = h.get("terrain", "plains")
        controlled   = h.get("controlled_by")
        is_player    = h.get("is_player_nation", False)

        # Base fill
        base_col = _hex_to_rgb(COLOURS.get(terrain, COLOURS["plains"]))
        draw.polygon(corners, fill=base_col + (255,))

        # Control tint (RGBA over base)
        if is_player:
            tint = _hex_to_rgb(COLOURS["player_nation"]) + (90,)
            draw.polygon(corners, fill=tint)
        elif controlled:
            disp     = disposition_map.get(controlled, "neutral")
            tint_col = _hex_to_rgb(COLOURS.get(f"npc_{disp}", COLOURS["npc_neutral"]))
            draw.polygon(corners, fill=tint_col + (70,))

        # War overlay
        if controlled in at_war_with:
            draw.polygon(corners, fill=(220, 0, 0, 50))

        # Border
        if is_player:
            b_col, b_w = _hex_to_rgb(COLOURS["hex_border_player"]) + (255,), 2
        elif controlled:
            b_col, b_w = _hex_to_rgb(COLOURS["hex_border_npc"]) + (255,), 1
        else:
            b_col, b_w = _hex_to_rgb(COLOURS["hex_border"]) + (200,), 1
        draw.polygon(corners, outline=b_col, width=b_w)

        # Terrain symbol
        symbol  = TERRAIN_SYMBOLS.get(terrain, "·")
        sym_rgb = (255, 255, 255, 180) if terrain in ("sea", "forest", "mountain") else (42, 26, 8, 200)
        try:
            bb = draw.textbbox((0, 0), symbol, font=font_symbol)
            sw, sh = bb[2] - bb[0], bb[3] - bb[1]
            draw.text((cx - sw // 2, cy - sh // 2 - 1), symbol, font=font_symbol, fill=sym_rgb)
        except Exception:
            pass

    # ── NPC capitals ──
    for n in npc_nations:
        if n.get("is_defeated"):
            continue
        cq, cr = n.get("capital_q"), n.get("capital_r")
        if cq is None:
            continue
        cx, cy = hex_to_pixel(cq, cr, HEX_SIZE, ox, oy)
        s = 5
        draw.ellipse((cx - s, cy - s, cx + s, cy + s), fill=(255, 215, 0, 255), outline=(139, 105, 20, 255))
        try:
            name = n["name"]
            bb = draw.textbbox((0, 0), name, font=font_capital)
            nw = bb[2] - bb[0]
            draw.text((cx - nw // 2 + 1, cy + s + 2), name, font=font_capital, fill=(0, 0, 0, 180))
            draw.text((cx - nw // 2, cy + s + 1), name, font=font_capital, fill=(240, 232, 200, 255))
        except Exception:
            pass

    # ── Player nation label ──
    player_hexes = [(h["q"], h["r"]) for h in hexes if h.get("is_player_nation")]
    if player_hexes:
        centres = [hex_to_pixel(q, r, HEX_SIZE, ox, oy) for q, r in player_hexes]
        ax = sum(c[0] for c in centres) // len(centres)
        ay = sum(c[1] for c in centres) // len(centres)
        try:
            bb  = draw.textbbox((0, 0), nation_name, font=font_legend)
            nw  = bb[2] - bb[0]
            draw.text((ax - nw // 2 + 1, ay + 1), nation_name, font=font_legend, fill=(0, 0, 0, 200))
            draw.text((ax - nw // 2, ay), nation_name, font=font_legend, fill=(255, 128, 80, 255))
        except Exception:
            pass

    # ── Title bar ──
    title_text = f"V.I.C.T.O.R.I.A.  ·  {nation_name}  ·  Turn {turn_number}"
    title_bg   = _hex_to_rgb(COLOURS["title_bg"]) + (255,)
    draw.rectangle((0, 0, img_w, title_h), fill=title_bg)
    draw.line((PADDING // 2, title_h - 2, img_w - PADDING // 2, title_h - 2), fill=(90, 58, 16, 255), width=2)
    try:
        bb = draw.textbbox((0, 0), title_text, font=font_title)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text(((img_w - tw) // 2, (title_h - th) // 2), title_text, font=font_title, fill=_hex_to_rgb(COLOURS["text_light"]) + (255,))
    except Exception:
        pass

    # ── Legend ──
    legend_y  = img_h - legend_h
    legend_bg = _hex_to_rgb(COLOURS["legend_bg"]) + (255,)
    draw.rectangle((0, legend_y, img_w, img_h), fill=legend_bg)
    draw.line((PADDING // 2, legend_y + 1, img_w - PADDING // 2, legend_y + 1), fill=(90, 58, 16, 255), width=1)

    legend_items = [
        (COLOURS["player_nation"],  "Your Nation"),
        (COLOURS["npc_friendly"],   "Friendly"),
        (COLOURS["npc_neutral"],    "Neutral"),
        (COLOURS["npc_hostile"],    "Hostile"),
        (COLOURS["plains"],         "Plains"),
        (COLOURS["hills"],          "Hills"),
        (COLOURS["forest"],         "Forest"),
        (COLOURS["coast"],          "Coast"),
        (COLOURS["mountain"],       "Mountain"),
        (COLOURS["sea"],            "Sea"),
    ]
    lx = PADDING // 2
    ly = legend_y + 14
    col_w = (img_w - PADDING) // len(legend_items)
    for i, (col, label) in enumerate(legend_items):
        x = lx + i * col_w
        draw.rectangle((x, ly, x + 12, ly + 12), fill=_hex_to_rgb(col) + (255,), outline=(136, 136, 136, 255))
        try:
            draw.text((x + 15, ly), label, font=font_legend, fill=_hex_to_rgb(COLOURS["text_light"]) + (255,))
        except Exception:
            pass

    # ── Compass rose ──
    _draw_compass(draw, img_w - PADDING + 20, PADDING + title_h + 20, 18, font_legend)

    # ── Final border ──
    draw.rectangle((1, 1, img_w - 2, img_h - 2), outline=_hex_to_rgb(COLOURS["border"]) + (255,), width=3)

    # ── Export: flatten RGBA -> RGB ──
    final = Image.new("RGB", (img_w, img_h), bg_rgb)
    final.paste(img, mask=img.split()[3])
    buf = io.BytesIO()
    final.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def _draw_compass(draw, cx, cy, size, font):
    for label, dx, dy in [("N", 0, -1), ("S", 0, 1), ("E", 1, 0), ("W", -1, 0)]:
        lx = cx + dx * (size + 6)
        ly = cy + dy * (size + 6)
        try:
            bb = draw.textbbox((0, 0), label, font=font)
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            draw.text((lx - w // 2, ly - h // 2), label, font=font, fill=(200, 176, 96, 255))
        except Exception:
            pass
    draw.line((cx, cy - size, cx, cy + size), fill=(200, 176, 96, 255), width=1)
    draw.line((cx - size, cy, cx + size, cy), fill=(200, 176, 96, 255), width=1)
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(255, 215, 0, 255))


# ─────────────────────────────────────────
# DB FETCH + RENDER
# ─────────────────────────────────────────

async def render_map_for_guild(guild_id: int, conn) -> io.BytesIO:
    hexes = await conn.fetch(
        "SELECT q, r, terrain, controlled_by, is_player_nation FROM hex_map WHERE guild_id = $1", guild_id
    )
    npc_nations = await conn.fetch(
        "SELECT name, disposition, capital_q, capital_r, is_defeated FROM npc_nations WHERE guild_id = $1", guild_id
    )
    config = await conn.fetchrow("SELECT nation_name FROM guild_config WHERE guild_id = $1", guild_id)
    nation = await conn.fetchrow("SELECT turn_number, at_war_with FROM nation_state WHERE guild_id = $1", guild_id)

    return render_map(
        hexes       = [dict(h) for h in hexes],
        npc_nations = [dict(n) for n in npc_nations],
        nation_name = config["nation_name"] if config else "The Empire",
        at_war_with = list(nation["at_war_with"]) if nation and nation["at_war_with"] else [],
        turn_number = nation["turn_number"] if nation else 1,
    )
