# pipeline-kubegen — Pipeline séquentiel strict à 5 agents (K8s + énergie)

Génère des manifestes Kubernetes optimisés en énergie (HPA, requests/limits,
probes...) à partir d'une demande en langage naturel, via un pipeline
**strictement séquentiel** à 5 agents, propulsé par **Gemma ou Gemini**
(Google AI Studio, configurable via `LLM_MODEL`) orchestré avec
**LangGraph**.

```
Input -> Agent1 (analyse) -> Agent2 (template) -> Agent3 (validation)
      -> Agent4 (énergie) -> Agent5 (vérification syntaxique post-énergie)
      -> Manifeste final
```

- Chaîne stricte : **aucune arête de retour** dans le graphe.
- Contexte isolé par étape : chaque agent ne reçoit dans son prompt que les
  champs pertinents à son rôle.
- Un seul agent (Agent 1) voit la demande brute de l'utilisateur — voir plus
  bas comment le projet garantit qu'elle est bien comprise et transmise.

## Pourquoi ce projet répond à votre problème initial

> "seul l'agent 1 voit la commande de l'utilisateur, donc s'il rate quelque
> chose on n'aura pas exactement ce qui est demandé"

C'est le risque structurel de toute architecture en chaîne stricte. Ce
projet le traite à trois niveaux, **sans jamais introduire de retour en
arrière dans le graphe** :

### 1. Un contrat structuré strict : `NormalizedSpec` (`schemas.py`)

L'Agent 1 ne "résume" pas librement la demande : il doit remplir un schéma
Pydantic précis (nom, image, ports, env, volumes, réplicas, objectifs
énergie, contraintes...). Contraindre la sortie à un schéma explicite réduit
fortement le risque d'oubli silencieux, par rapport à un simple résumé texte.

### 2. Une boucle d'auto-vérification interne à l'Agent 1

