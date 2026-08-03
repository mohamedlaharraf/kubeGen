"""
Configuration centrale pour l'Architecture 1 : Agent unique monolithique.

Toutes les valeurs peuvent être surchargées via des variables d'environnement,
ce qui permet de lancer facilement des benchmarks avec différents modèles
sans toucher au code.
"""
import os

# Nom du modèle Gemini à utiliser via l'API Gemini / Google AI Studio.
# Accepte toujours l'ancienne variable GEMMA_MODEL par compatibilité
# ascendante (si quelqu'un a un script/CI qui la définit encore).
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or os.getenv("GEMMA_MODEL", "gemini-3.6-flash")

# Clé API Google AI Studio (https://aistudio.google.com/apikey).
# Accepte aussi GEMINI_API_KEY par compatibilité avec le SDK google-genai.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Dossier où les manifestes générés sont déposés.
# Chaque exécution crée un sous-dossier horodaté : generated-k8s-templates/run_YYYYMMDD_HHMMSS/
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "generated-k8s-templates")

# Température basse pour privilégier la cohérence et la validité syntaxique du YAML
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# Nombre max de tokens en sortie.
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "8192"))
