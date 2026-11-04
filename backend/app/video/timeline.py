"""Cálculo de linha do tempo: durações efetivas, sincronia de narração, legendas e ajuste de duração.

Usado pelo renderizador e pela pré-visualização do editor (mesma fonte de verdade).
"""

import re
from dataclasses import asdict, dataclass, field

TRANSITION_DURATION = 0.5
CUT_DURATION = 0.04
NARR_LEAD = 0.3
NARR_TAIL = 0.35
MIN_SCENE = 1.5
MAX_TEMPO = 1.2


@dataclass
class SceneIn:
    id: str
    duration: float
    transition: str = "fade"
    narration: str = ""
    caption_override: str = ""
    narration_duration: float | None = None


@dataclass
class Caption:
    start: float
    end: float
    text: str


@dataclass
class SceneOut:
    id: str
    start: float
    duration: float
    trans_out: float
    transition: str
    narr_start: float | None
    narr_duration: float | None
    captions: list[Caption] = field(default_factory=list)


@dataclass
class Timeline:
    total: float
    tempo: float
    scenes: list[SceneOut]
    end_card_start: float | None
    end_card_duration: float
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def trans_duration(name: str) -> float:
    return CUT_DURATION if name in ("none", "", None) else TRANSITION_DURATION


def split_captions(text: str, max_words: int = 5, max_chars: int = 30) -> list[str]:
    # mantém telefones como "(11) 98765-4321" em um único bloco
    text = re.sub(r"(\(\d{2}\))\s+(?=\d)", "\\1\u00a0", re.sub(r"\s+", " ", text).strip())
    words = text.split(" ")
    chunks: list[str] = []
    cur: list[str] = []
    for w in words:
        if not w:
            continue
        cand = " ".join(cur + [w])
        if cur and (len(cur) >= max_words or len(cand) > max_chars):
            chunks.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
        if re.search(r"[.!?;:]$", w) and len(cur) >= 2:
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _captions_for(text: str, start: float, dur: float) -> list[Caption]:
    chunks = split_captions(text)
    if not chunks or dur <= 0:
        return []
    weights = [max(len(c), 4) for c in chunks]
    total_w = sum(weights)
    out, t = [], start
    for c, w in zip(chunks, weights):
        d = dur * w / total_w
        out.append(Caption(round(t, 3), round(t + d, 3), c))
        t += d
    return out


def compute(
    scenes: list[SceneIn],
    *,
    target: float | None,
    fit: bool,
    narration_enabled: bool,
    subtitles_enabled: bool,
    end_card_duration: float = 0.0,
    end_card_transition: str = "fade",
) -> Timeline:
    warnings: list[str] = []
    n = len(scenes)
    has_end = end_card_duration > 0
    t_out = []
    for i, s in enumerate(scenes):
        if i < n - 1:
            t_out.append(trans_duration(s.transition))
        else:
            t_out.append(trans_duration(end_card_transition) if has_end else 0.0)
    t_in = [0.0] + t_out[:-1]

    def narr_dur(i: int, tempo: float) -> float:
        d = scenes[i].narration_duration if narration_enabled else None
        return (d or 0.0) / tempo

    def min_required(i: int, tempo: float) -> float:
        nd = narr_dur(i, tempo)
        if nd <= 0:
            return max(MIN_SCENE, t_in[i] + t_out[i] + 0.5)
        return max(MIN_SCENE, max(NARR_LEAD, t_in[i] * 0.6) + nd + NARR_TAIL + t_out[i] * 0.4)

    def total_of(durs: list[float]) -> float:
        return sum(durs) - sum(t_out) + (end_card_duration if has_end else 0.0)

    tempo = 1.0
    durs = [max(float(s.duration or 0), min_required(i, tempo)) for i, s in enumerate(scenes)]
    if any(float(s.duration or 0) < min_required(i, 1.0) - 1e-6 for i, s in enumerate(scenes)):
        warnings.append("Algumas cenas foram estendidas para caber a narração.")

    if fit and target:
        total = total_of(durs)
        if total > target + 0.05:
            # 1) remove folgas
            excess = total - target
            for i in range(n):
                slack = durs[i] - min_required(i, tempo)
                cut = min(slack, excess)
                durs[i] -= cut
                excess -= cut
            # 2) acelera narração (até MAX_TEMPO)
            if excess > 0.05 and narration_enabled:
                narr_total = sum(narr_dur(i, 1.0) for i in range(n))
                if narr_total > 0:
                    tempo = min(MAX_TEMPO, max(1.0, narr_total / max(narr_total - excess, 0.1)))
                    durs = [min_required(i, tempo) for i in range(n)]
                    if tempo > 1.0:
                        warnings.append(f"Narração acelerada em {tempo:.2f}x para caber em {target:.0f}s.")
            final = total_of(durs)
            if final > target + 0.5:
                warnings.append(f"O vídeo ficou com {final:.1f}s (alvo {target:.0f}s). Reduza o texto da narração.")
        elif total < target - 0.05:
            extra = target - total
            weight = sum(durs) or 1.0
            durs = [d + extra * d / weight for d in durs]

    out: list[SceneOut] = []
    t = 0.0
    for i, s in enumerate(scenes):
        d = round(durs[i], 3)
        nd = narr_dur(i, tempo)
        narr_start = round(t + max(NARR_LEAD, t_in[i] * 0.6), 3) if nd > 0 else None
        caps: list[Caption] = []
        if subtitles_enabled:
            text = s.caption_override.strip() or (s.narration.strip() if narration_enabled else "")
            if text:
                if narr_start is not None:
                    caps = _captions_for(text, narr_start, nd)
                elif s.caption_override.strip():
                    caps = _captions_for(text, t + t_in[i] * 0.5 + 0.2, d - t_in[i] * 0.5 - t_out[i] - 0.3)
        out.append(SceneOut(s.id, round(t, 3), d, round(t_out[i], 3), s.transition or "none", narr_start,
                            round(nd, 3) if nd > 0 else None, caps))
        t += d - t_out[i]
    end_start = round(t, 3) if has_end else None
    total = round(t + (end_card_duration if has_end else 0.0), 3)
    return Timeline(total, round(tempo, 3), out, end_start, end_card_duration if has_end else 0.0, warnings)
