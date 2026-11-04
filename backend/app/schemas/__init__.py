import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.catalog import (
    DURATIONS,
    FITS,
    FORMATS,
    MOTIONS,
    QUALITIES,
    STYLES,
    SUBTITLE_STYLES,
    TEXT_ANIMATIONS,
    TEXT_POSITIONS,
    TRANSITIONS,
    VIDEO_TYPES,
)

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _password_ok(v: str) -> str:
    if len(v) < 8 or not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("a senha deve ter ao menos 8 caracteres, com letras e números")
    return v


class RegisterIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(max_length=128)

    _pw = field_validator("password")(_password_ok)


class LoginIn(Strict):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(max_length=128)


class ProfileIn(Strict):
    name: str = Field(min_length=2, max_length=120)


class PasswordChangeIn(Strict):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

    _pw = field_validator("new_password")(_password_ok)


class CompanyIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    segment: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=2000)
    product: str = Field(default="", max_length=300)
    offer: str = Field(default="", max_length=300)
    audience: str = Field(default="", max_length=300)
    differentials: str = Field(default="", max_length=1000)
    phone: str = Field(default="", max_length=40)
    whatsapp: str = Field(default="", max_length=40)
    instagram: str = Field(default="", max_length=60)
    address: str = Field(default="", max_length=300)
    website: str = Field(default="", max_length=200)


class WatermarkIn(Strict):
    enabled: bool = False
    type: Literal["text", "image"] = "text"
    text: str = Field(default="", max_length=60)
    asset_id: uuid.UUID | None = None
    position: Literal["top_right", "top_left", "bottom_right", "bottom_left"] = "top_right"
    opacity: float = Field(default=0.6, ge=0.05, le=1.0)


class EndCardIn(Strict):
    enabled: bool = True
    duration: float = Field(default=4.0, ge=2.0, le=10.0)
    show_phone: bool = True
    show_instagram: bool = True
    show_address: bool = True
    headline: str = Field(default="", max_length=120)


class ProjectSettingsIn(Strict):
    format: str | None = None
    duration: int | None = None
    style: str | None = None
    video_type: str | None = None
    quality: str | None = None
    music_asset_id: uuid.UUID | None = None
    music_mood: str | None = None
    music_volume: float | None = Field(default=None, ge=0.0, le=1.0)
    narration_enabled: bool | None = None
    narration_mode: Literal["tts", "upload"] | None = None
    narration_asset_id: uuid.UUID | None = None
    tts_provider: Literal["kokoro", "piper", "espeak"] | None = None
    voice_gender: Literal["female", "male"] | None = None
    voice_speed: float | None = Field(default=None, ge=0.6, le=1.6)
    subtitles_enabled: bool | None = None
    subtitle_style: str | None = None
    font: str | None = None
    palette: list[str] | None = None
    watermark: WatermarkIn | None = None
    end_card: EndCardIn | None = None
    logo_asset_id: uuid.UUID | None = None
    fit_duration: bool | None = None
    photo_asset_ids: list[uuid.UUID] | None = Field(default=None, max_length=20)

    @field_validator("format")
    @classmethod
    def _fmt(cls, v):
        if v is not None and v not in FORMATS:
            raise ValueError("formato inválido")
        return v

    @field_validator("duration")
    @classmethod
    def _dur(cls, v):
        if v is not None and v not in DURATIONS:
            raise ValueError("duração deve ser 15, 30, 45 ou 60")
        return v

    @field_validator("style")
    @classmethod
    def _style(cls, v):
        if v is not None and v not in STYLES:
            raise ValueError("estilo inválido")
        return v

    @field_validator("video_type")
    @classmethod
    def _vt(cls, v):
        if v is not None and v not in VIDEO_TYPES:
            raise ValueError("tipo de vídeo inválido")
        return v

    @field_validator("quality")
    @classmethod
    def _q(cls, v):
        if v is not None and v not in QUALITIES:
            raise ValueError("qualidade inválida")
        return v

    @field_validator("subtitle_style")
    @classmethod
    def _ss(cls, v):
        if v is not None and v not in SUBTITLE_STYLES:
            raise ValueError("estilo de legenda inválido")
        return v

    @field_validator("palette")
    @classmethod
    def _pal(cls, v):
        if v is not None and (len(v) != 4 or not all(HEX.match(c) for c in v)):
            raise ValueError("paleta deve conter 4 cores hexadecimais")
        return v


