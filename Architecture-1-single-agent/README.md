<<<<<<< HEAD
# EcoKubeGen — Architecture 1 : Agent unique monolithique

Première des 4 architectures à comparer dans le cadre du projet
*"Energy Aware Multi-Agent System for Kubernetes Configuration Generation"*.

```
Utilisateur (exigences en langage naturel)
        │
        ▼
┌───────────────────────────────────────────┐
│        Agent unique LLM (Gemma / API Gemini)│
│  - Analyse des exigences                   │
│  - Génération de manifestes Kubernetes     │
│  - Règles de bonnes pratiques / sécurité   │
│  - Heuristiques d'efficacité énergétique   │
│  (aucune isolation de contexte : tout dans │
│   le même prompt / historique)             │
└───────────────────────────────────────────┘
        │
        ▼
   Manifeste Kubernetes (YAML)
```

C'est la ligne de base ("baseline") : un seul appel LLM fait tout le travail.
Les architectures 2 (chaîne séquentielle), 3 (orchestrateur + blackboard) et
4 (orchestrateur + débat multi-agents) viendront ensuite se comparer à celle-ci
sur : validité du YAML généré, latence, nombre d'appels LLM, et qualité de
l'optimisation énergétique.

## 1. Prérequis

- Python 3.9+
- Une clé API Google AI Studio (gratuite) : https://aistudio.google.com/apikey

## 2. Installation

### a) Créer une clé API Google AI Studio

1. Ouvre https://aistudio.google.com/apikey et connecte-toi avec un compte Google.
2. Clique sur **"Create API key"**, choisis ou crée un projet Google Cloud (pas de
   carte bancaire requise pour le tier gratuit).
3. Copie la clé générée (`AIzaSy...`).

### b) Exporter la clé en variable d'environnement

```bash
# macOS / Linux :
export GOOGLE_API_KEY="ta_clé_api"

# Windows PowerShell :
$env:GOOGLE_API_KEY = "ta_clé_api"
```

`GEMINI_API_KEY` fonctionne aussi si tu préfères ce nom.

> Astuce : si tu veux un modèle plus léger/rapide, utilise `gemma-4-26b-a4b-it`
> au lieu du défaut `gemma-4-31b-it` (voir section "Changer de modèle" plus bas).

### c) Installer les dépendances Python du projet

Depuis le dossier de ce projet :

