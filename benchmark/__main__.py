"""
CLI entry point: python -m benchmark run --set poc

Usage:
    uv run python -m benchmark run --set {poc,v1,recommended}
    uv run python -m benchmark run --model gemma4:e2b
    uv run python -m benchmark run --set poc --timeout 300
    uv run python -m benchmark run --set poc --task limerick
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import yaml

from .agent import TIMEOUT_SECONDS
from .runner import run_benchmark

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MODELS_YAML = Path(__file__).parent.parent / "models.yaml"


def load_catalog() -> dict:
    with open(MODELS_YAML) as f:
        data = yaml.safe_load(f)

    catalog: dict = {}
    for _family, entries in data.items():
        if isinstance(entries, list):
            for entry in entries:
                catalog[entry["id"]] = entry
    return catalog


def models_for_set(catalog: dict, model_set: str) -> list[dict]:
    def is_runnable(e: dict) -> bool:
        return not e.get("exclude") and e.get("provider") in ("ollama", "anthropic")

    if model_set == "reference":
        return [e for e in catalog.values() if is_runnable(e) and e.get("provider") == "anthropic"]

    key_map = {"poc": "poc", "v1": "v1", "recommended": "recommended"}
    if model_set not in key_map:
        logger.error("Unknown set '%s'. Choose: poc, v1, recommended, reference", model_set)
        sys.exit(1)

    key = key_map[model_set]
    return [e for e in catalog.values() if is_runnable(e) and e.get(key)]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m benchmark",
        description="Run the LLM coding benchmark.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the benchmark")
    group = run_p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--set",
        dest="model_set",
        choices=["poc", "v1", "recommended", "reference"],
        metavar="{poc,v1,recommended,reference}",
        help="Named model set",
    )
    group.add_argument(
        "--model",
        nargs="+",
        metavar="MODEL_ID",
        help="One or more specific model IDs",
    )
    run_p.add_argument("--task", default="limerick", help="Task name (default: limerick)")
    run_p.add_argument(
        "--timeout",
        type=int,
        default=TIMEOUT_SECONDS,
        help=f"Per-model timeout in seconds (default: {TIMEOUT_SECONDS})",
    )

    args = parser.parse_args()

    catalog = load_catalog()

    if args.model_set:
        models = models_for_set(catalog, args.model_set)
        if not models:
            logger.error("No runnable models found for set '%s'", args.model_set)
            sys.exit(1)
    else:
        models = []
        for mid in args.model:
            entry = catalog.get(mid)
            if entry is None:
                logger.warning("%s not in catalog — adding with provider=ollama", mid)
                entry = {"id": mid, "provider": "ollama"}
            elif entry.get("exclude"):
                logger.warning("Skipping %s: %s", mid, entry["exclude"])
                continue
            models.append(entry)

        if not models:
            logger.error("No valid models to run")
            sys.exit(1)

    logger.info("Models to run (%d):", len(models))
    for m in models:
        size = m.get("size_gb")
        size_str = f"  {size:.1f} GB" if size else ""
        logger.info("  %s%s", m["id"], size_str)

    summaries = asyncio.run(run_benchmark(models, task_name=args.task, timeout=args.timeout))

    passed = sum(1 for s in summaries if s.get("eval", {}).get("http_status") == 200)
    logger.info("Done. %d/%d returned HTTP 200.", passed, len(summaries))


if __name__ == "__main__":
    main()
