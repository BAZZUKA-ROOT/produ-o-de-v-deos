"""Catálogo de opções de vídeo compartilhado entre API, IA e renderizador."""

FORMATS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "4:5": (1080, 1350),
}
QUALITIES = {"360p": 360, "540p": 540, "720p": 720, "1080p": 1080}
DURATIONS = (15, 30, 45, 60)
STYLES = {
    "profissional": "Profissional",
    "moderno": "Moderno",
    "comercial": "Comercial",
    "elegante": "Elegante",
    "tecnologico": "Tecnológico",
    "criativo": "Criativo",
}
VIDEO_TYPES = {
    "anuncio": "Anúncio",
    "promocao": "Promoção",
    "apresentacao": "Apresentação",
    "institucional": "Institucional",
    "produto": "Divulgação de produto",
}
TRANSITIONS = [
    "none", "fade", "fadeblack", "fadewhite", "dissolve", "slideleft", "slideright", "slideup", "slidedown",
    "wipeleft", "wiperight", "smoothleft", "smoothright", "circleopen", "circleclose", "radial", "zoomin",
    "pixelize", "hblur", "diagtl", "squeezeh",
]
MOTIONS = ["none", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "zoom_in_left", "zoom_in_right"]
TEXT_ANIMATIONS = ["none", "fade", "slide_up", "slide_left", "pop", "typewriter", "blur_in"]
TEXT_POSITIONS = ["top", "center", "bottom"]
FITS = ["cover", "contain_blur"]
SCENE_ROLES = ["hook", "problem", "product", "benefit", "differential", "offer", "social_proof", "content", "cta"]
VOICES = {
    "kokoro": {"female": "pf_dora", "male": "pm_alex", "male_alt": "pm_santa"},
    "piper": {"male": "faber"},
    "espeak": {"female": "pt-br+f3", "male": "pt-br+m3"},
}
MUSIC_MOODS = {
    "upbeat": "Animada",
    "corporate": "Corporativa",
    "elegant": "Elegante",
    "tech": "Tecnológica",
    "chill": "Tranquila",
    "energetic": "Energética",
}
SUBTITLE_STYLES = ["clean", "boxed", "highlight", "bold_outline"]

STYLE_PRESETS = {
    "profissional": {"font": "Montserrat", "transition": "fade", "motion": "zoom_in", "animation": "fade",
                      "palette": ["#0F172A", "#1E3A8A", "#38BDF8", "#FFFFFF"], "music": "corporate"},
    "moderno": {"font": "Poppins", "transition": "slideleft", "motion": "zoom_in", "animation": "slide_up",
                "palette": ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"], "music": "upbeat"},
    "comercial": {"font": "Anton", "transition": "wipeleft", "motion": "zoom_in", "animation": "pop",
                  "palette": ["#7F1D1D", "#DC2626", "#FACC15", "#FFFFFF"], "music": "energetic"},
    "elegante": {"font": "DM Serif Display", "transition": "dissolve", "motion": "zoom_out", "animation": "fade",
                 "palette": ["#1C1917", "#57534E", "#D4AF37", "#FAFAF9"], "music": "elegant"},
    "tecnologico": {"font": "Audiowide", "transition": "pixelize", "motion": "pan_left", "animation": "typewriter",
                    "palette": ["#020617", "#0E7490", "#22D3EE", "#E0F2FE"], "music": "tech"},
    "criativo": {"font": "Bebas Neue", "transition": "circleopen", "motion": "zoom_in_right", "animation": "pop",
                 "palette": ["#1E1B4B", "#F97316", "#FDE047", "#FFFFFF"], "music": "upbeat"},
}

FONT_FILES = {
    "Montserrat": "Montserrat-ExtraBold.ttf",
    "Poppins": "Poppins-Bold.ttf",
    "Anton": "Anton-Regular.ttf",
    "DM Serif Display": "DMSerifDisplay-Regular.ttf",
    "Audiowide": "Audiowide-Regular.ttf",
    "Bebas Neue": "BebasNeue-Regular.ttf",
    "Pacifico": "Pacifico-Regular.ttf",
}
BODY_FONT_FILE = "Montserrat-SemiBold.ttf"


def resolution(fmt: str, quality: str) -> tuple[int, int]:
    w, h = FORMATS.get(fmt, FORMATS["9:16"])
    short = QUALITIES.get(quality, 1080)
    scale = short / min(w, h)
    rw, rh = int(round(w * scale / 2) * 2), int(round(h * scale / 2) * 2)
    return rw, rh


def default_project_settings(style: str = "moderno") -> dict:
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["moderno"])
    return {
        "format": "9:16",
        "duration": 30,
        "style": style,
        "video_type": "anuncio",
        "quality": "1080p",
        "music_asset_id": None,
        "music_mood": preset["music"],
        "music_volume": 0.35,
        "narration_enabled": True,
        "narration_mode": "tts",  # tts | upload
        "narration_asset_id": None,
        "tts_provider": None,
        "voice_gender": "female",
        "voice_speed": 1.0,
        "subtitles_enabled": True,
        "subtitle_style": "highlight",
        "font": preset["font"],
        "palette": preset["palette"],
        "watermark": {"enabled": False, "type": "text", "text": "", "asset_id": None, "position": "top_right",
                      "opacity": 0.6},
        "end_card": {"enabled": True, "duration": 4.0, "show_phone": True, "show_instagram": True,
                     "show_address": True, "headline": ""},
        "logo_asset_id": None,
        "photo_asset_ids": [],
        "fit_duration": True,
    }
