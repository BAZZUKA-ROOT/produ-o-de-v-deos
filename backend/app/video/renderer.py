"""Motor de renderização: cenas (OpenCV) -> composição FFmpeg (xfade, ASS, marca d'água, mixagem)."""

import logging
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.catalog import resolution
from app.video import frames, motion, timeline
from app.video.ass import AssDoc, TextEvent

log = logging.getLogger(__name__)

ProgressCB = Callable[[float, str], None]


@dataclass
class ScenePlan:
    id: str
    image: Path
    duration: float
    transition: str = "fade"
    motion: str = "zoom_in"
    fit: str = "cover"
    title: str = ""
    subtitle: str = ""
    text_animation: str = "fade"
    text_position: str = "center"
    narration_text: str = ""
    caption_override: str = ""
    narration_audio: Path | None = None
    narration_duration: float | None = None
    role: str = "content"
    decor: bool = False


@dataclass
class EndCardPlan:
    enabled: bool = True
    duration: float = 4.0
    background: Path | None = None
    logo: Path | None = None
    headline: str = ""
    company: str = ""
    lines: list[str] = field(default_factory=list)


@dataclass
class RenderPlan:
    scenes: list[ScenePlan]
    format: str = "9:16"
    quality: str = "1080p"
    fps: int = 30
    target_duration: float | None = 30
    fit_duration: bool = True
    font: str = "Montserrat"
    visual_style: str = "moderno"
    palette: list[str] = field(default_factory=lambda: ["#111827", "#7C3AED", "#F472B6", "#FFFFFF"])
    subtitles: bool = True
    subtitle_style: str = "boxed"
    narration_enabled: bool = True
    narration_track: Path | None = None
    music: Path | None = None
    music_volume: float = 0.35
    watermark_text: str = ""
    watermark_image: Path | None = None
    watermark_position: str = "top_right"
    watermark_opacity: float = 0.6
    end_card: EndCardPlan = field(default_factory=EndCardPlan)
    x264_preset: str = "medium"
    crf: int = 20
    fonts_dir: Path | None = None


@dataclass
class RenderResult:
    path: Path
    duration: float
    width: int
    height: int
    timeline: dict
    thumbnail: Path | None
    warnings: list[str]


def _title_y(pos: str, h: int, w: int) -> int:
    vertical = h > w
    if pos == "top":
        return int(h * (0.2 if vertical else 0.18))
    if pos == "bottom":
        return int(h * (0.66 if vertical else 0.62))
    return int(h * (0.42 if vertical else 0.40))


def _overlay_xy(position: str, margin: int) -> str:
    return {
        "top_left": f"{margin}:{margin}",
        "bottom_left": f"{margin}:H-h-{margin}",
        "bottom_right": f"W-w-{margin}:H-h-{margin}",
    }.get(position, f"W-w-{margin}:{margin}")


def build_timeline(plan: RenderPlan) -> timeline.Timeline:
    return timeline.compute(
        [timeline.SceneIn(s.id, s.duration, s.transition, s.narration_text, s.caption_override, s.narration_duration)
         for s in plan.scenes],
        target=plan.target_duration,
        fit=plan.fit_duration,
        narration_enabled=plan.narration_enabled and plan.narration_track is None,
        subtitles_enabled=plan.subtitles,
        end_card_duration=plan.end_card.duration if plan.end_card.enabled else 0.0,
    )


def _upload_track_timeline(plan: RenderPlan, tl: timeline.Timeline) -> timeline.Timeline:
    """Narração enviada pelo usuário: legendas distribuídas pelo texto de cada cena."""
    if not plan.subtitles:
        return tl
    for sc, sp in zip(tl.scenes, plan.scenes):
        text = sp.caption_override.strip() or sp.narration_text.strip()
        if text:
            start = sc.start + 0.25
            sc.captions = timeline._captions_for(text, start, sc.duration - sc.trans_out - 0.4)
    return tl


