"""Mockups de dispositivos gerados por código: transforma prints de tela em celular ou notebook realistas."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from app.core.config import get_settings


def _status_bar(shot: Image.Image, width: int) -> Image.Image:
    """Adiciona barra de status (hora, sinal, bateria) no topo de prints sem ela."""
    bar_h = int(width * 0.12)
    top = shot.crop((0, 0, shot.width, max(2, shot.height // 200))).resize((1, 1)).getpixel((0, 0))
    lum = 0.299 * top[0] + 0.587 * top[1] + 0.114 * top[2]
    fg = (255, 255, 255) if lum < 150 else (15, 15, 20)
    out = Image.new("RGB", (width, shot.height + bar_h), top)
    out.paste(shot, (0, bar_h))
    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype(str(get_settings().fonts_dir / "Montserrat-SemiBold.ttf"), int(bar_h * 0.34))
    except OSError:
        font = ImageFont.load_default()
    y = int(bar_h * 0.36)
    d.text((int(width * 0.11), y), "9:41", font=font, fill=fg)
    x = int(width * 0.74)
    for k in range(4):  # sinal
        hh = int(bar_h * (0.12 + 0.06 * k))
        d.rectangle([x + k * int(width * 0.012), y + int(bar_h * 0.32) - hh, x + k * int(width * 0.012) + int(width * 0.007),
                     y + int(bar_h * 0.32)], fill=fg)
    bx = int(width * 0.82)
    bw, bh = int(width * 0.065), int(bar_h * 0.24)
    by = y + int(bar_h * 0.07)
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh // 4, outline=fg, width=max(1, width // 400))
    d.rounded_rectangle([bx + 3, by + 3, bx + int(bw * 0.8), by + bh - 3], radius=bh // 6, fill=fg)
    return out


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


def phone(screenshot: Path, out: Path, screen_w: int = 900, status_bar: bool = True) -> Path:
    """Celular moderno: corpo em titânio escuro, borda polida, dynamic island e reflexo de vidro."""
    with Image.open(screenshot) as im:
        shot = ImageOps.exif_transpose(im).convert("RGB")
    if status_bar:
        shot = shot.resize((screen_w, int(shot.height * screen_w / shot.width)), Image.Resampling.LANCZOS)
        shot = _status_bar(shot, screen_w)
    ratio = shot.height / shot.width
    ratio = min(max(ratio, 1.6), 2.3)
    sw, sh = screen_w, int(screen_w * ratio)
    shot = ImageOps.fit(shot, (sw, sh), Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    bez = int(sw * 0.045)
    W, H = sw + bez * 2, sh + bez * 2
    r_out = int(W * 0.15)
    r_in = r_out - bez
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    # corpo com gradiente metálico
    grad = Image.linear_gradient("L").resize((W, H)).rotate(35, expand=False)
    metal = Image.merge("RGB", [grad.point(lambda v: 40 + v // 6)] * 3)
    body.paste(metal, (0, 0), _rounded_mask((W, H), r_out))
    # aro polido
    d.rounded_rectangle([1, 1, W - 2, H - 2], radius=r_out, outline=(170, 170, 185, 255), width=max(2, W // 260))
    d.rounded_rectangle([bez // 3, bez // 3, W - bez // 3, H - bez // 3], radius=r_out - bez // 3,
                        fill=(8, 8, 12, 255))
    # tela
    screen = shot.convert("RGBA")
    body.paste(screen, (bez, bez), _rounded_mask((sw, sh), r_in))
    # dynamic island
    iw, ih = int(sw * 0.3), int(sw * 0.085)
    ix, iy = (W - iw) // 2, bez + int(sw * 0.03)
    d.rounded_rectangle([ix, iy, ix + iw, iy + ih], radius=ih // 2, fill=(0, 0, 0, 255))
    # botões laterais
    for y0, y1 in ((0.22, 0.3), (0.33, 0.41)):
        d.rounded_rectangle([0, int(H * y0), max(3, W // 120), int(H * y1)], radius=2, fill=(120, 120, 130, 255))
    d.rounded_rectangle([W - max(3, W // 120), int(H * 0.27), W, int(H * 0.38)], radius=2, fill=(120, 120, 130, 255))
    # reflexo diagonal sutil no vidro
    gloss = Image.new("L", (W, H), 0)
    ImageDraw.Draw(gloss).polygon([(0, 0), (int(W * 0.55), 0), (0, int(H * 0.38))], fill=30)
    gloss = gloss.filter(ImageFilter.GaussianBlur(W // 40))
    white = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    white.putalpha(Image.composite(gloss, Image.new("L", (W, H), 0), _rounded_mask((W, H), r_out)))
    body.alpha_composite(white)
    out.parent.mkdir(parents=True, exist_ok=True)
    body.save(out, "PNG")
    return out


def laptop(screenshot: Path, out: Path, screen_w: int = 1400) -> Path:
    """Notebook: tela com moldura fina, câmera, base em alumínio com sombra de dobradiça."""
    with Image.open(screenshot) as im:
        shot = ImageOps.exif_transpose(im).convert("RGB")
    sw, sh = screen_w, int(screen_w / 1.6)
    shot = ImageOps.fit(shot, (sw, sh), Image.Resampling.LANCZOS, centering=(0.5, 0.0))
    bez = int(sw * 0.022)
    lid_w, lid_h = sw + bez * 2, sh + bez * 2 + int(bez * 0.6)
    base_h = int(lid_h * 0.06)
    base_w = int(lid_w * 1.16)
    W, H = base_w, lid_h + base_h
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lx = (W - lid_w) // 2
    d.rounded_rectangle([lx, 0, lx + lid_w, lid_h], radius=int(bez * 1.4), fill=(18, 18, 22, 255),
                        outline=(150, 150, 160, 255), width=max(2, W // 700))
    img.paste(shot, (lx + bez, bez + int(bez * 0.3)))
    cx = lx + lid_w // 2
    d.ellipse([cx - bez // 5, bez // 4, cx + bez // 5, bez // 4 + bez // 2.5], fill=(40, 40, 50, 255))
    # base em alumínio (trapézio) com gradiente
    top = lid_h
    poly = [(lx - int(lid_w * 0.03), top), (lx + lid_w + int(lid_w * 0.03), top), (W, top + base_h), (0, top + base_h)]
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(base).polygon(poly, fill=(150, 152, 162, 255))
    shade = Image.linear_gradient("L").resize((W, base_h)).point(lambda v: 255 - v // 3)
    tint = Image.new("RGBA", (W, base_h), (120, 122, 132, 0))
    tint.putalpha(shade.point(lambda v: 255 - v))
    base.alpha_composite(tint, (0, top))
    img.alpha_composite(base)
    notch_w = int(lid_w * 0.14)
    d.rounded_rectangle([cx - notch_w // 2, top, cx + notch_w // 2, top + base_h // 2], radius=base_h // 4,
                        fill=(150, 152, 160, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out


def is_phone_screenshot(path: Path) -> bool:
    with Image.open(path) as im:
        w, h = im.size
    return 1.85 <= h / max(w, 1) <= 2.4
