# Benchmark comparatif des architectures (E6)

Harnais de benchmark homogène pour comparer les architectures A
(agent unique), B (pipeline), C (blackboard) et D (débat) sur une même
suite de 10 exigences en langage naturel.

## Statut actuel

| Architecture | Adaptateur | Statut |
|---|---|---|
| A - Agent unique | `adapters/architecture_a_single_agent.py` | ✅ branché |
| B - Pipeline multi-agents | `adapters/architecture_b_pipeline.py` | ✅ branché (⚙️ chemin à configurer, voir ci-dessous) |
| C - Orchestrateur + blackboard | — | ⏳ pas encore construit |
| D - Orchestrateur + débat | — | ⏳ pas encore construit |

### Configurer l'architecture B

`pipeline-kubegen` est un projet séparé avec son propre venv (langgraph,
tenacity, etc.), donc le benchmark l'appelle en sous-processus plutôt
que de l'importer. Deux façons de configurer le chemin :

```bash
# Option 1 : variables d'environnement (recommandé, pas besoin d'éditer de code)
export PIPELINE_KUBEGEN_DIR="/chemin/vers/pipeline-kubegen"
export PIPELINE_PYTHON_EXE="/chemin/vers/pipeline-kubegen/venv/bin/python"   # ou venv\Scripts\python.exe sous Windows

# Option 2 : éditer les constantes en tête de
# benchmark/adapters/architecture_b_pipeline.py
```

Le venv (`.../venv/Scripts/python.exe` ou `.../venv/bin/python`) est
auto-détecté si `PIPELINE_KUBEGEN_DIR` est correct et que le venv existe
à l'emplacement standard -- sinon un avertissement s'affiche et le
benchmark utilisera par défaut l'interpréteur Python du benchmark
lui-même (probablement sans `langgraph`/`tenacity` installés, donc B
échouera avec une erreur claire plutôt qu'un plantage silencieux).

⚠️ **Cohérence du modèle** : à ce jour, `pipeline-kubegen` utilise
toujours `GEMMA_MODEL=gemma-4-31b-it` (voir son `config.py`) alors que
l'Architecture A a été basculée sur `gemini-2.5-flash`. Comparer A et B
avec des modèles différents biaise le tableau de coût/latence -- si vous
voulez une comparaison équitable, alignez aussi le modèle de
pipeline-kubegen avant de lancer le benchmark complet.

## Lancer le benchmark

```bash
# Depuis la racine du repo (là où se trouve run_benchmark.py)
export GOOGLE_API_KEY=votre_clé   # ou GEMINI_API_KEY

python run_benchmark.py                                   # tout, toutes archis dispo
python run_benchmark.py --architectures A                 # une seule architecture
python run_benchmark.py --scenarios 01,03,10               # un sous-ensemble de scénarios
python run_benchmark.py --output-dir resultats_2026_07_29  # dossier de sortie custom
```

⚠️ Chaque run fait un vrai appel API (10 scénarios × N architectures).
Ça consomme du quota et coûte de l'argent réel (voir `pricing.py`) — pas
de mode `--dry-run` pour l'instant (vous avez confirmé vouloir lancer en
conditions réelles).

Sorties, dans `--output-dir` (par défaut `benchmark_results/`) :
- `benchmark_telemetry.json` — détail complet par run (source de vérité)
- `benchmark_telemetry.csv` — vue plate, une ligne par run (Excel/pandas)
- `benchmark_report.md` — tableau comparatif agrégé + détail par scénario

## Installer kube-linter (optionnel mais recommandé)

`kube-linter` est un binaire Go, pas un package pip. Sans lui, le
harnais fonctionne quand même (le validateur `k8s_validate.py` vendoré,
zéro dépendance, reste actif), mais la colonne "Validité kube-linter"
du rapport affichera `N/A`.

**Windows (PowerShell)** — méthode la plus simple, binaire précompilé :
```powershell
# Télécharger la dernière release depuis
# https://github.com/stackrox/kube-linter/releases/latest
# (fichier kube-linter-windows.zip), extraire kube-linter.exe, puis
# soit l'ajouter à votre PATH, soit le placer à la racine du repo.
```
Ou via [Chocolatey](https://community.chocolatey.org/) si installé :
```powershell
choco install kube-linter
```

**macOS** :
```bash
brew install kube-linter
```

**Linux** :
```bash
curl -sL "https://github.com/stackrox/kube-linter/releases/latest/download/kube-linter-linux.tar.gz" | tar xz
sudo mv kube-linter /usr/local/bin/
```

Vérifiez avec `kube-linter version`.

## Ajouter les architectures C, D

1. Créer `benchmark/adapters/architecture_c_blackboard.py` (par ex.) avec
   une classe héritant de `ArchitectureAdapter` (voir `adapters/base.py`) :
   - `architecture_id` (ex: `"C_blackboard"`)
   - `architecture_label` (ex: `"Architecture C - Orchestrateur + blackboard"`)
   - `run(requirement, scenario_id, run_name) -> RunResult`, avec UN
     `StepTelemetry` par agent/étape (pas juste un total global) pour
     avoir la ventilation "latence par sous-agent" demandée par la tâche.
2. L'enregistrer dans `ARCHITECTURE_REGISTRY` (`adapters/__init__.py`).
3. Rien d'autre à modifier — scénarios, validateurs, scoring énergie,
   pricing et génération du rapport sont déjà architecture-agnostiques.

`adapters/architecture_b_pipeline.py` (invocation en sous-processus d'un
projet séparé + lecture de son `execution_metrics.json`) et
`adapters/architecture_a_single_agent.py` (import direct en mémoire)
montrent les deux patterns d'intégration possibles selon que
l'architecture vit dans ce repo ou dans un projet à part.

## Rubrique du score énergie

Voir le docstring de `energy_score.py` pour le détail des 5 critères et
leurs poids (requests/limits 40, autoscaling 25, node scheduling 20,
PodDisruptionBudget 10, probes 5), et pour la logique de normalisation
quand un critère n'est pas applicable à un scénario donné (ex : pas de
pénalité HPA sur un CronJob).

## Tarification (`pricing.py`)

Les prix par modèle sont une estimation à vérifier avant publication —
voir l'avertissement en tête de ce fichier. Si le modèle utilisé par une
architecture n'a pas d'entrée dans `PRICING_TABLE_USD_PER_1M_TOKENS`, le
coût est `None` (pas silencieusement faux) : ajoutez l'entrée manquante.