class ProjectCreateIn(Strict):
    name: str | None = Field(default=None, max_length=200)
    template_id: uuid.UUID | None = None
    company: CompanyIn
    settings: ProjectSettingsIn = ProjectSettingsIn()


class ProjectUpdateIn(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    company: CompanyIn | None = None
    settings: ProjectSettingsIn | None = None
    script: dict[str, Any] | None = None


class SceneIn(Strict):
    role: str | None = Field(default=None, max_length=30)
    title: str | None = Field(default=None, max_length=300)
    subtitle: str | None = Field(default=None, max_length=300)
    narration: str | None = Field(default=None, max_length=1500)
    caption_override: str | None = Field(default=None, max_length=1500)
    image_prompt: str | None = Field(default=None, max_length=1000)
    duration: float | None = Field(default=None, ge=1.0, le=30.0)
    transition: str | None = None
    motion: str | None = None
    text_animation: str | None = None
    text_position: str | None = None
    fit: str | None = None
    layout: str | None = None
    bullets: str | None = Field(default=None, max_length=600)
    image_asset_id: uuid.UUID | None = None
    clear_image: bool | None = None

    @field_validator("transition")
    @classmethod
    def _t(cls, v):
        if v is not None and v not in TRANSITIONS:
            raise ValueError("transição inválida")
        return v

    @field_validator("motion")
    @classmethod
    def _m(cls, v):
        if v is not None and v not in MOTIONS:
            raise ValueError("movimento inválido")
        return v

    @field_validator("text_animation")
    @classmethod
    def _a(cls, v):
        if v is not None and v not in TEXT_ANIMATIONS:
            raise ValueError("animação inválida")
        return v

    @field_validator("text_position")
    @classmethod
    def _p(cls, v):
        if v is not None and v not in TEXT_POSITIONS:
            raise ValueError("posição inválida")
        return v

    @field_validator("layout")
    @classmethod
    def _l(cls, v):
        from app.video.compose import LAYOUTS

        if v is not None and v not in LAYOUTS:
            raise ValueError("layout inválido")
        return v

    @field_validator("fit")
    @classmethod
    def _f(cls, v):
        if v is not None and v not in FITS:
            raise ValueError("enquadramento inválido")
        return v


class SceneCreateIn(SceneIn):
    position: int | None = Field(default=None, ge=0)


class ReorderIn(Strict):
    scene_ids: list[uuid.UUID]


class ImagesJobIn(Strict):
    scene_ids: list[uuid.UUID] | None = None
    force: bool = False


class NarrationJobIn(Strict):
    force: bool = False


class AssetUpdateIn(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    in_library: bool | None = None


class AdminUserCreateIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(max_length=128)
    role: Literal["user", "admin"] = "user"
    quota_mb: int | None = Field(default=None, ge=0)

    _pw = field_validator("password")(_password_ok)


class AdminUserUpdateIn(Strict):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None
    quota_mb: int | None = Field(default=None, ge=0)
    password: str | None = Field(default=None, max_length=128)

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        return _password_ok(v) if v else v


class TemplateIn(Strict):
    slug: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9_-]+$")
    category: str = Field(min_length=2, max_length=60)
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    style: str
    video_type: str
    config: dict[str, Any]
    is_active: bool = True

    @field_validator("style")
    @classmethod
    def _s(cls, v):
        if v not in STYLES:
            raise ValueError("estilo inválido")
        return v

    @field_validator("video_type")
    @classmethod
    def _vt(cls, v):
        if v not in VIDEO_TYPES:
            raise ValueError("tipo inválido")
        return v


class SettingsUpdateIn(BaseModel):
    values: dict[str, Any]


class ModelPullIn(Strict):
    model: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9._:/-]+$")
