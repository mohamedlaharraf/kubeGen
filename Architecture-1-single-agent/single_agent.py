"""
Architecture 1 : Agent unique (prompt monolithique).

    Utilisateur --> [Agent unique LLM] --> Manifeste Kubernetes

Aucune isolation de contexte : l'analyse des exigences, la génération,
les règles de bonnes pratiques et les heuristiques énergétiques sont
toutes gérées par le même appel LLM, avec le même historique.

Ce module est volontairement autonome (pas de dépendance à un
orchestrateur) car il servira de ligne de base ("baseline") pour la
comparaison avec les architectures 2, 3 et 4.
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
import yaml

from config import MAX_OUTPUT_TOKENS, GEMMA_MODEL, GOOGLE_API_KEY, OUTPUT_DIR, TEMPERATURE
from prompts import SYSTEM_PROMPT


class SingleAgentGenerator:
    """Génère un manifeste Kubernetes à partir d'une exigence en langage naturel,
    en un seul appel LLM (architecture monolithique)."""

    def __init__(self, model: str = GEMMA_MODEL, temperature: float = TEMPERATURE,
                 output_dir: str = OUTPUT_DIR, api_key: str = GOOGLE_API_KEY,
                 max_output_tokens: int = MAX_OUTPUT_TOKENS):
        if not api_key:
            raise RuntimeError(
                "Aucune clé API Google trouvée. Définis la variable d'environnement "
                "GOOGLE_API_KEY (ou GEMINI_API_KEY) — clé disponible sur "
                "https://aistudio.google.com/apikey"
            )
        self.model = model
        self.temperature = temperature
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = genai.Client(api_key=api_key)
        self.max_output_tokens = max_output_tokens

    # ------------------------------------------------------------------ #
    # Utilitaires internes
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_yaml(text: str) -> str:
        """Retire d'éventuelles balises markdown que le modèle aurait ajoutées
        malgré la consigne du prompt."""
        text = text.strip()
        text = re.sub(r"^```(?:yaml|yml)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @staticmethod
    def _validate_yaml(text: str):
        """Validation légère : le YAML doit parser, et chaque document doit
        contenir apiVersion / kind / metadata. Ce n'est PAS une validation
        contre le schéma Kubernetes officiel (voir Architecture 3 pour ça),
        volontairement, car cette architecture 1 n'a pas d'étape de
        validation dédiée."""
        errors = []
        try:
            docs = [d for d in yaml.safe_load_all(text) if d is not None]
        except yaml.YAMLError as e:
            return False, [f"Erreur de parsing YAML : {e}"]

        if not docs:
            return False, ["Aucun document YAML trouvé dans la sortie."]

        for i, doc in enumerate(docs):
            if not isinstance(doc, dict):
                errors.append(f"Document {i}: n'est pas un objet YAML valide.")
                continue
            for field in ("apiVersion", "kind", "metadata"):
                if field not in doc:
                    errors.append(f"Document {i}: champ requis manquant '{field}'.")

        return (len(errors) == 0), errors

    # ------------------------------------------------------------------ #
    # API publique
    # ------------------------------------------------------------------ #
    def generate(self, requirement: str, run_name: str = None) -> dict:
        """Lance une génération complète et écrit les artefacts sur disque.

        Retourne un dict de métadonnées (utile pour agréger des résultats
        de benchmark inter-architectures).
        """
        run_name = run_name or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        run_dir = self.output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        start = time.time()
        response = self.client.models.generate_content(
            model=self.model,
            contents=requirement,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            ),
        )
        elapsed = time.time() - start

        raw_output = response.text or ""
        if not raw_output:
            finish_reason = getattr(response.candidates[0], "finish_reason", None) if response.candidates else None
            raise RuntimeError(
                f"Réponse vide du modèle '{self.model}' (finish_reason={finish_reason}). "
                "Le budget max_output_tokens a probablement été épuisé par le "
                "'thinking' interne du modèle. Augmente MAX_OUTPUT_TOKENS dans "
                "config.py, ou essaie un autre modèle."
            )
        yaml_text = self._clean_yaml(raw_output)
        is_valid, errors = self._validate_yaml(yaml_text)

        manifest_path = run_dir / "manifest.yaml"
        manifest_path.write_text(yaml_text, encoding="utf-8")
        (run_dir / "raw_llm_output.txt").write_text(raw_output, encoding="utf-8")

        metadata = {
            "architecture": "1_single_agent_monolithic",
            "model": self.model,
            "temperature": self.temperature,
            "requirement": requirement,
            "latency_seconds": round(elapsed, 2),
            "output_chars": len(raw_output),
            "num_llm_calls": 1,
            "yaml_valid": is_valid,
            "validation_errors": errors,
            "timestamp": datetime.now().isoformat(),
        }
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return {
            "run_dir": str(run_dir),
            "manifest_path": str(manifest_path),
            **metadata,
        }
