"""Textos animados em ASS (renderizados pelo libass dentro do FFmpeg).

Cada estilo visual tem um tratamento de título próprio (caixa sólida, barra animada, linhas finas, brilho),
selo de preço para ofertas e tela final com botão de chamada e "pílulas" de contato.
"""

import math
import re
from dataclasses import dataclass, field

UPPERCASE_FONTS = {"Anton", "Bebas Neue"}
TITLE_STYLE = {"comercial": "box", "criativo": "box_tilt", "moderno": "bar", "profissional": "bar",
               "elegante": "lines", "tecnologico": "glow"}
PRICE_RE = re.compile(r"(R\$\s?\d[\d.,]*|\d{1,3}\s?%\s?(off|de desconto)?)", re.I)


def ass_color(hex_color: str, alpha: float = 0.0) -> str:
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = int(max(0.0, min(1.0, alpha)) * 255)
    return f"&H{a:02X}{b}{g}{r}".upper()


def _c(hex_color: str) -> str:
    """Cor para override tag (\\c&HBBGGRR&)."""
    return ass_color(hex_color)[:2] + ass_color(hex_color)[4:] + "&"


def ts(t: float) -> str:
    t = max(t, 0.0)
    cs_total = int(round(t * 100))
    h, rem = divmod(cs_total, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def esc(text: str) -> str:
    return (text or "").replace("\\", "⧵").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@dataclass
class TextEvent:
    start: float
    end: float
    text: str
    style: str
    x: int
    y: int
    animation: str = "fade"
    delay: float = 0.0
    align: int = 5
    margin_l: int = 0
    margin_r: int = 0


@dataclass
class AssDoc:
    w: int
    h: int
    font: str
    palette: list[str]
    subtitle_style: str = "highlight"
    visual_style: str = "moderno"
    events: list[str] = field(default_factory=list)

    @property
    def m(self) -> int:
        return min(self.w, self.h)

    @property
    def pal(self) -> list[str]:
        return (list(self.palette) + ["#111111", "#333333", "#FACC15", "#FFFFFF"])[:4]

    @property
    def title_style(self) -> str:
        return TITLE_STYLE.get(self.visual_style, "bar")

    @property
    def title_size(self) -> int:
        return int(self.m * (0.135 if self.font in UPPERCASE_FONTS else 0.105))

    @property
    def on_accent(self) -> str:
        return "#111111" if luminance(self.pal[2]) > 0.55 else "#FFFFFF"

    def header(self) -> str:
        pal = self.pal
        white = ass_color(pal[3])
        accent = ass_color(pal[2])
        dark = ass_color("#000000")
        shadow = ass_color("#000000", 0.45)
        m = self.m
        ml = int(self.w * 0.08)
        o = max(2, m // 260)
        pad = max(10, m // 55)
        cap_size = int(m * 0.07)
        # legenda
        cap = dict(primary=white, secondary=white, outline=dark, back=ass_color("#000000", 0.35), border=1,
                   ol=max(3, m // 180), sh=o)
        if self.subtitle_style == "boxed":
            cap.update(border=3, outline=ass_color("#000000", 0.3), ol=max(8, m // 80), sh=0)
        elif self.subtitle_style == "highlight":
            cap.update(primary=accent, secondary=white, ol=max(4, m // 150))
        elif self.subtitle_style == "bold_outline":
            cap.update(ol=max(6, m // 100))
        ts_ = self.title_size
        box_text = ass_color(self.on_accent)
        styles = [
            # título comum (contorno + sombra)
            f"Style: Title,{self.font},{ts_},{white},{white},{dark},{shadow},-1,0,0,0,100,100,1,0,1,{o + 1},{o + 2},5,{ml},{ml},10,1",
            # título dentro de caixa sólida na cor de destaque (BorderStyle 3 usa OutlineColour como caixa)
            f"Style: TitleBox,{self.font},{ts_},{box_text},{box_text},{accent},{ass_color('#000000', 0.5)},-1,0,0,0,100,100,1,0,3,{pad},0,5,{ml},{ml},10,1",
            f"Style: Subtitle,Montserrat SemiBold,{int(m * 0.056)},{accent},{accent},{dark},{shadow},0,0,0,0,100,100,0.5,0,1,{o},{o},5,{ml},{ml},10,1",
            f"Style: SubtitlePill,Montserrat SemiBold,{int(m * 0.05)},{white},{white},{ass_color('#000000', 0.45)},{shadow},0,0,0,0,100,100,0.5,0,3,{pad - 2},0,5,{ml},{ml},10,1",
            f"Style: Caption,Montserrat ExtraBold,{cap_size},{cap['primary']},{cap['secondary']},{cap['outline']},{cap['back']},"
            f"-1,0,0,0,100,100,0,0,{cap['border']},{cap['ol']},{cap['sh']},2,{ml},{ml},{int(self.h * 0.1)},1",
            f"Style: Bullet,Montserrat SemiBold,{int(m * 0.058)},{white},{white},{ass_color('#000000', 0.45)},{shadow},0,0,0,0,100,100,0,0,3,{pad - 2},0,5,{ml},{ml},10,1",
            f"Style: Badge,Montserrat Black,{int(m * 0.1)},{box_text},{box_text},{accent},{shadow},-1,0,0,0,100,100,0,0,1,0,0,5,{ml},{ml},10,1",
            f"Style: Shape,Arial,20,{accent},{accent},{accent},{shadow},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
            f"Style: EndName,{self.font},{int(m * 0.12)},{white},{white},{dark},{shadow},-1,0,0,0,100,100,1,0,1,{o + 1},{o + 2},5,{ml},{ml},10,1",
            f"Style: EndCta,Montserrat ExtraBold,{int(m * 0.062)},{box_text},{box_text},{accent},{ass_color('#000000', 0.5)},-1,0,0,0,100,100,0.5,0,3,{pad + 6},0,5,{ml},{ml},10,1",
            f"Style: EndInfo,Montserrat SemiBold,{int(m * 0.052)},{white},{white},{ass_color('#FFFFFF', 0.86)},{shadow},0,0,0,0,100,100,0,0,3,{pad},0,5,{ml},{ml},10,1",
            f"Style: Watermark,Montserrat SemiBold,{int(m * 0.032)},{ass_color('#FFFFFF', 0.35)},{white},"
            f"{ass_color('#000000', 0.6)},{ass_color('#000000', 0.7)},-1,0,0,0,100,100,0,0,1,1,0,9,"
            f"{int(m * 0.04)},{int(m * 0.04)},{int(m * 0.04)},1",
        ]
        return "\n".join([
            "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {self.w}", f"PlayResY: {self.h}",
            "WrapStyle: 0", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            *styles, "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ])

    # ---------- utilidades ----------

    def _anim(self, anim: str, x: int, y: int, dur_ms: int, text: str, extra: str = "") -> str:
        out_ms = 220
        if anim == "slide_up":
            d = int(self.m * 0.06)
            return f"{{\\fad(200,{out_ms})\\move({x},{y + d},{x},{y},0,380){extra}}}{text}"
        if anim == "slide_left":
            d = int(self.w * 0.18)
            return f"{{\\fad(150,{out_ms})\\move({x + d},{y},{x},{y},0,380){extra}}}{text}"
        if anim == "pop":
            return (f"{{\\pos({x},{y})\\fad(80,{out_ms})\\fscx40\\fscy40\\t(0,200,\\fscx110\\fscy110)"
                    f"\\t(200,330,\\fscx100\\fscy100){extra}}}{text}")
        if anim == "blur_in":
            return f"{{\\pos({x},{y})\\fad(150,{out_ms})\\blur18\\t(0,450,\\blur0){extra}}}{text}"
        if anim == "typewriter":
            chars = list(text.replace("\\N", "\n"))
            per = max(2, min(8, int(min(dur_ms * 0.4, 1600) / 10 / max(len(chars), 1))))
            body = "".join(("\\N" if c == "\n" else f"{{\\ko{per}}}{c}") for c in chars)
            return f"{{\\pos({x},{y})\\fad(0,{out_ms}){extra}}}{body}"
        if anim == "none":
            return f"{{\\pos({x},{y}){extra}}}{text}"
        return f"{{\\pos({x},{y})\\fad(300,{out_ms}){extra}}}{text}"

    def _lines(self, text: str, size: int, max_w: float | None = None) -> tuple[int, float]:
        """Estimativa de quebra de linhas e largura (px) da maior linha."""
        per_char = size * (0.5 if self.font in UPPERCASE_FONTS else 0.58)
        max_w = max_w or self.w * 0.84
        words, lines, cur = text.split(), [], ""
        for wd in words:
            cand = f"{cur} {wd}".strip()
            if cur and len(cand) * per_char > max_w:
                lines.append(cur)
                cur = wd
            else:
                cur = cand
        if cur:
            lines.append(cur)
        width = max((len(ln) for ln in lines), default=0) * per_char
        return max(1, len(lines)), min(width, max_w)

    def _rect(self, start: float, end: float, x: float, y: float, w: float, h: float, color: str, extra: str = "",
              layer: int = 0, alpha: str = "00") -> None:
        draw = f"m 0 0 l {w:.0f} 0 {w:.0f} {h:.0f} 0 {h:.0f}"
        self.events.append(
            f"Dialogue: {layer},{ts(start)},{ts(end)},Shape,,0,0,0,,"
            f"{{\\an7\\pos({x:.0f},{y:.0f})\\c{_c(color)}\\1a&H{alpha}&\\bord0\\shad0{extra}\\p1}}{draw}{{\\p0}}")

    # ---------- elementos ----------

    def add_text(self, ev: TextEvent) -> None:
        start = ev.start + ev.delay
        if ev.end - start < 0.2 or not ev.text.strip():
            return
        text = esc(ev.text.upper() if ev.style in ("Title", "TitleBox", "EndName", "Kinetic") and self.font in UPPERCASE_FONTS else ev.text)
        extra = f"\\an{ev.align}" if ev.align != 5 else ""
        body = self._anim(ev.animation, ev.x, ev.y, int((ev.end - start) * 1000), text, extra)
        self.events.append(f"Dialogue: 1,{ts(start)},{ts(ev.end)},{ev.style},,{ev.margin_l},{ev.margin_r},0,,{body}")

    def add_title(self, start: float, end: float, text: str, x: int, y: int, anim: str, role: str = "",
                  align: str = "center", max_w: float | None = None, badge_at: tuple[int, int] | None = None) -> int:
        """Desenha o título com o tratamento do estilo; retorna a coordenada y abaixo do bloco."""
        if not text.strip() or end - start < 0.3:
            return y
        pm = PRICE_RE.search(text)
        if pm and (role == "offer" or badge_at):
            bx, by = badge_at or (x, y)
            price = pm.group(0).strip()
            rest = (text[:pm.start()] + text[pm.end():]).strip(" -–:,")
            self.add_badge(start, end, price, bx, by)
            if not rest or not badge_at:
                if rest and not badge_at:
                    self.add_subtitle(start, end, rest, x, int(by + self.m * 0.3), "fade")
                return y
            text = rest[:1].upper() + rest[1:]
        left = align == "left"
        an, ml, mr = (4, int(x), int(self.w - x - (max_w or self.w * 0.45))) if left else (5, 0, 0)
        size = self.title_size
        n_lines, width = self._lines(text.upper() if self.font in UPPERCASE_FONTS else text, size,
                                     max_w if left else None)
        if left:
            x = int(x)

        def ev(style: str, animation: str) -> TextEvent:
            e = TextEvent(start, end, text, style, x, y, animation, align=an, margin_l=ml, margin_r=mr)
            return e
        block_h = n_lines * size * 1.12
        accent = self.pal[2]
        st = self.title_style
        dur = end - start
        if st in ("box", "box_tilt"):
            extra = "\\frz2.5" if st == "box_tilt" else ""
            self.add_text(ev("TitleBox", anim if anim != "typewriter" else "pop"))
            if extra:
                self.events[-1] = self.events[-1].replace("}", extra + "}", 1)
            return int(y + block_h / 2 + self.m * 0.05)
        if st == "lines":
            self.add_text(ev("Title", anim))
            lw = max(width * 0.5, self.m * 0.2)
            lx = x if left else x - lw / 2
            for yy in (y - block_h / 2 - self.m * 0.04, y + block_h / 2 + self.m * 0.03):
                self._rect(start + 0.2, end, lx, yy, lw, max(2, self.m / 400), accent,
                           f"\\fad(300,200)\\org({x},{yy:.0f})\\fscx0\\t(200,800,\\fscx100)")
            return int(y + block_h / 2 + self.m * 0.07)
        if st == "glow":
            glow = self._anim(anim, x, y, int(dur * 1000), esc(text),
                              f"\\an{an}\\blur12\\bord6\\3c{_c(accent)}\\3a&H60&\\1a&HFF&")
            self.events.append(f"Dialogue: 0,{ts(start)},{ts(end)},Title,,{ml},{mr},0,,{glow}")
            self.add_text(ev("Title", anim))
            return int(y + block_h / 2 + self.m * 0.05)
        # "bar": título + barra de destaque que cresce
        self.add_text(ev("Title", anim))
        bw, bh = self.m * 0.16, max(6, self.m * 0.014)
        by = y + block_h / 2 + self.m * 0.025
        bx = x if left else x - bw / 2
        self._rect(start + 0.25, end, bx, by, bw, bh, accent,
                   f"\\fad(150,200)\\org({bx:.0f},{by:.0f})\\fscx0\\t(250,700,\\fscx100)")
        return int(by + bh + self.m * 0.04)

    def add_badge(self, start: float, end: float, text: str, x: int, y: int) -> int:
        """Selo estilo 'oferta' (estrela) com o preço/desconto dentro, com pop e leve rotação."""
        size = int(self.m * 0.1)
        long = len(text) > 12
        _, width = self._lines(text.split(" ", 1)[-1] if long else text, size)
        r = max(self.m * 0.26, width / 2 * 1.3)
        spikes = 18
        pts = []
        for i in range(spikes * 2):
            ang = math.pi * i / spikes
            rr = r if i % 2 == 0 else r * 0.88
            pts.append(f"{r + rr * math.cos(ang):.0f} {r + rr * math.sin(ang):.0f}")
        draw = f"m {pts[0]} l " + " ".join(pts[1:])
        self.events.append(
            f"Dialogue: 0,{ts(start)},{ts(end)},Shape,,0,0,0,,{{\\an5\\pos({x},{y})\\c{_c(self.pal[2])}\\bord0"
            f"\\shad{max(3, self.m // 150)}\\4a&H70&\\fad(80,200)\\fscx30\\fscy30\\t(0,220,\\fscx108\\fscy108)"
            f"\\t(220,360,\\fscx100\\fscy100)\\t(0,{int((end - start) * 1000)},\\frz-8)\\p1}}{draw}{{\\p0}}")
        lines = esc(text).replace(" ", "\\N", 1) if long else esc(text)
        self.events.append(
            f"Dialogue: 1,{ts(start + 0.12)},{ts(end)},Badge,,0,0,0,,{{\\pos({x},{y})\\fad(100,200)\\fscx40\\fscy40"
            f"\\t(0,220,\\fscx105\\fscy105)\\t(220,340,\\fscx100\\fscy100)\\frz-4}}{lines}")
        return int(y + r + self.m * 0.04)

    def add_orbs(self, start: float, end: float, seed: int) -> None:
        """Luzes desfocadas flutuando (profundidade e movimento em fundos sem foto)."""
        import random

        rnd = random.Random(seed)
        for k in range(4):
            r = self.m * rnd.uniform(0.06, 0.16)
            x0, y0 = rnd.uniform(0, self.w), rnd.uniform(0, self.h)
            x1, y1 = x0 + rnd.uniform(-0.15, 0.15) * self.w, y0 - rnd.uniform(0.05, 0.2) * self.h
            pts = [f"{r + r * math.cos(2 * math.pi * i / 24):.0f} {r + r * math.sin(2 * math.pi * i / 24):.0f}"
                   for i in range(24)]
            color = self.pal[2] if k % 2 == 0 else "#FFFFFF"
            alpha = "C8" if color == "#FFFFFF" else "A0"
            draw = f"m {pts[0]} l " + " ".join(pts[1:])
            self.events.append(
                f"Dialogue: 0,{ts(start)},{ts(end)},Shape,,0,0,0,,{{\\an5\\move({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})"
                f"\\c{_c(color)}\\1a&H{alpha}&\\bord0\\shad0\\blur{max(8, int(r / 2.5))}\\fad(500,500)\\p1}}{draw}{{\\p0}}")

    def add_subtitle(self, start: float, end: float, text: str, x: int, y: int, anim: str, align: str = "center",
                     max_w: float | None = None) -> None:
        style = "SubtitlePill" if self.title_style in ("bar", "glow") else "Subtitle"
        left = align == "left"
        self.add_text(TextEvent(start, end, text, style, x, y, "fade" if anim == "typewriter" else anim, delay=0.3,
                                align=4 if left else 5, margin_l=int(x) if left else 0,
                                margin_r=int(self.w - x - (max_w or self.w * 0.45)) if left else 0))

    def add_bullets(self, start: float, end: float, items: list[str], x: int, y: int, align: str = "center",
                    max_w: float | None = None) -> None:
        """Lista de destaques em 'pílulas' com marcador, entrando em sequência (coluna alinhada à esquerda)."""
        size = self.m * 0.058
        r = self.m * 0.02
        if align != "left":
            widest = max((len(i) for i in items[:4]), default=0) * size * 0.56
            x = int((self.w - widest) / 2 - r * 1.6)
            max_w = self.w - x - self.w * 0.05
        step = int(self.m * 0.115)
        for k, item in enumerate(items[:4]):
            yy = y + k * step
            st = start + 0.5 + 0.28 * k
            if end - st < 0.3:
                break
            cx = x + r
            tx = int(x + r * 3.4)
            pts = [f"{r + r * math.cos(2 * math.pi * i / 16):.0f} {r + r * math.sin(2 * math.pi * i / 16):.0f}"
                   for i in range(16)]
            draw = f"m {pts[0]} l " + " ".join(pts[1:])
            self.events.append(
                f"Dialogue: 2,{ts(st)},{ts(end)},Shape,,0,0,0,,{{\\an5\\pos({cx:.0f},{yy})\\c{_c(self.pal[2])}\\bord0"
                f"\\shad0\\fad(120,200)\\fscx0\\fscy0\\t(0,250,\\fscx100\\fscy100)\\p1}}{draw}{{\\p0}}")
            self.add_text(TextEvent(st, end, item, "Bullet", tx, yy, "slide_left", align=4, margin_l=tx,
                                    margin_r=max(0, int(self.w - tx - (max_w or self.w * 0.45)))))

    def add_kinetic(self, start: float, end: float, text: str, y: int) -> None:
        """Tipografia cinética: palavras grandes, uma por linha, entrando alternadas com bloco de cor."""
        words = text.replace("\\N", " ").split()
        if not words:
            return
        lines: list[str] = []
        for wd in words:
            if lines and len(lines[-1]) + len(wd) < 9 and len(lines) >= 1 and len(wd) <= 4:
                lines[-1] += " " + wd
            else:
                lines.append(wd)
        while len(lines) > 5:
            lines = [" ".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        upper = self.font in UPPERCASE_FONTS
        longest = max(len(ln) for ln in lines)
        size = int(min(self.m * (0.22 if upper else 0.17), self.w * 0.86 / max(longest * (0.5 if upper else 0.6), 1)))
        step = int(size * 1.08)
        y0 = int(y - step * (len(lines) - 1) / 2)
        hl = len(lines) // 2 if len(lines) > 1 else -1
        for k, ln in enumerate(lines):
            yy = y0 + k * step
            st = start + 0.12 * k
            if k == hl:
                bw = min(self.w * 0.92, len(ln) * size * (0.5 if upper else 0.6) + size * 0.6)
                bx = (self.w - bw) / 2
                self._rect(st, end, bx, yy - size * 0.58, bw, size * 1.12, self.pal[2],
                           f"\\fad(0,200)\\org({bx:.0f},{yy})\\fscx0\\t(0,260,\\fscx100)", layer=1)
            color = self.on_accent if k == hl else (self.pal[3] if k % 2 == 0 else self.pal[2])
            dx = int(self.w * (0.25 if k % 2 == 0 else -0.25))
            txt = esc(ln.upper() if upper else ln)
            self.events.append(
                f"Dialogue: 2,{ts(st + (0.12 if k == hl else 0))},{ts(end)},Title,,0,0,0,,"
                f"{{\\fs{size}\\c{_c(color)}\\bord{0 if k == hl else max(2, self.m // 300)}\\shad{0 if k == hl else 3}"
                f"\\move({self.w // 2 + dx},{yy},{self.w // 2},{yy},0,320)\\fad(120,200)}}{txt}")

    def add_caption(self, start: float, end: float, text: str) -> None:
        if end - start < 0.1:
            return
        if self.subtitle_style == "highlight":
            words = text.split()
            total_cs = int((end - start) * 100)
            weights = [max(len(w), 2) for w in words]
            tw = sum(weights) or 1
            parts = [f"{{\\k{max(1, int(total_cs * wt / tw))}}}{esc(w)} " for w, wt in zip(words, weights)]
            body = "{\\fad(60,60)\\fscx92\\fscy92\\t(0,120,\\fscx100\\fscy100)}" + "".join(parts).rstrip()
        else:
            body = "{\\fad(60,60)}" + esc(text)
        self.events.append(f"Dialogue: 2,{ts(start)},{ts(end)},Caption,,0,0,0,,{body}")

    def add_end_card(self, start: float, end: float, text_y: float, headline: str, company: str, lines: list[str]) -> None:
        x = self.w // 2
        y = int(self.h * text_y)
        m = self.m
        if company:
            self.add_text(TextEvent(start, end, company, "EndName", x, y, "pop", delay=0.05))
            n, _ = self._lines(company, int(m * 0.12))
            y += int(n * m * 0.135 / 2 + m * 0.08)
        if headline:
            self.add_text(TextEvent(start, end, headline, "EndCta", x, y, "pop", delay=0.35))
            n, _ = self._lines(headline, int(m * 0.055))
            y += int(n * m * 0.065 / 2 + m * 0.11)
        for k, line in enumerate(lines):
            self.add_text(TextEvent(start, end, line, "EndInfo", x, y + k * int(m * 0.11), "slide_up", delay=0.45 + 0.12 * k))

    def add_watermark(self, total: float, text: str, position: str, opacity: float) -> None:
        align = {"top_right": 9, "top_left": 7, "bottom_right": 3, "bottom_left": 1}.get(position, 9)
        a = f"{int((1 - max(0.05, min(1.0, opacity))) * 255):02X}"
        self.events.append(
            f"Dialogue: 3,{ts(0)},{ts(total)},Watermark,,0,0,0,,{{\\an{align}\\1a&H{a}&\\3a&H{a}&\\4a&HFF&}}{esc(text)}")

    def render(self) -> str:
        return self.header() + "\n" + "\n".join(self.events) + "\n"
