"""
benchmark/validators/kube_linter.py

Wrapper autour du binaire externe `kube-linter` (https://kube-linter.io).
kube-linter n'est PAS un package pip : c'est un binaire Go que vous devez
installer vous-même sur la machine qui lance `run_benchmark.py` (je ne
peux pas l'installer depuis mon environnement, qui est isolé de votre
machine). Voir le README du dossier `benchmark/` pour les instructions
d'installation.

Dégradation : si le binaire est introuvable sur le PATH, on ne fait PAS
échouer le benchmark -- on marque juste `available=False` pour ce
scénario, avec un avertissement affiché une seule fois. Le validateur
`k8s_validate.py` (vendored, zéro dépendance) reste actif dans tous les
cas et garantit qu'on a toujours au moins une mesure de validité
syntaxique/structurelle.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_warned_missing = False

# Cherche le binaire d'abord DANS le dossier benchmark/ lui-même (pas besoin
# de l'installer sur le PATH système), puis retombe sur le PATH si absent.
_LOCAL_BINARY_DIR = Path(__file__).resolve().parent.parent  # benchmark/


def _resolve_binary() -> str | None:
    for name in ("kube-linter.exe", "kube-linter"):
        candidate = _LOCAL_BINARY_DIR / name
        if candidate.exists():
            return str(candidate)
    return shutil.which("kube-linter")


@dataclass
class KubeLinterResult:
    available: bool          # False si le binaire n'est pas installé
    passed: bool | None      # None si available=False
    checks_failed: list[str]
    raw_output: str = ""


def is_available() -> bool:
    return _resolve_binary() is not None


def lint_yaml(yaml_text: str, timeout_seconds: int = 30) -> KubeLinterResult:
    global _warned_missing

    if not is_available():
        if not _warned_missing:
            print(
                "[avertissement] binaire 'kube-linter' introuvable sur le PATH -- "
                "le score de validité syntaxique kube-linter sera vide pour tous "
                "les scénarios. Voir benchmark/README.md pour l'installer. "
                "(cet avertissement ne s'affiche qu'une fois)"
            )
            _warned_missing = True
        return KubeLinterResult(available=False, passed=None, checks_failed=[])

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(yaml_text)
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [_resolve_binary(), "lint", str(tmp_path), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        raw = proc.stdout or proc.stderr

        # kube-linter renvoie un exit code != 0 dès qu'il y a au moins un
        # check en échec -- ce n'est PAS une erreur d'exécution, donc on ne
        # se fie jamais au returncode seul, on parse toujours le JSON.
        checks_failed: list[str] = []
        try:
            parsed = json.loads(raw) if raw.strip() else {}
            for report in parsed.get("Reports") or []:
                check = report.get("Check", "?")
                k8s_obj = (report.get("Object") or {}).get("K8sObject", {})
                kind = k8s_obj.get("GroupVersionKind", {}).get("Kind", "?")
                name = k8s_obj.get("Name", "?")
                checks_failed.append(f"{check} [{kind}/{name}]")
        except json.JSONDecodeError:
            # kube-linter a échoué à s'exécuter correctement (pas un simple
            # "checks failed") -- on le signale distinctement plutôt que de
            # compter ça comme 0 erreurs (faux positif de validité).
            return KubeLinterResult(
                available=True,
                passed=None,
                checks_failed=["[erreur d'exécution kube-linter, sortie non-JSON]"],
                raw_output=raw,
            )

        return KubeLinterResult(
            available=True,
            passed=(len(checks_failed) == 0),
            checks_failed=checks_failed,
            raw_output=raw,
        )
    except subprocess.TimeoutExpired:
        return KubeLinterResult(
            available=True,
            passed=None,
            checks_failed=[f"[timeout après {timeout_seconds}s]"],
        )
    finally:
        tmp_path.unlink(missing_ok=True)