```bash
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Structure du projet

```
ecokubegen-v1-single-agent/
├── config.py                  # Paramètres (modèle Gemma, clé API, dossier de sortie...)
├── prompts.py                 # Le prompt système monolithique (les 4 responsabilités)
├── single_agent.py            # La classe SingleAgentGenerator (cœur de l'architecture 1)
├── main.py                    # CLI pour une génération unique
├── run_scenarios.py           # Lance l'agent sur tous les scénarios de test (benchmark)
├── requirements.txt
├── scenarios/                 # Exigences de test réutilisables (pour comparer les 4 archis)
│   ├── scenario_1_simple_web_app.txt
│   ├── scenario_2_variable_load_api.txt
│   └── scenario_3_nightly_cleanup_job.txt
├── generated-k8s-templates/   # Créé automatiquement : manifestes générés
└── results/                   # Créé automatiquement : CSV agrégé des benchmarks
```

## 4. Utilisation

### a) Génération unique (mode interactif)

```bash
python main.py
```

Le programme vous demande de décrire votre besoin :

```
Décris ton besoin (type d'appli, replicas, port, stockage, etc.) puis Entrée :
> Déploie une API Flask, 3 replicas, port 5000, accessible en interne uniquement
```

### b) Génération unique (argument direct)

```bash
python main.py -r "Déploie une API Flask, 3 replicas, port 5000, accessible en interne uniquement" -n mon_api_flask
```

Options :
- `-r / --requirement` : l'exigence en langage naturel
- `-n / --name` : nom du sous-dossier de sortie (défaut : horodatage `run_YYYYMMDD_HHMMSS`)
- `-m / --model` : nom du modèle Gemma à utiliser (défaut : `gemma-4-31b-it`)
- `--max-output-tokens` : nombre max de tokens générés par l'appel LLM (défaut : `2048`)

### c) Résultat produit

Chaque exécution crée un dossier sous `generated-k8s-templates/` :

```
generated-k8s-templates/
└── mon_api_flask/
    ├── manifest.yaml         # Le manifeste K8s final, nettoyé
    ├── raw_llm_output.txt    # La sortie brute du LLM (pour debug/analyse)
    └── metadata.json         # Métriques : latence, validité YAML, modèle utilisé...
```

Exemple de `metadata.json` :

```json
{
  "architecture": "1_single_agent_monolithic",
  "model": "llama3.2",
  "temperature": 0.2,
  "requirement": "Déploie une API Flask, 3 replicas, port 5000, ...",
  "latency_seconds": 4.32,
  "output_chars": 1523,
  "num_llm_calls": 1,
  "yaml_valid": true,
  "validation_errors": [],
  "timestamp": "2026-07-10T14:05:12"
}
```

`yaml_valid` / `validation_errors` proviennent d'une **validation légère**
(le YAML doit parser et contenir `apiVersion` / `kind` / `metadata`) : cette
architecture n'a volontairement **pas** d'étape de validation dédiée, contrairement
aux architectures 2/3/4. C'est exactement la limite que le projet cherche à mesurer.

### d) Lancer le benchmark sur tous les scénarios

Pour comparer objectivement cette architecture aux 3 autres, utilisez toujours
les mêmes exigences de test (`scenarios/`) :

```bash
python run_scenarios.py
```

Cela génère un manifeste par scénario et ajoute une ligne par scénario dans
`results/single_agent_results.csv`, avec les colonnes :

```
architecture, scenario, model, latency_seconds, num_llm_calls, yaml_valid, output_chars, timestamp, run_dir
```

Quand vous implémenterez les architectures 2, 3 et 4, faites-les écrire dans
des CSV avec les mêmes colonnes (ex: `results/chain_results.csv`,
`results/blackboard_results.csv`, `results/debate_results.csv`) : vous pourrez
ensuite les concaténer facilement pour l'analyse comparative finale.

## 5. Changer de modèle

Pour tester avec un modèle plus léger ou plus puissant :

```bash
python main.py -m gemma-4-26b-a4b-it -r "..."
```

ou en variable d'environnement (pratique pour ne pas répéter `-m` à chaque fois) :

```bash
export GEMMA_MODEL=gemma-4-26b-a4b-it
python main.py -r "..."
```

Pour vérifier les modèles Gemma réellement disponibles pour ta clé :

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models?key=TA_CLE"
```

## 6. Dépannage

| Problème | Cause probable | Solution |
|---|---|---|
| `RuntimeError: Aucune clé API Google trouvée` | Variable d'environnement absente | `export GOOGLE_API_KEY="ta_clé"` |
| `PermissionDenied` / `401` / `403` | Clé API invalide ou absente | Vérifier `GOOGLE_API_KEY` sur https://aistudio.google.com/apikey |
| `ResourceExhausted` / `429` | Quota gratuit dépassé | Attendre le renouvellement du quota ou passer à un modèle plus petit |
| `404 NOT_FOUND ... is not found for API version v1beta` | Nom de modèle retiré/incorrect | Lister les modèles dispo (`curl .../v1beta/models?key=TA_CLE`) et utiliser `-m` avec un nom valide |
| `RuntimeError: Réponse vide du modèle` | Budget de tokens épuisé par le "thinking" interne du modèle | Augmenter `--max-output-tokens`, ou vérifier `thinking_level` dans `single_agent.py` |
| `yaml_valid: false` récurrent | Modèle trop petit / prompt mal suivi | Essayer `gemma-4-31b-it` (plus grand), ou baisser `TEMPERATURE` dans `config.py` |
| Génération très lente | Modèle plus gros / charge côté API | Utiliser `gemma-4-26b-a4b-it` (plus rapide) |

## 7. Ce que ce projet mesure (pour le rapport final)

Cette architecture sert de référence pour répondre aux objectifs de recherche :

- **Qualité / fiabilité** : taux de `yaml_valid: true` sur l'ensemble des scénarios
- **Efficacité énergétique du manifeste généré** : présence de `requests`/`limits`
  bien dimensionnés, présence d'un HPA quand pertinent, absence de sur-provisionnement
  (à évaluer manuellement ou via un script d'analyse à écrire plus tard)
- **Coût d'inférence** : `num_llm_calls` (toujours 1 ici) et `latency_seconds`,
  à comparer aux architectures multi-agents qui feront plusieurs appels LLM
=======
# kubeGen
TBD
>>>>>>> 6a19c5f9b72e3e254c4036326da5e9320d6e5aad
