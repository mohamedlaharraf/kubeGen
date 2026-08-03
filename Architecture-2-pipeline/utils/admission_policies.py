"""
utils/admission_policies.py

Génération de squelettes de policies d'admission (Kyverno) à partir de
descriptions en langage naturel — VOLONTAIREMENT déterministe (pattern
matching Python simple), PAS via un appel LLM.

Pourquoi pas de LLM ici : une policy d'admission mal générée peut soit
bloquer tout le cluster (faux positif trop strict), soit laisser passer
ce qu'elle était censée empêcher (faux négatif) — le risque d'une
hallucination silencieuse est plus élevé ici que pour un manifeste
applicatif ordinaire. On préfère donc ne reconnaître qu'une poignée de
patterns bien connus et documenter le reste comme non résolu, plutôt que
de laisser un LLM improviser une règle de sécurité incertaine.
"""

from __future__ import annotations

import re

# (regex sur la description, générateur de policy Kyverno)
_KNOWN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"limit.*(ressource|resource|cpu|m[ée]moire|memory)|"
                   r"resource.*limit", re.IGNORECASE),
        "require-resource-limits",
    ),
    (
        re.compile(r"non.?root|runAsNonRoot|pas.*root|sans.*root|"
                   r"interdi\w*.*root|\ben\s+root\b|accès\s+root", re.IGNORECASE),
        "require-run-as-non-root",
    ),
    (
        re.compile(r"latest|tag.*explicite|image.*versionn", re.IGNORECASE),
        "disallow-latest-tag",
    ),
]

_POLICY_TEMPLATES = {
    "require-resource-limits": """apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
spec:
  validationFailureAction: Audit
  rules:
    - name: check-resource-limits
      match:
        resources:
          kinds: ["Pod"]
      validate:
        message: "Chaque conteneur doit définir resources.limits.cpu et memory."
        pattern:
          spec:
            containers:
              - resources:
                  limits:
                    cpu: "?*"
                    memory: "?*"
""",
    "require-run-as-non-root": """apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-run-as-non-root
spec:
  validationFailureAction: Audit
  rules:
    - name: check-run-as-non-root
      match:
        resources:
          kinds: ["Pod"]
      validate:
        message: "Les pods doivent définir securityContext.runAsNonRoot=true."
        pattern:
          spec:
            securityContext:
              runAsNonRoot: true
""",
    "disallow-latest-tag": """apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-latest-tag
spec:
  validationFailureAction: Audit
  rules:
    - name: require-image-tag
      match:
        resources:
          kinds: ["Pod"]
      validate:
        message: "Les images doivent utiliser un tag explicite, jamais ':latest' ou aucun tag."
        pattern:
          spec:
            containers:
              - image: "!*:latest"
""",
}


def generate_admission_policy_skeletons(descriptions: list[str]) -> dict:
    """
    Pour chaque description, tente de la faire correspondre à un pattern
    connu. Renvoie :
      {"manifest_yaml": str, "addressed": [...], "left_open": [...]}

    `validationFailureAction: Audit` (pas `Enforce`) par défaut, DÉLIBÉRÉMENT
    conservateur : ces policies doivent être passées en mode "audit" et
    revues avant d'être activées en blocage réel — ce squelette ne doit
    jamais bloquer silencieusement un déploiement sans revue humaine.
    """
    addressed: list[str] = []
    left_open: list[str] = []
    yaml_parts: list[str] = []
    used_templates: set[str] = set()

    for desc in descriptions:
        matched_template = None
        for pattern, template_key in _KNOWN_PATTERNS:
            if pattern.search(desc):
                matched_template = template_key
                break

        if matched_template and matched_template not in used_templates:
            yaml_parts.append(_POLICY_TEMPLATES[matched_template])
            used_templates.add(matched_template)
            addressed.append(f"{desc} -> ClusterPolicy Kyverno '{matched_template}' (mode Audit)")
        elif matched_template:
            addressed.append(f"{desc} -> déjà couvert par '{matched_template}'")
        else:
            left_open.append(
                f"{desc} : pattern non reconnu, aucune policy générée "
                f"automatiquement (évite le risque d'une règle de sécurité "
                f"mal traduite) — à écrire manuellement."
            )

    return {
        "manifest_yaml": "\n---\n".join(yaml_parts),
        "addressed": addressed,
        "left_open": left_open,
    }