def render(plan: RenderPlan, out_path: Path, work_dir: Path, progress: ProgressCB | None = None,
           should_cancel: Callable[[], bool] | None = None) -> RenderResult:
    if not plan.scenes:
        raise ValueError("projeto sem cenas")
    progress = progress or (lambda p, s: None)
    work_dir.mkdir(parents=True, exist_ok=True)
    w, h = resolution(plan.format, plan.quality)
    fps = plan.fps
    tl = build_timeline(plan)
    if plan.narration_track is not None:
        tl = _upload_track_timeline(plan, tl)
    warnings = list(tl.warnings)
    total = tl.total
    preview = plan.quality in ("360p", "540p")
    clip_preset, clip_crf = ("ultrafast", 22) if preview else ("veryfast", 16)

    # 1. Clipes de cena
    n = len(plan.scenes)
    clip_paths: list[Path] = []
    durations: list[float] = []
    total_frames = sum(s.duration for s in tl.scenes) + tl.end_card_duration
    done_s = 0.0

    def frame_cb(base: float, dur: float):
        def cb(i: int, nf: int):
            progress(0.05 + 0.55 * (base + dur * i / max(nf, 1)) / max(total_frames, 0.1), "Animando cenas")
        return cb

    for i, (sp, so) in enumerate(zip(plan.scenes, tl.scenes)):
        src = frames.prepare_source(sp.image, w, h, sp.fit, sp.motion)
        clip = work_dir / f"scene_{i:02d}.mp4"
        motion.render_clip(src, clip, w, h, so.duration, fps, sp.motion, clip_preset, clip_crf,
                           frame_cb(done_s, so.duration), should_cancel)
        clip_paths.append(clip)
        durations.append(so.duration)
        done_s += so.duration

    ec = plan.end_card
    if ec.enabled:
        bg = ec.background or plan.scenes[-1].image
        card_img, text_y = frames.end_card_image(work_dir / "endcard.jpg", w, h, plan.palette, ec.logo, bg)
        src = frames.prepare_source(card_img, w, h, "cover", "zoom_in")
        clip = work_dir / "endcard.mp4"
        motion.render_clip(src, clip, w, h, tl.end_card_duration, fps, "zoom_in", clip_preset, clip_crf,
                           frame_cb(done_s, tl.end_card_duration), should_cancel)
        clip_paths.append(clip)
        durations.append(tl.end_card_duration)
    else:
        text_y = 0.42

    # 2. Textos e legendas (ASS)
    progress(0.62, "Gerando textos e legendas")
    doc = AssDoc(w, h, plan.font, plan.palette, plan.subtitle_style, plan.visual_style)
    positions: set[str] = set()
    for sp, so in zip(plan.scenes, tl.scenes):
        y = _title_y(sp.text_position, h, w)
        end = so.start + so.duration - so.trans_out * 0.6
        start = so.start + (0.15 if so.start == 0 else 0.25)
        if sp.decor:
            doc.add_orbs(so.start, so.start + so.duration, hash(sp.id) & 0xFFFF)
        if sp.title or sp.subtitle:
            positions.add(sp.text_position)
        below = doc.add_title(start, end, sp.title, w // 2, y, sp.text_animation, sp.role) if sp.title else y
        if sp.subtitle:
            doc.add_subtitle(start, end, sp.subtitle, w // 2, below + int(min(w, h) * 0.03), sp.text_animation)
        for c in so.captions:
            doc.add_caption(c.start, min(c.end, end + 0.2), c.text)
    if ec.enabled and tl.end_card_start is not None:
        doc.add_end_card(tl.end_card_start + 0.3, total - 0.05, text_y, ec.headline, ec.company, ec.lines)
    if plan.watermark_text and not plan.watermark_image:
        doc.add_watermark(total, plan.watermark_text, plan.watermark_position, plan.watermark_opacity)
    ass_path = work_dir / "texts.ass"
    ass_path.write_text(doc.render(), encoding="utf-8")
    shade = frames.shade_overlay(work_dir / "shade.png", w, h, plan.subtitles, positions)

    # 3. Composição final
    inputs: list[str] = []
    for c in clip_paths:
        inputs += ["-i", str(c)]
    idx = len(clip_paths)
    inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(shade)]
    shade_idx = idx
    idx += 1
    wm_idx = None
    if plan.watermark_image:
        inputs += ["-loop", "1", "-framerate", str(fps), "-i", str(plan.watermark_image)]
        wm_idx = idx
        idx += 1

    fc: list[str] = []
    for i in range(len(clip_paths)):
        fc.append(f"[{i}:v]settb=AVTB,fps={fps},format=yuv420p,setsar=1[v{i}]")
    last = "v0"
    acc = durations[0]
    trans = [so.transition for so in tl.scenes] + []
    t_outs = [so.trans_out for so in tl.scenes]
    for i in range(1, len(clip_paths)):
        name = trans[i - 1] if i - 1 < len(trans) else "fade"
        name = "fade" if name in ("none", "", None) else name
        td = t_outs[i - 1]
        off = max(acc - td, 0.01)
        fc.append(f"[{last}][v{i}]xfade=transition={name}:duration={td:.3f}:offset={off:.3f}[x{i}]")
        last = f"x{i}"
        acc = acc + durations[i] - td
    fonts = str(plan.fonts_dir) if plan.fonts_dir else ""
    fc.append(f"[{shade_idx}:v]format=rgba[sh]")
    fc.append(f"[{last}][sh]overlay=0:0:shortest=1[vs]")
    ass_opt = f"ass=filename={_fesc(str(ass_path))}" + (f":fontsdir={_fesc(fonts)}" if fonts else "")
    fc.append(f"[vs]{ass_opt}[va]")
    vout = "va"
    if wm_idx is not None:
        size = int(min(w, h) * 0.16)
        op = max(0.05, min(1.0, plan.watermark_opacity))
        fc.append(f"[{wm_idx}:v]format=rgba,scale={size}:-1,colorchannelmixer=aa={op:.2f}[wm]")
        fc.append(f"[va][wm]overlay={_overlay_xy(plan.watermark_position, int(min(w, h) * 0.04))}:shortest=1[vw]")
        vout = "vw"
    fc.append(f"[{vout}]format=yuv420p[vout]")

    # Áudio
    narr_labels: list[str] = []
    if plan.narration_track is not None:
        inputs += ["-i", str(plan.narration_track)]
        fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,adelay=300|300[n0]")
        narr_labels.append("n0")
        idx += 1
    elif plan.narration_enabled:
        for sp, so in zip(plan.scenes, tl.scenes):
            if sp.narration_audio and so.narr_start is not None:
                inputs += ["-i", str(sp.narration_audio)]
                ms = int(so.narr_start * 1000)
                tempo = f",atempo={tl.tempo:.3f}" if tl.tempo > 1.001 else ""
                lbl = f"n{len(narr_labels)}"
                fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo{tempo},adelay={ms}|{ms}[{lbl}]")
                narr_labels.append(lbl)
                idx += 1
    music_lbl = None
    if plan.music:
        inputs += ["-stream_loop", "-1", "-i", str(plan.music)]
        vol = max(0.0, min(1.0, plan.music_volume))
        fade_st = max(total - 2.0, 0)
        fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
                  f"volume={vol:.3f},afade=t=in:d=0.8,afade=t=out:st={fade_st:.3f}:d=2[mus]")
        music_lbl = "mus"
        idx += 1
    if narr_labels:
        if len(narr_labels) > 1:
            fc.append("".join(f"[{l}]" for l in narr_labels) + f"amix=inputs={len(narr_labels)}:normalize=0[narr]")
        else:
            fc.append(f"[{narr_labels[0]}]anull[narr]")
        if music_lbl:
            fc.append("[narr]asplit=2[narr_a][narr_b]")
            fc.append("[mus][narr_b]sidechaincompress=threshold=0.02:ratio=9:attack=15:release=450:makeup=1[duck]")
            fc.append("[narr_a][duck]amix=inputs=2:normalize=0:duration=longest[amixed]")
        else:
            fc.append("[narr]anull[amixed]")
    elif music_lbl:
        fc.append("[mus]anull[amixed]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fc.append(f"[{idx}:a]anull[amixed]")
        idx += 1
    fc.append(f"[amixed]apad,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")

    preset = "veryfast" if preview else plan.x264_preset
    crf = 28 if preview else plan.crf
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
           "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-t", f"{total:.3f}", "-progress", "pipe:1", "-nostats", str(out_path)]
    (work_dir / "ffmpeg_cmd.txt").write_text(" ".join(cmd))
    progress(0.65, "Compondo vídeo final")
    _run_ffmpeg(cmd, total, lambda p: progress(0.65 + 0.33 * p, "Compondo vídeo final"), should_cancel, work_dir)

    thumb = work_dir / "thumb.jpg"
    first = tl.scenes[0]
    tpos = min(first.start + first.duration * 0.6, max(total - 0.1, 0))
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{tpos:.2f}", "-i", str(out_path), "-frames:v", "1",
                        "-vf", "scale=480:-2", str(thumb)], capture_output=True, timeout=60)
    progress(1.0, "Concluído")
    return RenderResult(out_path, total, w, h, tl.to_dict(), thumb if r.returncode == 0 else None, warnings)


def _fesc(p: str) -> str:
    return "'" + p.replace("\\", "/").replace("'", r"'\''").replace(":", r"\:") + "'"


def _run_ffmpeg(cmd: list[str], total: float, on_progress: Callable[[float], None],
                should_cancel: Callable[[], bool] | None, work_dir: Path) -> None:
    err_file = (work_dir / "ffmpeg_stderr.log").open("wb")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err_file, text=True)
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            m = re.match(r"out_time_(?:us|ms)=(\d+)", line.strip())
            if m and total > 0:
                on_progress(min(int(m.group(1)) / 1_000_000 / total, 1.0))
            if should_cancel and should_cancel():
                raise motion.Cancelled()
        rc = proc.wait(timeout=3600)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    finally:
        err_file.close()
    if rc != 0:
        err = (work_dir / "ffmpeg_stderr.log").read_text(errors="ignore")[-1500:]
        raise RuntimeError(f"FFmpeg falhou (código {rc}): {err}")


def cleanup(work_dir: Path) -> None:
    shutil.rmtree(work_dir, ignore_errors=True)
