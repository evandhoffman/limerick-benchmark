"""Shared helpers for querying the local Ollama model store."""

import logging
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LocalModel:
    name: str       # e.g. "gemma4:e2b-mlx-bf16"
    model_id: str   # short hash
    size_gb: float
    modified: str   # raw string from ollama list


def get_local_models() -> list[LocalModel]:
    """Return all models currently in the local Ollama store."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        logger.error("'ollama' not found. Install Ollama from https://ollama.ai")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        logger.warning("'ollama list' timed out — is ollama running? (try: ollama serve)")
        return []

    if result.returncode != 0:
        logger.warning("'ollama list' failed: %s", result.stderr.strip())
        return []

    models = []
    for line in result.stdout.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0]
        model_id = parts[1]
        # Size is "X GB" or "X MB" — two tokens
        try:
            size_val = float(parts[2])
            size_unit = parts[3].upper()
            size_gb = size_val if size_unit == "GB" else size_val / 1024
            modified = " ".join(parts[4:])
        except (ValueError, IndexError):
            size_gb = 0.0
            modified = ""
        models.append(LocalModel(name=name, model_id=model_id, size_gb=size_gb, modified=modified))

    return models


def get_pulled_names() -> set[str]:
    """Return just the set of pulled model name:tag strings."""
    return {m.name for m in get_local_models()}
