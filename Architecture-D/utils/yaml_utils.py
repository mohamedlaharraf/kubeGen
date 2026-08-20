"""utils/yaml_utils.py — helpers YAML pour manifestes Kubernetes."""

from __future__ import annotations

import yaml


def load_all_documents(yaml_text: str) -> list[dict]:
    """Parse un YAML multi-documents (séparés par ---). Lève une erreur
    claire si un document est invalide."""
    try:
        docs = [d for d in yaml.safe_load_all(yaml_text) if d is not None]
    except yaml.YAMLError as e:
        raise ValueError(f"YAML invalide : {e}") from e
    return docs


def dump_all_documents(docs: list[dict]) -> str:
    return "---\n".join(
        yaml.dump(d, sort_keys=False, default_flow_style=False) for d in docs
    )
