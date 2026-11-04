"""Geração de roteiro comercial: Ollama (LLM local) com fallback determinístico baseado em templates."""

import json
import logging
import re
from typing import Any

import httpx

from app.core.catalog import SCENE_ROLES, STYLES, VIDEO_TYPES

log = logging.getLogger(__name__)
WORDS_PER_SECOND = 2.4

SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "analysis": {"type": "string"},
        "hook": {"type": "string"},
        "cta": {"type": "string"},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": ["hook", "problem", "product", "benefit", "differential",
                                                        "offer", "social_proof", "content", "cta"]},
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                    "narration": {"type": "string"},
                    "image_prompt": {"type": "string"},
                    "duration": {"type": "number"},
                },
                "required": ["role", "title", "narration", "image_prompt", "duration"],
            },
        },
    },
    "required": ["title", "hook", "cta", "scenes"],
}


class LLMError(RuntimeError):
    pass


def _clean(s: Any, limit: int = 400) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()[:limit]


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _company_ctx(company: dict) -> dict[str, str]:
    diffs = [d.strip() for d in re.split(r"[,;\n]", company.get("differentials") or "") if d.strip()]
    nome = _clean(company.get("name")) or "nossa empresa"
    produto = _clean(company.get("product")) or _clean(company.get("segment")) or "nossos serviços"
    oferta = _clean(company.get("offer"))
    desc = _clean(company.get("description"), 300)
    contatos = []
    if company.get("whatsapp") or company.get("phone"):
        contatos.append(f"Chame no WhatsApp {company.get('whatsapp') or company.get('phone')}")
    if company.get("instagram"):
        contatos.append(f"siga @{str(company['instagram']).lstrip('@')}")
    first_sentence = re.split(r"(?<=[.!?])\s", desc)[0] if desc else ""
    return {
        "empresa": nome,
        "produto": produto,
        "oferta": oferta or "Condições especiais",
        "oferta_frase": (f"Aproveite: {oferta}." if oferta else f"Condições especiais para você na {nome}."),
        "publico": _clean(company.get("audience")) or "você",
        "segmento": _clean(company.get("segment")),
        "diferencial_1": diffs[0] if diffs else "Qualidade garantida",
        "diferenciais_frase": (
            "Aqui você encontra " + ", ".join(diffs[:3]) + "." if diffs else f"Na {nome}, qualidade vem em primeiro lugar."
        ),
        "descricao_curta": first_sentence or f"{produto} com a qualidade que você merece.",
        "contato_frase": (", ".join(contatos) + ".") if contatos else "",
        "endereco": _clean(company.get("address")),
    }


def _fill(text: str, ctx: dict[str, str]) -> str:
    try:
        return _clean(text.format(**ctx), 300)
    except (KeyError, IndexError, ValueError):
        return _clean(text, 300)


def fallback_script(company: dict, settings: dict, template_cfg: dict | None) -> dict:
    from app.seed.templates import CATEGORIES, _blueprint

    cfg = template_cfg or {}
    ctx = _company_ctx(company)
    cta = cfg.get("cta") or "Fale com a gente pelo WhatsApp!"
    ctx["cta"] = cta
    blueprint = cfg.get("blueprint")
    if not blueprint:
        cat = CATEGORIES["empresas"]
        blueprint = _blueprint(cat, settings.get("video_type", "anuncio"))
    image_style = cfg.get("image_style", "professional commercial photography, high quality")
    n = scene_count(settings, len(blueprint))
    if len(blueprint) > n:
        blueprint = blueprint[: n - 1] + [blueprint[-1]]
    scenes = []
    for b in blueprint:
        scenes.append({
            "role": b["role"],
            "title": _fill(b["title"], ctx),
            "subtitle": "",
            "narration": _fill(b["narration"], ctx),
            "image_prompt": f"{b['image']}, {image_style}",
            "duration": b.get("share", 0.2),
        })
    script = {
        "title": f"{ctx['empresa']} — {VIDEO_TYPES.get(settings.get('video_type', ''), 'Vídeo')}",
        "analysis": "Roteiro gerado pelo modo template (sem LLM).",
        "hook": scenes[0]["title"] if scenes else "",
        "cta": cta,
        "caption": f"{ctx['empresa']}: {ctx['descricao_curta']} {ctx['contato_frase']}".strip(),
        "hashtags": ["#" + re.sub(r"[^\w]", "", ctx["empresa"].lower()), "#promocao", "#oferta"],
        "scenes": scenes,
        "engine": "template",
    }
    return normalize_script(script, settings)


