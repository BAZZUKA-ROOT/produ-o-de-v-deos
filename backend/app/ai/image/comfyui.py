"""Cliente da API HTTP do ComfyUI (Stable Diffusion / SDXL / SD 1.5 + LCM)."""

import random
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx


class ComfyUIError(RuntimeError):
    pass


def _dims(width: int, height: int, base: int) -> tuple[int, int]:
    """Resolução nativa do modelo mantendo a proporção (múltiplos de 64)."""
    ratio = width / height
    area = base * base
    h = (area / ratio) ** 0.5
    w = h * ratio
    return max(64, int(round(w / 64)) * 64), max(64, int(round(h / 64)) * 64)


def build_workflow(prompt: str, negative: str, cfg: dict, width: int, height: int, seed: int) -> dict:
    w, h = _dims(width, height, int(cfg.get("comfyui_base_resolution", 1024)))
    model_out: list = ["4", 0]
    clip_out: list = ["4", 1]
    wf: dict = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": cfg["comfyui_checkpoint"]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
    }
    if cfg.get("comfyui_lora"):
        wf["10"] = {"class_type": "LoraLoader", "inputs": {
            "lora_name": cfg["comfyui_lora"], "strength_model": float(cfg.get("comfyui_lora_strength", 1.0)),
            "strength_clip": float(cfg.get("comfyui_lora_strength", 1.0)), "model": ["4", 0], "clip": ["4", 1]}}
        model_out, clip_out = ["10", 0], ["10", 1]
    wf.update({
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_out}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_out}},
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": int(cfg.get("comfyui_steps", 25)), "cfg": float(cfg.get("comfyui_cfg", 6.5)),
            "sampler_name": cfg.get("comfyui_sampler", "dpmpp_2m"), "scheduler": cfg.get("comfyui_scheduler", "karras"),
            "denoise": 1.0, "model": model_out, "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "forja", "images": ["8", 0]}},
    })
    return wf


def generate(prompt: str, out_path: Path, cfg: dict, width: int, height: int,
             should_cancel: Callable[[], bool] | None = None, seed: int | None = None) -> Path:
    base = cfg["comfyui_url"].rstrip("/")
    seed = seed if seed is not None else random.randint(1, 2**31 - 1)
    negative = cfg.get("negative_prompt", "")
    wf = build_workflow(prompt, negative, cfg, width, height, seed)
    timeout = float(cfg.get("comfyui_timeout_seconds", 600))
    client_id = uuid.uuid4().hex
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(f"{base}/prompt", json={"prompt": wf, "client_id": client_id})
            if r.status_code != 200:
                raise ComfyUIError(f"ComfyUI rejeitou o workflow: {r.text[:300]}")
            prompt_id = r.json()["prompt_id"]
            start = time.time()
            while True:
                if should_cancel and should_cancel():
                    c.post(f"{base}/interrupt")
                    raise ComfyUIError("cancelado")
                if time.time() - start > timeout:
                    raise ComfyUIError("tempo limite do ComfyUI excedido")
                h = c.get(f"{base}/history/{prompt_id}")
                data = h.json() if h.status_code == 200 else {}
                if prompt_id in data:
                    entry = data[prompt_id]
                    status = entry.get("status", {})
                    if status.get("status_str") == "error":
                        raise ComfyUIError(f"erro na geração: {status.get('messages')}")
                    images = [img for node in entry.get("outputs", {}).values() for img in node.get("images", [])]
                    if images:
                        img = images[0]
                        v = c.get(f"{base}/view", params={
                            "filename": img["filename"], "subfolder": img.get("subfolder", ""),
                            "type": img.get("type", "output")}, timeout=60)
                        v.raise_for_status()
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        out_path.write_bytes(v.content)
                        return out_path
                time.sleep(1.0)
    except httpx.HTTPError as exc:
        raise ComfyUIError(f"ComfyUI indisponível: {exc}") from exc


def status(cfg: dict) -> dict:
    base = cfg["comfyui_url"].rstrip("/")
    try:
        r = httpx.get(f"{base}/system_stats", timeout=5)
        r.raise_for_status()
        info = r.json()
        ckpts: list[str] = []
        try:
            o = httpx.get(f"{base}/object_info/CheckpointLoaderSimple", timeout=5).json()
            ckpts = o["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        except (httpx.HTTPError, KeyError, ValueError, IndexError, TypeError):
            pass
        return {"online": True, "devices": [d.get("name") for d in info.get("devices", [])], "checkpoints": ckpts,
                "checkpoint_ready": cfg["comfyui_checkpoint"] in ckpts}
    except (httpx.HTTPError, ValueError) as exc:
        return {"online": False, "error": str(exc), "checkpoints": [], "checkpoint_ready": False}
