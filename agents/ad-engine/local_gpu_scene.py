#!/usr/bin/env python3
"""Local CUDA image generation for the Ad Creative Engine.

This script gives the ad-engine a genuinely GPU-bound scene generation path for
RunPod / H100 environments. It is intentionally optional: if the CUDA stack or
diffusers dependencies are missing, the rest of the ad-engine can continue to
use Google Stitch / Vertex.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).resolve().parent
REPO_DIR = AGENT_DIR.parent.parent

DEFAULT_MODEL = os.environ.get("AD_LOCAL_GPU_MODEL", "stabilityai/sdxl-turbo")
DEFAULT_WIDTH = int(os.environ.get("AD_LOCAL_GPU_WIDTH", "1024"))
DEFAULT_HEIGHT = int(os.environ.get("AD_LOCAL_GPU_HEIGHT", "1024"))
DEFAULT_STEPS = int(os.environ.get("AD_LOCAL_GPU_STEPS", "4"))
DEFAULT_GUIDANCE = float(os.environ.get("AD_LOCAL_GPU_GUIDANCE", "0.0"))
DEFAULT_NEGATIVE_PROMPT = os.environ.get(
    "AD_LOCAL_GPU_NEGATIVE_PROMPT",
    "text, logo, watermark, collage, split screen, low quality, blurry, deformed hands, extra fingers, duplicate face",
)

_PIPELINE = None
_PIPELINE_KEY: tuple[str, str] | None = None


def module_present(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def get_secret_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value

    try:
        sys.path.insert(0, str(REPO_DIR))
        from src.coordinator.secrets import get_secret

        return get_secret(name)
    except Exception:
        return None


def torch_dtype_from_name(torch: Any, dtype_name: str) -> Any:
    normalized = dtype_name.lower().strip()
    if normalized in {"bfloat16", "bf16"}:
        return torch.bfloat16
    if normalized in {"float32", "fp32"}:
        return torch.float32
    return torch.float16


def healthcheck() -> dict[str, Any]:
    status: dict[str, Any] = {
        "provider": "local_gpu_scene",
        "model": DEFAULT_MODEL,
        "torch_installed": module_present("torch"),
        "diffusers_installed": module_present("diffusers"),
        "pillow_installed": module_present("PIL"),
        "ready": False,
    }

    if not status["torch_installed"]:
        status["error"] = "torch not installed"
        return status
    if not status["diffusers_installed"]:
        status["error"] = "diffusers not installed"
        return status
    if not status["pillow_installed"]:
        status["error"] = "Pillow not installed"
        return status

    try:
        import torch

        status["cuda_available"] = bool(torch.cuda.is_available())
        status["device_count"] = int(torch.cuda.device_count())
        status["device_name"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        status["cuda_version"] = getattr(torch.version, "cuda", None)
    except Exception as exc:
        status["error"] = f"torch healthcheck failed: {exc}"
        return status

    hf_token_present = bool(get_secret_value("HF_TOKEN"))
    status["hf_token_present"] = hf_token_present
    status["ready"] = bool(status["cuda_available"])
    if not status["ready"]:
        status["error"] = "CUDA is not available"
    return status


def build_pipeline(model: str, dtype_name: str):
    global _PIPELINE, _PIPELINE_KEY

    cache_key = (model, dtype_name)
    if _PIPELINE is not None and _PIPELINE_KEY == cache_key:
        return _PIPELINE

    import torch
    from diffusers import AutoPipelineForText2Image

    hf_token = get_secret_value("HF_TOKEN")
    torch_dtype = torch_dtype_from_name(torch, dtype_name)
    kwargs: dict[str, Any] = {
        "torch_dtype": torch_dtype,
        "use_safetensors": True,
    }
    if hf_token:
        kwargs["token"] = hf_token
    if torch_dtype in {torch.float16, torch.bfloat16}:
        kwargs["variant"] = "fp16"

    pipe = AutoPipelineForText2Image.from_pretrained(model, **kwargs)
    pipe = pipe.to("cuda")

    # These toggles usually help on H100-class hardware without changing output semantics.
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing()
    if hasattr(pipe, "set_progress_bar_config"):
        pipe.set_progress_bar_config(disable=True)

    _PIPELINE = pipe
    _PIPELINE_KEY = cache_key
    return pipe


def generate_image(
    *,
    prompt: str,
    output: str,
    model: str = DEFAULT_MODEL,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    num_inference_steps: int = DEFAULT_STEPS,
    guidance_scale: float = DEFAULT_GUIDANCE,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    seed: int | None = None,
    dtype_name: str = os.environ.get("AD_LOCAL_GPU_DTYPE", "float16"),
) -> dict[str, Any]:
    status = healthcheck()
    if not status.get("ready"):
        print(f"ERROR: {status.get('error', 'local GPU scene provider is not ready')}", file=sys.stderr)
        sys.exit(1)

    import torch

    pipe = build_pipeline(model, dtype_name)
    generator = None
    if seed is not None:
        generator = torch.Generator(device="cuda").manual_seed(seed)

    image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        generator=generator,
    ).images[0]

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return {
        "provider": "local_gpu_scene",
        "model": model,
        "output": str(output_path),
        "width": width,
        "height": height,
        "steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Local CUDA image generation for ad-engine scenes")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("healthcheck", help="Validate the local CUDA render stack")

    generate = sub.add_parser("generate", help="Generate one scene image on the local GPU")
    generate.add_argument("--prompt", required=True, help="Scene prompt")
    generate.add_argument("--output", required=True, help="Output PNG path")
    generate.add_argument("--model", default=DEFAULT_MODEL, help="Diffusers model id")
    generate.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Image width")
    generate.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Image height")
    generate.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="Inference steps")
    generate.add_argument("--guidance-scale", type=float, default=DEFAULT_GUIDANCE, help="CFG scale")
    generate.add_argument("--negative-prompt", default=DEFAULT_NEGATIVE_PROMPT, help="Negative prompt")
    generate.add_argument("--seed", type=int, help="Optional random seed")
    generate.add_argument(
        "--dtype",
        default=os.environ.get("AD_LOCAL_GPU_DTYPE", "float16"),
        choices=["float16", "fp16", "bfloat16", "bf16", "float32", "fp32"],
        help="Torch dtype for model weights",
    )

    args = parser.parse_args()
    if args.command == "healthcheck":
        print(json.dumps(healthcheck(), indent=2))
        return

    if args.command == "generate":
        result = generate_image(
            prompt=args.prompt,
            output=args.output,
            model=args.model,
            width=args.width,
            height=args.height,
            num_inference_steps=args.steps,
            guidance_scale=args.guidance_scale,
            negative_prompt=args.negative_prompt,
            seed=args.seed,
            dtype_name=args.dtype,
        )
        print(json.dumps(result, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
