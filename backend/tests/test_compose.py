import json
import subprocess

import numpy as np
from PIL import Image

from app.models import Scene
from app.services.pipeline import resolve_layout
from app.video import compose
from app.video.ass import AssDoc


def _product(path):
    img = np.zeros((400, 300, 4), np.uint8)
    img[60:340, 40:260] = (30, 120, 220, 255)
    Image.fromarray(img, "RGBA").save(path)
    return path


def test_resolve_layout_rules():
    sc = Scene(role="product", layout="auto", bullets="")
    assert resolve_layout(sc, True, 1, False) == "hero"
    assert resolve_layout(sc, False, 1, False) == "fullscreen"
    assert resolve_layout(Scene(role="offer", layout="auto", bullets=""), True, 1, False) == "price"
    assert resolve_layout(Scene(role="differential", layout="auto", bullets="a\nb"), True, 1, False) == "features"
    assert resolve_layout(Scene(role="hook", layout="auto", bullets=""), True, 4, False) == "gallery"
    assert resolve_layout(Scene(role="hook", layout="auto", bullets=""), False, 0, True) == "kinetic"
    assert resolve_layout(Scene(role="cta", layout="price", bullets=""), False, 0, False) == "fullscreen"


def test_render_product_layouts(tmp_path):
    prod = _product(tmp_path / "p.png")
    photo = tmp_path / "photo.jpg"
    Image.new("RGB", (640, 480), (200, 80, 40)).save(photo)
    pal = ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"]
    for layout in ("hero", "price", "features", "cta", "gallery", "kinetic"):
        spec = compose.SceneSpec(layout, 1.0, pal, prod, [photo, photo, photo])
        out = compose.render_scene(spec, tmp_path / f"{layout}.mp4", 360, 640, 24, "ultrafast", 28)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(out)],
                                         capture_output=True).stdout)
        assert info["streams"][0]["width"] == 360


def test_ass_price_badge_and_bullets():
    doc = AssDoc(1080, 1920, "Poppins", ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"], "highlight", "moderno")
    doc.add_title(0, 3, "R$ 199,90 só esta semana", 540, 300, "pop", "offer", badge_at=(700, 1200))
    doc.add_bullets(0, 3, ["Frete grátis", "Troca fácil"], 540, 1200)
    doc.add_kinetic(0, 3, "Entrega grátis hoje", 800)
    text = doc.render()
    assert "Badge" in text and "R$ 199,90" in text and "Só esta semana" in text
    assert text.count("Bullet") >= 3
    assert "\a" not in text
