#!/usr/bin/env python3
"""Download the recommended R3 models (pinned revisions) into ./models for offline use.

    python download_models.py [--set default|small|all] [--dest models]

Uses huggingface_hub if installed, otherwise plain HTTPS. Nothing runs on import.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

EMBED_MINILM = ("sentence-transformers/all-MiniLM-L6-v2", "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                ["config.json", "modules.json", "sentence_bert_config.json", "config_sentence_transformers.json",
                 "1_Pooling/config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "vocab.txt",
                 "special_tokens_map.json"])
EMBED_MULTI = ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
               ["config.json", "modules.json", "sentence_bert_config.json", "config_sentence_transformers.json",
                "1_Pooling/config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                "special_tokens_map.json"])
LLM_15B = ("Qwen/Qwen2.5-1.5B-Instruct-GGUF", "91cad51170dc346986eccefdc2dd33a9da36ead9", ["qwen2.5-1.5b-instruct-q4_k_m.gguf", "LICENSE"])
LLM_05B = ("Qwen/Qwen2.5-0.5B-Instruct-GGUF", "9217f5db79a29953eb74d5343926648285ec7e67", ["qwen2.5-0.5b-instruct-q4_k_m.gguf", "LICENSE"])
SETS = {"default": [EMBED_MINILM, LLM_15B], "small": [EMBED_MINILM, LLM_05B],
        "all": [EMBED_MINILM, EMBED_MULTI, LLM_15B, LLM_05B]}


def fetch(repo: str, rev: str, files: list, dest: Path) -> None:
    target = dest / repo.split("/")[1]
    target.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except ImportError:
        hf_hub_download = None
    for f in files:
        out = target / f
        if out.exists() and out.stat().st_size > 0:
            print(f"  already have {out}")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"  downloading {repo}/{f} @ {rev[:8]} ...", flush=True)
        if hf_hub_download is not None:
            hf_hub_download(repo_id=repo, filename=f, revision=rev, local_dir=str(target))
        else:
            url = f"https://huggingface.co/{repo}/resolve/{rev}/{f}"
            tmp = out.with_suffix(out.suffix + ".part")
            urllib.request.urlretrieve(url, tmp)
            tmp.rename(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", choices=sorted(SETS), default="default")
    ap.add_argument("--dest", default=str(Path(__file__).resolve().parent / "models"))
    args = ap.parse_args()
    dest = Path(args.dest)
    for repo, rev, files in SETS[args.set]:
        print(f"{repo}")
        try:
            fetch(repo, rev, files, dest)
        except Exception as e:  # network problems etc.
            print(f"  FAILED: {e}\n  (If organisers provided a mirror, copy the files into {dest / repo.split('/')[1]} instead.)", file=sys.stderr)
            return 1
    print(f"Done. Models are in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