Toujours dans le même noeud du graphe (donc sans violer "pas de retour en
arrière") :

1. **Extraction** : le LLM produit la `NormalizedSpec` depuis le texte brut.
2. **Self-check** : le LLM relit le texte brut + son propre JSON et liste
   les exigences non couvertes (`gaps`).
3. **Réparation** : s'il y a des `gaps`, le LLM corrige son JSON. Répété
   jusqu'à `AGENT1_MAX_REPAIR_ATTEMPTS` fois (défaut : 2) ou jusqu'à ce
   qu'il n'y ait plus de gap.

Le résultat de cette boucle (`coverage.self_check_passed`,
`coverage.requirements_unmapped`, `ambiguities`) est conservé **dans** la
`NormalizedSpec** elle-même et voyage avec elle dans tout le pipeline.

### 3. Traçabilité de bout en bout + audit final (Agent 5)

Chaque agent (2 à 5) déclare explicitement, dans son rapport
(`AgentReport`), quels champs de la spec il a traités (`fields_addressed`)
et lesquels il laisse ouverts pour un agent suivant (`fields_left_open`).
L'Agent 5 agrège tout ça dans une **matrice de traçabilité** et une liste
`unresolved_items` : tout ce qui n'a été traité par personne devient
**visible** dans `output/audit_report.md`.

Le pipeline reste strict — il ne boucle pas automatiquement pour se
corriger — mais rien n'est perdu silencieusement : l'utilisateur voit
précisément ce qui a été compris, ce qui a été supposé, et ce qui reste
ouvert, et peut relancer une exécution avec une demande précisée si besoin.

> Autrement dit : dans une chaîne stricte, on ne peut pas éliminer le risque
> qu'un agent en amont se trompe, mais on peut (a) réduire ce risque avec de
> l'auto-vérification interne à l'étape, et (b) rendre toute perte
> **visible et traçable** plutôt que silencieuse.

## Rôle de chaque agent (strictement délimité)

| Agent | Entrée | Rôle | Ne fait PAS |
|---|---|---|---|
| **1. Analyse** | Texte brut utilisateur | Produire `NormalizedSpec` (`architecture_type` + `components[]`) + auto-vérification | Générer du YAML |
| **2. Template** | Un `ServiceComponent` à la fois (champs structurels + `security_requirements` + `observability_requirements` + `sidecars`) | Manifeste K8s de base **+ sidecars dans le même Pod** **+ hardening sécurité** **+ scrape Prometheus** | Resources, HPA |
| **3. Validation** | Manifeste v1 (tous composants) + `components[]` | Corriger structure/cohérence YAML, y compris entre composants | Optimisation énergie, sécurité |
| **4. Énergie** | Un `ServiceComponent` à la fois + son YAML isolé | Ajouter `resources`, `HPA` (ou `ScaledObject` KEDA), probes... | Toucher à l'identité du workload |
| **5. Vérification finale** | Manifeste v3 (tous composants) + spec + tous les rapports | Contrôle syntaxique final + audit de traçabilité, y compris cross-composants | Corriger des choix métier des agents précédents |

> **Sécurité** : la `NormalizedSpec` isole les exigences de sécurité dans un
> champ dédié `security_requirements` (distinct de `constraints`). C'est
> l'**Agent 2** qui les implémente concrètement (securityContext durci par
> défaut, `Service.type: ClusterIP` + `NetworkPolicy` si "interne
> uniquement" est demandé, etc.), et qui documente dans
> `security_requirements_left_open` tout ce qu'il n'a pas pu traduire
> automatiquement (ex: besoins nécessitant un outil externe comme un
> service mesh ou un scanner d'image). Ces éléments non résolus remontent
> ensuite dans l'audit final de l'Agent 5, comme tout autre champ ouvert.

Chaque prompt système (`prompts/agentN_*.txt`) rappelle explicitement à
l'agent son périmètre et ce qui **n'est pas** son rôle, pour éviter les
dérives où un agent "aide" en empiétant sur le rôle du suivant.

### Correspondance avec un cahier des charges à 4 agents (Analyst/Generator/Validator/Energy Optimizer)

Si on vous demande "Analyst → Generator → Validator → Energy Optimizer",
c'est ce même pipeline, avec un découpage légèrement différent :
Analyst = **Agent 1**, Generator = **Agent 2** (qui inclut aussi la
sécurité/observabilité de base), Validator = **Agent 3**, Energy Optimizer
= **Agent 4**. L'**Agent 5** (vérification syntaxique + audit de
traçabilité) est un ajout au-delà d'un découpage à 4 agents strict, gardé
ici comme filet de sécurité déterministe plutôt que retiré.

Les critères d'acceptation habituellement associés à ce type de cahier des
charges sont déjà couverts par l'implémentation actuelle :
- **Chaîne strictement linéaire, zéro boucle/intervention d'orchestrateur** :
  `graph.py` n'a que des arêtes vers l'avant (voir `add_edge`), aucun
  retour en arrière possible dans le graphe.
- **Prompt système dédié et spécialisé par agent** : un fichier par agent
  dans `prompts/`, chacun rappelant explicitement ce qui n'est PAS son rôle.
- **Isolation de contexte stricte** : `raw_user_request` (la demande brute
  de l'utilisateur) n'est lu par AUCUN prompt des agents 2 à 5 — seul
  l'Agent 1 y a accès, tout le reste passe par les champs structurés de
  `NormalizedSpec`/`ServiceComponent`. L'Agent 4 (Énergie), en particulier,
  ne reçoit que le YAML déjà validé par l'Agent 3 et les champs énergie de
  son composant — jamais le texte original.
- **YAML final énergie-optimisé écrit sur disque** : chaque run produit
  `output/run_.../agent5_manifest_final.yaml` (voir section Utilisation).
- **Framework de chaînage** : LangGraph plutôt que LCEL/CrewAI — un choix
  différent des exemples cités, mais qui satisfait la même exigence
  fonctionnelle (chaînage séquentiel typé, sans veto explicite envers un
  framework précis dans un cahier des charges qui cite ses exemples avec
  "e.g.").

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# éditez .env et renseignez GOOGLE_API_KEY (https://aistudio.google.com/app/apikey)
```

`LLM_MODEL` dans `.env` est réglé par défaut sur `gemini-2.5-flash`, un
modèle Gemini du **tier gratuit** AI Studio (aucune carte bancaire requise).
Pour utiliser Gemma à la place, il suffit de changer cette variable (ex.
`LLM_MODEL=gemma-3-27b-it`) — le client (`llm_client.py`) est identique pour
les deux familles, via le SDK `google-genai`. Attention : depuis avril 2026,
les modèles **Pro** (`gemini-2.5-pro`, `gemini-3.x-pro`...) sont passés
payants sur AI Studio — restez sur un modèle **Flash** ou **Flash-Lite**
pour rester gratuit. Vérifiez dans votre compte AI Studio le nom exact des
modèles disponibles pour votre clé (les noms évoluent régulièrement côté
Google). L'ancienne variable `GEMMA_MODEL` reste lue en repli si `LLM_MODEL`
n'est pas définie, pour compatibilité avec un `.env` existant.

## Utilisation

```bash
python main.py "Déploie une API Node.js appelée checkout-api, image \
myregistry/checkout:1.4, 3 réplicas, port 8080, secret DB_PASSWORD, \
optimise l'énergie car trafic faible la nuit."
```

ou depuis un fichier :

```bash
python main.py --file examples/example_request.txt
```

Sorties générées dans `output/run_<horodatage>/` (un nouveau sous-dossier à
chaque exécution, rien n'est jamais écrasé) :
- `00_request.txt` — copie de la demande brute (contexte du run)
- `agent1_normalized_spec.json` — le contrat structuré produit par l'Agent 1
- `agent2_template.yaml` — manifeste de base (Agent 2)
- `agent3_validated.yaml` — manifeste validé/corrigé (Agent 3)
- `agent4_energie.yaml` — manifeste + optimisations énergie (Agent 4)
- `agent5_manifest_final.yaml` — manifeste final vérifié (Agent 5)
- `audit_report.md` — rapport de traçabilité complet

Si le pipeline s'arrête en erreur en cours de route, les fichiers déjà
produits par les agents précédents sont quand même écrits sur disque —
utile pour voir précisément à quelle étape ça a coincé.

> **Observabilité** : même logique que pour la sécurité. `observability_requirements`
> isole les besoins de monitoring (ex: "métriques Prometheus port 9091") de
> `constraints`. Sans ce champ dédié, un port de métriques finissait déclaré
> sur le conteneur mais jamais réellement scrapé (aucune annotation, aucun
> `ServiceMonitor`). L'Agent 2 ajoute désormais par défaut les annotations
> `prometheus.io/scrape`/`port`/`path` sur le pod — une approche portable qui
> ne nécessite aucun opérateur particulier dans le cluster.

## Microservices et Sidecar

Le pipeline ne suppose plus un unique conteneur/service. La `NormalizedSpec`
contient un `architecture_type` (`"single"` ou `"microservices"`) et une
liste `components` (toujours au moins un élément).

- **Sidecar** : un `ServiceComponent` peut avoir des `sidecars` — des
  conteneurs additionnels packagés dans le **même Pod** (proxy de service
  mesh, agent de logs, exportateur de métriques dédié...). L'Agent 1 ne
  les capture QUE si l'utilisateur les demande explicitement ; l'Agent 2
  les ajoute comme conteneurs supplémentaires dans le même
  `spec.template.spec.containers`, jamais comme un Deployment séparé.
- **Microservices** : si l'utilisateur décrit plusieurs services distincts
  en interaction, l'Agent 1 produit un `ServiceComponent` par service
  (avec `depends_on` pour documenter qui appelle qui). Les Agents 2 à 4
  itèrent alors sur chaque composant séparément : un appel LLM par
  composant pour le template (Agent 2) et pour l'énergie (Agent 4), avec
  uniquement les champs de CE composant dans le prompt — même principe
  de "contexte isolé par étape" qu'ailleurs dans le pipeline. L'Agent 4
  isole les documents YAML de chaque composant par correspondance de nom
  (`metadata.name == component_name`) avant d'appliquer son optimisation,
  pour ne jamais mélanger les ressources d'un composant avec celles d'un
  autre. L'Agent 5 vérifie en plus qu'aucune ressource d'un composant ne
  référence par erreur le nom d'un autre.

Une demande "normale" à un seul service reste `architecture_type: "single"`
avec un seul élément dans `components` — le comportement par défaut est
inchangé, ce mécanisme ne s'active que si la demande le justifie
réellement.

## Ressources additionnelles : Ingress, RBAC, PVC, Namespace, CronJob

Ajouté suite à un audit de couverture (voir historique) : le pipeline
générait auparavant uniquement Deployment/StatefulSet/Service/HPA/PDB. Il
couvre maintenant, toujours selon le principe "champ dédié → rôle clair →
contrôle déterministe" :

- **`Namespace`** : généré une seule fois par l'Agent 2, de façon
  déterministe en Python (pas via le LLM — évite toute duplication ou
  incohérence entre composants d'une architecture microservices).
- **`Ingress`** (`ServiceComponent.ingress`) : UNIQUEMENT si l'utilisateur
  demande explicitement un accès externe (nom de domaine, "accessible sur
  internet"...). Un domaine non précisé devient un placeholder explicite
  documenté en avertissement, jamais une valeur inventée silencieuse.
- **RBAC** (`ServiceComponent.rbac`) : un `ServiceAccount` dédié est
  TOUJOURS créé par composant (jamais le `default` — moindre privilège).
  `Role`/`RoleBinding` uniquement si des permissions sont explicitement
  demandées.
- **`PersistentVolumeClaim`** (`VolumeSpec.kind="pvc"`) : la ressource PVC
  réelle est désormais générée (pas seulement montée) ; taille par défaut
  documentée si non précisée par l'utilisateur.
- **`CronJob.spec.schedule`** (`ServiceComponent.cron_schedule`) : distinct
  du scaling KEDA — c'est le déclenchement même du Job qui est planifié.
  Validé par le même contrôle anti-inversion minute/heure que les cron KEDA.
- **Routage service mesh** (`service_mesh_routing`) et **`ServiceMonitor`**
  (`observability_style`) : générés seulement sur demande explicite, avec
  le même avertissement de dépendance externe que KEDA (Istio /
  Prometheus Operator requis).

Le matching des documents YAML par composant (Agent 4, pour l'énergie) a
été renforcé en conséquence : reconnaissance par préfixe de nom
(`<component_name>-...`) en plus du nom exact, pour couvrir ServiceAccount/
Ingress/PVC/Role sans les signaler à tort comme "orphelins". Les contrôles
déterministes (`utils/k8s_validate.py`) reconnaissent aussi la structure
imbriquée propre à `CronJob` (`spec.jobTemplate.spec.template`, différente
de `spec.template` pour les autres workloads) pour les vérifications de
labels et de quantités de ressources.

## Scaling basé sur des horaires (KEDA `cron`)

Un `HorizontalPodAutoscaler` classique scale en fonction de la charge
**observée** (ex: % CPU) — il ne garantit pas un nombre de réplicas précis
à une heure donnée, seulement une corrélation probable avec le trafic réel.

Si votre demande contient des horaires explicites (ex: *"trafic très
faible entre minuit et 6h, très élevé entre 9h et midi"*), l'Agent 1 les
capture dans un champ structuré dédié `traffic_windows` (distinct
d'`energy_goals`, qui reste du texte libre). L'Agent 4 détecte ce champ
et génère alors, **à la place** du `HorizontalPodAutoscaler` classique,
un `ScaledObject` [KEDA](https://keda.sh) combinant :
- un trigger `cron` par fenêtre horaire "faible" (force le nombre de
  réplicas voulu sur ce créneau) ;
- un trigger `cpu` pour rester réactif en dehors de ces créneaux.

⚠️ **Cette approche nécessite l'opérateur KEDA installé sur le cluster
cible** (`kubectl get pods -n keda` pour vérifier). Le rapport de l'Agent 4
le rappelle systématiquement dans `warnings` quand un `ScaledObject` est
généré, avec l'alternative (un `HorizontalPodAutoscaler` classique avec les
mêmes bornes min/max, moins précis sur les horaires mais sans dépendance
externe) si KEDA n'est pas disponible dans votre cluster.

Si aucun horaire précis n'est mentionné dans la demande, le comportement
par défaut est inchangé : un simple `HorizontalPodAutoscaler` réactif au
CPU, sans dépendance supplémentaire.

## Validation contre un cluster réel (`--kubeconform`, `--dry-run-apply`)

`utils/k8s_validate.py` fait des vérifications déterministes "maison"
(cohérence de noms, format de quantités, expressions cron...). Ce n'est PAS
une validation contre les vrais schémas OpenAPI Kubernetes. Deux options
CLI ajoutent cette couche, **toutes deux optionnelles** :

```bash
# Validation contre les schémas OpenAPI réels (+ CRD KEDA/Istio/Prometheus
# Operator via un catalogue communautaire). Nécessite kubeconform installé :
# https://github.com/yannh/kubeconform#installation
python main.py --file examples/example_request.txt --kubeconform

# kubectl apply --dry-run=server contre le cluster actuellement configuré
# (ex: un cluster kind/k3d local) — déclenche aussi les admission webhooks
# (policies OPA/Kyverno/Gatekeeper si le cluster en a).
python main.py --file examples/example_request.txt --dry-run-apply --kube-context kind-test

# Vérifie que les CRD requises (KEDA, Istio, Prometheus Operator, Argo
# Rollouts) sont bien installées sur le cluster cible, pour les kinds
# effectivement générés dans ce run.
python main.py --file examples/example_request.txt --check-cluster-deps
```

Si `kubeconform`/`kubectl` ne sont pas installés, ces options dégradent
proprement (avertissement dans le rapport, le run continue normalement) —
ce ne sont pas des pré-requis pour utiliser le pipeline.

## Mode interactif (`--interactive`)

```bash
python main.py --interactive "Déploie une API de paiement..."
```

Exécute l'Agent 1 seul en amont ; s'il a des ambiguïtés non résolues
(`spec.ambiguities` non vide), pose une question ciblée par ambiguïté
avant de lancer le pipeline complet (5 agents, toujours strictement
séquentiel — le graphe lui-même ne boucle jamais). Si aucune clarification
n'est apportée, les hypothèses initiales de l'Agent 1 sont conservées.

## Dimensionnement basé sur des métriques réelles (`--metrics-source`)

Par défaut, l'Agent 4 dimensionne `resources.requests/limits` par
heuristique LLM. Avec des métriques mesurées réelles (export Prometheus,
recommandation VPA...), le dimensionnement devient un calcul déterministe
(`utils/cost_estimate.py`) : `requests = p50 mesuré`, `limits = p95 mesuré
* marge de sécurité` — remplace la sortie du LLM pour ce composant.

```bash
cat > metrics.json << 'EOF'
{
  "checkout-api": {
    "cpu_p50": "120m", "cpu_p95": "280m",
    "memory_p50": "180Mi", "memory_p95": "310Mi"
  }
}
EOF
python main.py --file examples/example_request.txt --metrics-source metrics.json
```

## Estimation de coût (`--cost-estimate`)

```bash
python main.py --file examples/example_request.txt --cost-estimate
```

Calcule un coût mensuel approximatif par composant à partir de
`resources.requests` × réplicas × tarifs génériques €/vCPU et €/Go RAM
(`utils/cost_estimate.py`). **C'est un ordre de grandeur pour comparer des
scénarios entre eux (avant/après optimisation énergie), pas une facture**
— le coût réel dépend du cloud provider, de la région, du type
d'instance, etc.

## Détection de dépendances circulaires (microservices)

Automatique, sans option à activer : si des `depends_on` entre composants
forment un cycle (A→B→A) ou pointent vers un composant inexistant,
`utils/dependency_graph.py` le détecte et le signale dans la section
"Architecture détectée" du rapport d'audit — le pipeline continue de
tourner (chaîne stricte oblige) mais le cycle est rendu visible.

## Policies d'admission (`admission_policies`)

Génération **volontairement déterministe** (pattern matching Python,
`utils/admission_policies.py`), PAS via le LLM : le risque qu'une règle de
sécurité mal traduite bloque tout un cluster (ou pire, laisse passer ce
qu'elle devait empêcher) est jugé trop élevé pour laisser un LLM
improviser ici. Seuls quelques patterns bien connus sont reconnus (limits
de ressources obligatoires, non-root obligatoire, tag d'image explicite
obligatoire) et génèrent un squelette `ClusterPolicy` Kyverno en mode
`Audit` (jamais `Enforce` par défaut — à activer après revue humaine).
Toute description non reconnue est listée comme non résolue plutôt que
traduite au hasard.

## Tests

```bash
pip install pytest
pytest tests/ -v
```

63 tests, tous avec LLM entièrement mocké (aucun appel réseau, aucune clé
API requise) : câblage du `StateGraph`, parsing JSON→Pydantic, non-
régression sur chaque bug réel rencontré au fil du développement (cron KEDA
inversé, faux positifs de cross-référence StatefulSet/CronJob, clé de
secret non documentée...), scénarios Job/CronJob/microservices/sidecars
multiples/dépendances circulaires, et les nouveaux modules déterministes
(`cost_estimate`, `cluster_validate`, `admission_policies`,
`dependency_graph`) testés isolément avec `subprocess`/`input` mockés.

## Structure du projet

```
pipeline-kubegen/
├── main.py                     # CLI (+ --interactive, --kubeconform, --dry-run-apply,
│                                #   --check-cluster-deps, --metrics-source, --cost-estimate)
├── graph.py                     # Assemblage LangGraph (chaîne stricte)
├── schemas.py                    # NormalizedSpec, ServiceComponent, PipelineState...
├── config.py                     # Lecture .env
├── llm_client.py                  # Appel Gemma/Gemini via Google AI Studio
├── prompts/                       # Un prompt système par agent
├── agents/
│   ├── agent1_analyse.py           # Extraction + auto-vérification + réparation
│   ├── agent2_template.py           # Template + sidecars + Ingress/RBAC/PVC/ConfigMap/
│   │                                #   NetworkPolicy/Rollout/policies d'admission/
│   │                                #   Gateway API/cert-manager/multi-cluster/best-effort
│   ├── agent3_validation.py          # Validation structurelle
│   ├── agent4_energie.py              # HPA/ScaledObject, resources (LLM ou métriques réelles)
│   └── agent5_verification.py          # Vérif syntaxique + audit traçabilité
├── utils/
│   ├── yaml_utils.py                    # Parsing YAML multi-documents
│   ├── k8s_validate.py                   # Checks déterministes "maison" (Python pur)
│   ├── cluster_validate.py                # kubeconform / dry-run-apply / CRD cluster
│   ├── cost_estimate.py                    # Dimensionnement métriques + coût estimé
│   ├── dependency_graph.py                  # Détection de cycles depends_on
│   ├── admission_policies.py                 # Squelettes Kyverno (pattern matching)
│   ├── multi_cluster.py                       # Squelette ArgoCD ApplicationSet
│   ├── llm_metrics.py                          # Latence/appels/tokens (collecteur global)
│   └── logging_utils.py                         # Affichage console (rich)
├── examples/example_request.txt
└── tests/                                       # 89 tests, LLM/subprocess/input mockés
```

## Métriques d'exécution (latence, appels LLM, tokens)

Chaque run mesure automatiquement, sans option à activer :

- **Latence totale** du run (mode interactif + pipeline + validations
  externes optionnelles), et latence du pipeline seul séparément.
- **Nombre d'appels LLM**, avec le détail de chaque tentative de retry ou
  de repli (ex: le repli sans `response_mime_type=application/json` quand
  le mode JSON strict échoue déclenche un vrai deuxième appel réseau,
  comptabilisé séparément — jamais fusionné avec le premier).
- **Tokens consommés** (prompt + completion), extraits de
  `response.usage_metadata` du SDK `google-genai`. Si le SDK ne renvoie
  pas cette information pour un appel donné, les tokens sont marqués
  explicitement **inconnus** plutôt que comptés comme zéro — la distinction
  reste visible à tous les niveaux d'agrégation.

Le détail est ventilé **par agent**, y compris les sous-étapes internes de
l'Agent 1 (extraction / self-check / réparation) qui sont chacune un appel
LLM distinct. Deux sorties :

- `output/run_.../execution_metrics.json` — données brutes structurées.
- Section dédiée dans `audit_report.md` — tableau lisible par agent.

Implémentation (`utils/llm_metrics.py`) : un collecteur global, remis à
zéro au tout début de chaque exécution CLI (avant même le mode
`--interactive`, qui fait lui-même un vrai appel LLM). L'instrumentation
vit dans `llm_client.py` — les tests du pipeline mockent `call_llm` au
niveau de chaque agent et ne l'exercent donc jamais directement ; des
tests dédiés (`tests/test_llm_metrics.py`) valident l'extraction de tokens
et la mesure de latence avec le client Google GenAI mocké à un niveau plus
bas (`_get_client`), y compris le cas du repli à deux appels réseau.

## Le filet de sécurité générique : `unmapped_requirements`

Tous les champs ajoutés jusqu'ici (sécurité, Gateway API, cert-manager...)
partagent une faiblesse structurelle : ils couvrent ce qui a déjà été
anticipé. Le vrai risque révélé en testant Gateway API avant qu'il ait son
propre champ : quand une demande sort du périmètre connu, l'Agent 1 peut
la **réinterpréter silencieusement** pour la faire rentrer dans un champ
existant qui ne lui correspond pas (ex: Gateway API compris comme "Ingress
avec une classe appelée gateway-api"). Résultat : un audit qui affiche
"Aucun point ouvert détecté ✅" alors que la demande a été mal comprise —
plus dangereux qu'un champ vide, parce qu'une fausse correspondance a l'air
correcte.

`NormalizedSpec.unmapped_requirements` répond à ce problème sans étendre
le schéma à chaque nouveau cas imprévu :

- L'Agent 1 y dépose toute exigence qui ne correspond à AUCUN champ
  existant, même approximativement — jamais forcée dans un champ voisin.
  Le nom du champ reste toujours le même ; seul le contenu texte varie.
- L'Agent 2 génère un fragment YAML **best-effort séparé** pour ces
  exigences — **un appel LLM par exigence** (pas un appel groupé pour
  toute la liste : une réponse volumineuse couvrant plusieurs exigences
  risquait de dépasser `LLM_MAX_OUTPUT_TOKENS` et d'être tronquée avant
  la fin, ce qui faisait échouer TOUT le bloc, y compris les exigences
  qui auraient été correctement traitées seules), toujours précédé d'un
  commentaire `⚠️ GÉNÉRATION LIBRE`. Le chemin structuré habituel
  (`include={...}`) n'est jamais modifié par ce mécanisme.
- Si un fragment généré n'est pas du YAML syntaxiquement valide, il est
  automatiquement mis en **quarantaine** (transformé en commentaire inerte)
  **individuellement** — plutôt que de faire planter le reste du pipeline
  ou de quarantainer aussi les fragments valides des autres exigences —
  une génération best-effort ne doit jamais pouvoir couler la partie
  connue et correcte.
- L'audit final a une section dédiée, structurellement garantie : tant que
  `unmapped_requirements` n'est pas vide, le rapport ne peut plus jamais
  afficher "Aucun point ouvert détecté" (vérification indépendante de la
  bonne propagation par les agents, en défense en profondeur).

### Le trou qui restait : que se passe-t-il si l'Agent 1 n'obéit pas ?

Bug réel trouvé sur un run en conditions réelles (API Gemini, pas un mock) :
malgré la consigne, le LLM a parfois créé un `components[]` invalide pour
représenter une ressource hors périmètre (ex: un opérateur PostgreSQL avec
un `workload_type: "PostgresCluster"` qui n'existe pas dans l'énumération,
et une `image` manquante) au lieu d'utiliser `unmapped_requirements`.
Résultat avant correction : `NormalizedSpec.model_validate()` levait une
`ValidationError` **non rattrapée**, qui faisait planter tout le run — y
compris la partie de la demande parfaitement valide.

Trois niveaux de correction, dans `agents/agent1_analyse.py` et `schemas.py` :
1. **Coercion tolérante** sur les champs enum "administratifs" à faible
   impact (`cert_manager_issuer_kind`, `api_style`, `observability_style`,
   `architecture_type`, `deployment_strategy.strategy`, `PortSpec.protocol`) :
   une valeur `null` ou mal castée retombe sur le défaut documenté plutôt
   que de faire planter la validation. Les champs à fort impact fonctionnel
   (`workload_type`, `VolumeSpec.kind`) restent volontairement stricts — un
   défaut silencieux y serait plus dangereux qu'une erreur visible.
2. **Réparation de schéma ciblée** : si la validation échoue malgré tout,
   un second appel LLM reçoit les erreurs Pydantic exactes (chemin du
   champ, message, valeur reçue) et corrige uniquement ce qui est cassé —
   avec pour instruction explicite de déplacer vers `unmapped_requirements`
   toute entrée qui n'aurait jamais dû être un `component`.
3. **Filet de sécurité déterministe final** : si même la réparation via
   LLM échoue après plusieurs tentatives, les `components[i]` fautifs sont
   retirés par du code Python (pas un nouvel appel LLM), en ne retirant
   QUE ce qui est rattachable sans ambiguïté à un composant précis — une
   erreur au niveau racine de la spec ne déclenche jamais de retrait au
   hasard, le run échoue proprement dans ce cas plutôt que de deviner.

Testé par reproduction fidèle du bug exact observé (`tests/test_agent1_schema_recovery.py`).

### Deux autres bugs réels trouvés en creusant plus loin

**Le bloc best-effort pouvait disparaître à l'étape suivante.** L'Agent 3
régénère tout le YAML via un appel LLM — rien ne garantissait qu'il
préserve le bloc best-effort de l'Agent 2 en le jugeant "hors sujet" lors
de sa réécriture. Corrigé par `_split_off_unmapped_block()` dans
`agents/agent3_validation.py` : le bloc est isolé AVANT l'appel LLM
(l'Agent 3 ne le voit donc jamais, ne peut pas le juger inutile) et
réinjecté APRÈS, par code, quoi qu'ait fait le LLM entre-temps. Testé en
simulant explicitement un LLM qui "oublie" le bloc
(`tests/test_agent3_unmapped_isolation.py`).

**Les sidecars à injection automatique (Dapr, Istio, Linkerd...) étaient
mal générés**, pas par manque d'isolation de contexte mais par manque de
connaissance métier dans le prompt : `sidecars` est bien un champ
structuré, l'Agent 2 reçoit toute l'info nécessaire, mais le prompt
traitait tout sidecar de façon générique ("conteneur additionnel dans le
Pod"), alors que Dapr/Istio/Linkerd fonctionnent par injection automatique
via annotations, pas par déclaration manuelle d'un conteneur. Corrigé dans
`prompts/agent2_system.txt` : ces systèmes reconnus utilisent maintenant
leur convention d'injection propre (ex: `dapr.io/enabled: "true"` sur les
annotations du pod) plutôt qu'un conteneur manuel dans `containers[]`.

Un troisième correctif, plus délicat (faire connaître au fragment
best-effort les exigences de sécurité/dépendances du composant connu
associé), a été délibérément laissé de côté pour l'instant : plus on ouvre
le contexte transmis à la génération best-effort, plus on se rapproche du
risque qu'on cherche justement à éviter — un LLM avec plus de surface pour
halluciner des connexions inventées entre composants. À tester séparément
si le besoin se confirme, pour pouvoir attribuer clairement l'effet de ce
changement précis plutôt que de le mélanger avec d'autres.

Limite honnête, assumée : ces fragments passent par `kubeconform`
(validation syntaxique générique, fonctionne pour n'importe quel `kind`)
mais PAS par les cross-vérifications spécifiques (`check_httproute_cross_references`
et consorts), qui ne peuvent exister que pour des types anticipés à
l'avance. C'est la différence assumée entre "universel et fiable partout"
(impossible) et "capable de tenter n'importe quoi, honnête sur ce qui a
été vraiment vérifié" (atteignable).

## Gateway API, cert-manager, StatefulSet natif, multi-cluster

Ajouté suite à un second audit de couverture :

- **Gateway API** : `IngressSpec.api_style="gateway_api"` génère un
  `HTTPRoute` (`gateway.networking.k8s.io`) au lieu d'un `Ingress`
  classique, rattaché à une `Gateway` existante (`gateway_name`) si
  fournie, sinon un squelette de `Gateway` avec avertissement explicite à
  faire réviser par l'équipe infra. Comportement par défaut (`"ingress"`)
  inchangé.
- **cert-manager** : `IngressSpec.cert_manager_issuer` génère une vraie
  ressource `Certificate` (`cert-manager.io/v1`) référençant l'`Issuer`/
  `ClusterIssuer` donné, avec avertissement de dépendance externe. Sans ce
  champ, comportement inchangé (Secret TLS simplement référencé).
- **`volumeClaimTemplates` natif (StatefulSet)** : pour un composant
  `workload_type="StatefulSet"` avec un volume `kind="pvc"`, l'Agent 2
  utilise désormais `spec.volumeClaimTemplates` (un volume PAR RÉPLICA, le
  mécanisme natif K8s) au lieu d'un PVC externe partagé — l'ancien
  comportement aurait fait partager le même volume par tous les réplicas,
  cassant l'isolation des données. `utils/k8s_validate.py` détecte
  explicitement cet anti-pattern s'il réapparaît
  (`check_statefulset_volume_claim_templates`). Les autres types de
  workload (Deployment, DaemonSet, Job, CronJob) continuent d'utiliser un
  PVC externe classique, inchangé.
- **Multi-cluster** : `target_clusters` non vide déclenche désormais la
  génération DÉTERMINISTE (pas de LLM, pour éviter d'halluciner des
  adresses de cluster ou une URL de dépôt Git) d'un squelette `ApplicationSet`
  ArgoCD avec un générateur `list` (une entrée par cluster), placeholders
  explicites pour l'URL API de chaque cluster et le dépôt GitOps —
  toujours pas une orchestration multi-cluster fonctionnelle "out of the
  box" (impossible sans les vraies informations d'accès), mais un point de
  départ structurellement correct, validé contre le vrai schéma OpenAPI
  ArgoCD via kubeconform.

Tous les quatre validés par des tests dédiés + un test d'intégration bout-
en-bout qui combine les quatre en même temps et vérifie le résultat contre
`utils/k8s_validate.py` ET le vrai binaire `kubeconform` (schémas
`gateway.networking.k8s.io`, `cert-manager.io`, `argoproj.io` via le
catalogue CRD communautaire).

## Limites connues (honnêtes, pas exhaustives)

Même après ces deux tours d'extension, ce pipeline ne couvre pas "tous les
cas possibles" — voir la discussion complète dans l'historique du projet.
Encore hors périmètre : gestion complète du cycle de vie cert-manager
(le pipeline crée le `Certificate`, mais ne peut pas garantir que
cert-manager traite effectivement la demande ni que l'Issuer référencé est
valide), création automatique de `GatewayClass` (seul un placeholder est
généré si aucune `Gateway` existante n'est fournie), et toute
authentification/accès réel aux clusters listés dans `target_clusters`
(le pipeline ne peut techniquement pas connaître ces informations). La
traduction RBAC/service mesh par le LLM reste "au mieux" — à revoir avant
tout déploiement sensible. `--dry-run-apply` et `--check-cluster-deps`
nécessitent un accès réseau à un vrai cluster : sans lui, ce sont
`--kubeconform` et `utils/k8s_validate.py` qui portent l'essentiel de la
détection d'erreurs.
