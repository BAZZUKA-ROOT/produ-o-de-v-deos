"""Geração de legendas/textos animados em ASS (renderizados pelo libass dentro do FFmpeg)."""

from dataclasses import dataclass, field

UPPERCASE_FONTS = {"Anton", "Bebas Neue"}


def ass_color(hex_color: str, alpha: float = 0.0) -> str:
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = int(max(0.0, min(1.0, alpha)) * 255)
    return f"&H{a:02X}{b}{g}{r}".upper()


def ts(t: float) -> str:
    t = max(t, 0.0)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    cs = int(round((s - int(s)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def esc(text: str) -> str:
    return (text or "").replace("\\", "⧵").replace("{", "(").replace("}", ")").replace("\n", "\\N")


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


@dataclass
class AssDoc:
    w: int
    h: int
    font: str
    palette: list[str]
    subtitle_style: str = "boxed"
    events: list[str] = field(default_factory=list)

    @property
    def m(self) -> int:
        return min(self.w, self.h)

    def header(self) -> str:
        pal = (self.palette + ["#111111", "#333333", "#FACC15", "#FFFFFF"])[:4]
        primary_text = ass_color(pal[3] if pal[3] else "#FFFFFF")
        accent = ass_color(pal[2])
        dark = ass_color("#000000", 0.0)
        box = ass_color(pal[0], 0.25)
        m = self.m
        title_size = int(m * (0.115 if self.font in UPPERCASE_FONTS else 0.092))
        sub_size = int(m * 0.05)
        cap_size = int(m * 0.06)
        end_name = int(m * 0.10)
        end_info = int(m * 0.05)
        ml = int(self.w * 0.08)
        cap_border, cap_outline, cap_back = 1, max(2, m // 220), ass_color("#000000", 0.4)
        cap_primary, cap_secondary = primary_text, primary_text
        if self.subtitle_style == "boxed":
            cap_border, cap_outline, cap_back = 3, max(6, m // 90), box
        elif self.subtitle_style == "highlight":
            cap_primary, cap_secondary = accent, primary_text
        elif self.subtitle_style == "bold_outline":
            cap_outline = max(5, m // 110)
        o = max(2, m // 260)
        styles = [
            f"Style: Title,{self.font},{title_size},{primary_text},{primary_text},{dark},{ass_color('#000000', 0.45)},"
            f"-1,0,0,0,100,100,1,0,1,{o + 1},{o + 1},5,{ml},{ml},10,1",
            f"Style: Subtitle,Montserrat SemiBold,{sub_size},{accent},{accent},{dark},{ass_color('#000000', 0.5)},"
            f"0,0,0,0,100,100,0,0,1,{o},{o},5,{ml},{ml},10,1",
            f"Style: Caption,Montserrat ExtraBold,{cap_size},{cap_primary},{cap_secondary},{dark},{cap_back},"
            f"-1,0,0,0,100,100,0,0,{cap_border},{cap_outline},{o},2,{ml},{ml},{int(self.h * 0.1)},1",
            f"Style: EndName,{self.font},{end_name},{primary_text},{primary_text},{dark},{ass_color('#000000', 0.5)},"
            f"-1,0,0,0,100,100,1,0,1,{o + 1},{o + 1},5,{ml},{ml},10,1",
            f"Style: EndHead,Montserrat ExtraBold,{int(end_info * 1.15)},{accent},{accent},{dark},{ass_color('#000000', 0.5)},"
            f"-1,0,0,0,100,100,1,0,1,{o},{o},5,{ml},{ml},10,1",
            f"Style: EndInfo,Montserrat SemiBold,{end_info},{primary_text},{primary_text},{dark},{box},"
            f"0,0,0,0,100,100,0,0,3,{max(8, m // 70)},0,5,{ml},{ml},10,1",
            f"Style: Watermark,Montserrat SemiBold,{int(m * 0.032)},{ass_color('#FFFFFF', 0.35)},{primary_text},"
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

    def _anim(self, anim: str, x: int, y: int, dur_ms: int, text: str) -> str:
        out_ms = 220
        if anim == "slide_up":
            d = int(self.m * 0.06)
            return f"{{\\fad(200,{out_ms})\\move({x},{y + d},{x},{y},0,380)}}{text}"
        if anim == "slide_left":
            d = int(self.w * 0.18)
            return f"{{\\fad(150,{out_ms})\\move({x + d},{y},{x},{y},0,380)}}{text}"
        if anim == "pop":
            return (f"{{\\pos({x},{y})\\fad(80,{out_ms})\\fscx40\\fscy40\\t(0,200,\\fscx112\\fscy112)"
                    f"\\t(200,320,\\fscx100\\fscy100)}}{text}")
        if anim == "blur_in":
            return f"{{\\pos({x},{y})\\fad(150,{out_ms})\\blur18\\t(0,450,\\blur0)}}{text}"
        if anim == "typewriter":
            chars = list(text.replace("\\N", "\n"))
            per = max(2, min(8, int(min(dur_ms * 0.4, 1600) / 10 / max(len(chars), 1))))
            body = "".join(("\\N" if c == "\n" else f"{{\\ko{per}}}{c}") for c in chars)
            return f"{{\\pos({x},{y})\\fad(0,{out_ms})}}{body}"
        if anim == "none":
            return f"{{\\pos({x},{y})}}{text}"
        return f"{{\\pos({x},{y})\\fad(300,{out_ms})}}{text}"

    def add_text(self, ev: TextEvent) -> None:
        start = ev.start + ev.delay
        if ev.end - start < 0.2 or not ev.text.strip():
            return
        text = esc(ev.text.upper() if ev.style in ("Title", "EndName") and self.font in UPPERCASE_FONTS else ev.text)
        body = self._anim(ev.animation, ev.x, ev.y, int((ev.end - start) * 1000), text)
        self.events.append(f"Dialogue: 1,{ts(start)},{ts(ev.end)},{ev.style},,0,0,0,,{body}")

    def add_caption(self, start: float, end: float, text: str) -> None:
        if end - start < 0.1:
            return
        if self.subtitle_style == "highlight":
            words = text.split()
            total_cs = int((end - start) * 100)
            weights = [max(len(w), 2) for w in words]
            tw = sum(weights) or 1
            parts = [f"{{\\k{max(1, int(total_cs * wt / tw))}}}{esc(w)} " for w, wt in zip(words, weights)]
            body = "{\\fad(60,60)}" + "".join(parts).rstrip()
        else:
            body = "{\\fad(60,60)}" + esc(text)
        self.events.append(f"Dialogue: 2,{ts(start)},{ts(end)},Caption,,0,0,0,,{body}")

    def add_watermark(self, total: float, text: str, position: str, opacity: float) -> None:
        align = {"top_right": 9, "top_left": 7, "bottom_right": 3, "bottom_left": 1}.get(position, 9)
        a = f"{int((1 - max(0.05, min(1.0, opacity))) * 255):02X}"
        self.events.append(
            f"Dialogue: 3,{ts(0)},{ts(total)},Watermark,,0,0,0,,{{\\an{align}\\1a&H{a}&\\3a&H{a}&\\4a&HFF&}}{esc(text)}")

    def render(self) -> str:
        return self.header() + "\n" + "\n".join(self.events) + "\n"