def _target_scene_seconds(settings: dict) -> float:
    total = float(settings.get("duration", 30))
    end = settings.get("end_card", {})
    if end.get("enabled", True):
        total -= float(end.get("duration", 4.0))
    return max(total, 6.0)


def scene_count(settings: dict, blueprint_len: int = 0) -> int:
    target = _target_scene_seconds(settings)
    cap = max(3, min(8, round(target / 4.5)))
    return min(blueprint_len, cap) if blueprint_len else cap


def _fit_sentences(text: str, max_words: int) -> str:
    """Mantém apenas frases completas que caibam no limite (nunca corta no meio da frase)."""
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    out: list[str] = []
    count = 0
    for snt in sentences:
        n = len(snt.split())
        if out and count + n > max_words:
            break
        out.append(snt)
        count += n
    return " ".join(out) if out else text


def normalize_script(script: dict, settings: dict) -> dict:
    scenes = [s for s in script.get("scenes", []) if isinstance(s, dict)][:10]
    if not scenes:
        raise LLMError("roteiro sem cenas")
    target = _target_scene_seconds(settings)
    budget = int(target * WORDS_PER_SECOND)
    per_scene_budget = max(6, int(budget / len(scenes) * 1.3))
    cleaned = []
    for s in scenes:
        narration = _fit_sentences(_clean(s.get("narration"), 600), per_scene_budget)
        role = _clean(s.get("role"), 30).lower()
        cleaned.append({
            "role": role if role in SCENE_ROLES else "content",
            "title": _cap(_clean(s.get("title"), 120)),
            "subtitle": _clean(s.get("subtitle"), 160),
            "narration": narration,
            "image_prompt": _clean(s.get("image_prompt"), 500),
        })
    if cleaned[-1]["role"] != "cta" and len(cleaned) > 1:
        cleaned[-1]["role"] = "cta"
    # duração proporcional ao texto falado (mín. 2s por cena), escalada para o alvo
    weights = [max(len(c["narration"].split()) / WORDS_PER_SECOND + 0.8, 2.0) for c in cleaned]
    total_w = sum(weights)
    for c, w in zip(cleaned, weights):
        c["duration"] = round(max(2.0, target * w / total_w), 2)
    script["scenes"] = cleaned
    script["title"] = _clean(script.get("title"), 200) or "Vídeo promocional"
    script["hook"] = _clean(script.get("hook"), 200)
    script["cta"] = _clean(script.get("cta"), 200)
    script["caption"] = _clean(script.get("caption"), 600)
    script["hashtags"] = [_clean(h, 40) for h in (script.get("hashtags") or [])][:12]
    script["narration_full"] = " ".join(c["narration"] for c in cleaned)
    return script


def enrich_script(script: dict, template_cfg: dict | None) -> dict:
    """Completa lacunas comuns em modelos pequenos (títulos vazios, prompts de imagem pobres)."""
    cfg = template_cfg or {}
    hints = {b["role"]: b.get("image", "") for b in cfg.get("blueprint", [])}
    style = cfg.get("image_style", "professional commercial photography, high quality")
    for sc in script["scenes"]:
        if not sc["title"]:
            words = re.sub(r"[.!?]+$", "", sc["narration"]).split()
            sc["title"] = _cap(" ".join(words[:6]))
        if len(sc["image_prompt"].split()) < 6:
            hint = hints.get(sc["role"]) or next(iter(hints.values()), "")
            sc["image_prompt"] = ", ".join(x for x in (sc["image_prompt"], hint, style) if x)
    return script


SYSTEM_PROMPT = """Você é um redator publicitário brasileiro especialista em vídeos curtos para redes sociais \
(Reels, TikTok, Shorts). Escreva em português do Brasil, com frases curtas, persuasivas e naturais para narração. \
Nunca invente preços, prêmios, números ou dados que não foram informados. \
O campo image_prompt de cada cena deve estar em INGLÊS, descrever uma fotografia comercial realista, sem texto, \
sem letras e sem logotipos na imagem. Responda SOMENTE com JSON válido no schema pedido."""


