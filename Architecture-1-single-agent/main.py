"""
Point d'entrée en ligne de commande pour l'Architecture 1.

Exemples :
    python main.py -r "Déploie une API Flask, 3 replicas, port 5000, exposée en interne"
    python main.py            # mode interactif
    python main.py -r "..." -m gemini-2.5-flash -n test_flask

Nécessite une clé API Google AI Studio dans la variable d'environnement
GOOGLE_API_KEY (ou GEMINI_API_KEY) : https://aistudio.google.com/apikey
"""
import argparse
import sys

from single_agent import SingleAgentGenerator


def main():
    parser = argparse.ArgumentParser(
        description="EcoKubeGen — Architecture 1 : Agent unique monolithique (Gemini via l'API Gemini)."
    )
    parser.add_argument(
        "-r", "--requirement", type=str, default=None,
        help="Exigence en langage naturel. Si omis, un prompt interactif est utilisé.",
    )
    parser.add_argument(
        "-n", "--name", type=str, default=None,
        help="Nom du sous-dossier de sortie sous generated-k8s-templates/ (défaut: horodatage).",
    )
    parser.add_argument(
        "-m", "--model", type=str, default=None,
        help="Nom du modèle Gemini à utiliser (défaut: variable d'env GEMINI_MODEL ou 'gemini-2.5-flash').",
    )
    parser.add_argument(
        "--max-output-tokens", type=int, default=None,
        help="Nombre maximum de tokens générés par l'appel LLM (défaut: 2048).",
    )
    args = parser.parse_args()

    requirement = args.requirement
    if not requirement:
        print("Décris ton besoin (type d'appli, replicas, port, stockage, etc.) puis Entrée :")
        requirement = input("> ").strip()

    if not requirement:
        print("Aucune exigence fournie, abandon.", file=sys.stderr)
        sys.exit(1)

    kwargs = {}
    if args.model:
        kwargs["model"] = args.model

    if args.max_output_tokens:
        kwargs["max_output_tokens"] = args.max_output_tokens

    agent = SingleAgentGenerator(**kwargs)

    print(f"\n[Architecture 1] Génération en cours avec le modèle '{agent.model}'...\n")
    result = agent.generate(requirement, run_name=args.name)

    print("=== Génération terminée ===")
    print(f"Dossier      : {result['run_dir']}")
    print(f"Manifeste    : {result['manifest_path']}")
    print(f"Temps        : {result['latency_seconds']}s")
    print(f"YAML valide  : {result['yaml_valid']}")
    if not result["yaml_valid"]:
        print("Erreurs de validation :")
        for e in result["validation_errors"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