def build_prompt(company: dict, settings: dict, template_cfg: dict | None) -> str:
    target = _target_scene_seconds(settings)
    words = int(target * WORDS_PER_SECOND)
    cfg = template_cfg or {}
    blueprint = cfg.get("blueprint") or []
    n_scenes = scene_count(settings, len(blueprint))
    roles_list = [b["role"] for b in blueprint] or ["hook", "product", "benefit", "differential", "offer", "cta"]
    if len(roles_list) > n_scenes:
        roles_list = roles_list[: n_scenes - 1] + ["cta"]
    roles = ", ".join(roles_list)
    lines = [
        "DADOS DA EMPRESA:",
        *(f"- {label}: {_clean(company.get(key), 500)}" for key, label in [
            ("name", "Nome"), ("segment", "Segmento"), ("description", "Descrição"),
            ("product", "Produto/serviço em destaque"), ("offer", "Promoção/oferta"),
            ("audience", "Público-alvo"), ("differentials", "Diferenciais"),
            ("whatsapp", "WhatsApp"), ("phone", "Telefone"), ("instagram", "Instagram"),
            ("address", "Endereço"),
        ] if company.get(key)),
        "",
        "CONFIGURAÇÃO DO VÍDEO:",
        f"- Tipo: {VIDEO_TYPES.get(settings.get('video_type'), settings.get('video_type'))}",
        f"- Estilo: {STYLES.get(settings.get('style'), settings.get('style'))}",
        f"- Formato: {settings.get('format')}",
        f"- Duração das cenas (sem a tela final): {target:.0f} segundos",
        f"- Quantidade de cenas: {n_scenes}",
        f"- Sequência sugerida de papéis: {roles}",
        f"- Estilo visual das imagens: {cfg.get('image_style', 'commercial photography')}",
        "",
        "TAREFA:",
        "1. Analise o negócio e o público (campo analysis, 1-2 frases).",
        "2. Crie um gancho forte para os primeiros 2 segundos (hook).",
        f"3. Crie {n_scenes} cenas. Cada cena tem: role, title (texto curto na tela, máx. 6 palavras), "
        "subtitle (opcional, máx. 10 palavras), narration (fala do locutor), image_prompt (inglês) e duration (segundos).",
        f"4. A narração TOTAL deve ter no máximo {words} palavras (cerca de {max(4, words // n_scenes)} por cena), "
        f"com frases completas. A soma das durações deve ser {target:.0f}.",
        "   Cada image_prompt deve ser diferente e descrever visualmente a cena específica (objeto, ambiente, luz).",
        "5. A última cena é a chamada para ação (role=cta) e deve citar o canal de contato informado.",
        "6. Gere também cta, caption (legenda para o post) e até 8 hashtags.",
    ]
    return "\n".join(lines)


def ollama_script(company: dict, settings: dict, template_cfg: dict | None, ai_cfg: dict) -> dict:
    url = ai_cfg["ollama_url"].rstrip("/") + "/api/chat"
    body = {
        "model": ai_cfg["ollama_model"],
        "stream": False,
        "format": SCRIPT_SCHEMA,
        "think": False,
        "options": {"temperature": float(ai_cfg.get("llm_temperature", 0.7)), "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(company, settings, template_cfg)},
        ],
    }
    try:
        with httpx.Client(timeout=float(ai_cfg.get("llm_timeout_seconds", 300))) as client:
            r = client.post(url, json=body)
            if r.status_code == 400 and "think" in r.text:
                body.pop("think")
                r = client.post(url, json=body)
            r.raise_for_status()
            content = r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise LLMError(f"Ollama indisponível: {exc}") from exc
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise LLMError("resposta do LLM não é JSON")
        data = json.loads(m.group(0))
    data["engine"] = f"ollama:{ai_cfg['ollama_model']}"
    script = enrich_script(normalize_script(data, settings), template_cfg)
    if len(script["scenes"]) < 2:
        raise LLMError("roteiro do LLM com poucas cenas")
    return script


def generate_script(company: dict, settings: dict, template_cfg: dict | None, ai_cfg: dict) -> tuple[dict, list[str]]:
    notes: list[str] = []
    if ai_cfg.get("llm_provider") == "ollama":
        try:
            return ollama_script(company, settings, template_cfg, ai_cfg), notes
        except (LLMError, json.JSONDecodeError) as exc:
            log.warning("LLM falhou, usando fallback: %s", exc)
            notes.append(f"LLM indisponível ({exc}); roteiro gerado pelo modo template.")
    return fallback_script(company, settings, template_cfg), notes


def ollama_status(ai_cfg: dict) -> dict:
    try:
        r = httpx.get(ai_cfg["ollama_url"].rstrip("/") + "/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return {"online": True, "models": models, "model_ready": ai_cfg["ollama_model"] in models}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {"online": False, "error": str(exc), "models": [], "model_ready": False}
