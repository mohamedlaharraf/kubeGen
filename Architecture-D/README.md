# Architecture D — Pipeline à 5 agents + blackboard + débat multi-agents (K8s + énergie)

Génère des manifestes Kubernetes optimisés en énergie (HPA, requests/limits,
probes...) à partir d'une demande en langage naturel, via un pipeline à 5
agents, propulsé par **Gemini** (Google AI Studio) orchestré avec
**LangGraph**.

C'est une évolution directe de l'**Architecture C** (blackboard + boucles
bornées) : squelette identique à 5 agents, blackboard, et deux cycles
bornés inchangés — voir
["Pourquoi cette architecture existe"](#pourquoi-cette-architecture-existe)
pour le diagnostic hérité de B/C. La **seule** différence structurelle est
le remplacement de l'Agent 4 (un seul appel LLM en C) par un
**sous-système de débat multi-agents** : trois personas concurrentes
(Consolidation / Sizing / Autoscaling) proposent, se critiquent, puis un
Agent Juge tranche et fusionne — voir
["Le débat multi-agents (Agent 4)"](#le-débat-multi-agents-agent-4--consolidation-vs-sizing-vs-autoscaling)
plus bas pour le détail complet, y compris le coût réel en appels LLM.

```
Input -> Agent1 (analyse + extraction blackboard) -> Agent2 (template)
      -> Agent3 (validation) <-> [erreur schéma/sécurité ? -> Agent2 (correction) -> Agent3]* (borné, MAX_ITERATIONS)
      -> Agent4 (DÉBAT multi-agents, par composant, avec application_context) :
             ┌──> Stratégie A (Consolidation) ──┐
             ├──> Stratégie B (Sizing)          ┼──> [critique croisée]* (1-2 tours, borné) ──> Agent Juge
             └──> Stratégie C (Autoscaling)     ──┘
      -> Agent5 (vérification) -> [gap réparable ? -> repair -> Agent5]* (borné, MAX_REPAIR_ATTEMPTS)
      -> Manifeste final
```

- **Contexte isolé par étape, PLUS un blackboard de contraintes globales** :
  chaque agent ne reçoit toujours dans son prompt que les champs pertinents
  à son rôle — mais reçoit en plus, quand c'est pertinent, les contraintes
  qui traversent la frontière d'un composant unique (`global_constraints`,
  voir `schemas.GlobalConstraint`). Hérité tel quel de l'Architecture C.
- **DEUX cycles bornés indépendants**, chacun répondant à un problème
  différent (inchangés depuis C) :
  1. `agent3 <-> agent2_generator_fix` — erreurs de SCHÉMA/SÉCURITÉ
     structurées (`ValidationError`, style linter : `line`/`rule`/`message`),
     détectées tôt, corrigées par le Générateur avec ce retour explicite.
     Borné par `MAX_ITERATIONS` (défaut 3).
  2. `agent5 <-> repair` — contraintes globales du blackboard non
     respectées, détectées tard (vue complète, y compris best-effort),
     patch ciblé sans régénération. Borné par `MAX_REPAIR_ATTEMPTS`
     (défaut 2).
- **UN TROISIÈME mécanisme borné, interne à l'Agent 4** (nouveau en D,
  n'apparaît PAS comme une arête supplémentaire dans le graphe LangGraph) :
  le débat entre les 3 stratégies, borné par `DEBATE_MAX_TURNS` (défaut 1,
  plafonné en dur à 2 dans le code quelle que soit la config).
- Chaque agent-stratégie et le Juge reçoivent `application_context` — un
  résumé de 1 à 3 phrases du profil global de la demande (criticité,
  trafic, disponibilité), hérité tel quel de C.
- Un seul agent (Agent 1) voit la demande brute de l'utilisateur — voir plus
  bas comment le projet garantit qu'elle est bien comprise et transmise.

## Pourquoi cette architecture existe

Sur l'Architecture B (pipeline strict, sans aucune boucle), un test réel a
montré ceci : la demande contenait *"chiffrement au repos obligatoire pour
tous les volumes"*. Cette contrainte a été rattachée aux
`security_requirements` du composant applicatif principal (le seul visible
au moment où le LLM l'a lue) — le composant base de données, généré
séparément, n'en a **jamais hérité**. Le manifeste final de la base de
données ne comportait aucune configuration de chiffrement, alors que
c'était explicitement demandé.

Cause exacte, vérifiée dans le code de B, pas supposée : chaque agent
(Agent 2, Agent 4 en particulier) ne voit qu'UN composant à la fois —
jamais le texte brut, jamais les autres composants. Une contrainte qui
s'applique à *plusieurs* ressources n'a alors aucun moyen de traverser la
frontière d'un composant vers un autre. Le pipeline B le savait et le
documentait honnêtement dans `audit_report.md` — mais ne pouvait rien
corriger, étant strictement à sens unique.

**Les trois mécanismes de cette architecture répondent chacun à un aspect
distinct du problème :**

1. **Blackboard (`GlobalConstraint`)** : Agent 1 extrait maintenant, en plus
   des composants, une liste séparée de contraintes transversales, avec un
   `scope` explicite (`all_components` / `all_volumes` / `all_containers` /
   `specific`). Tout agent qui génère une ressource — y compris en
   best-effort, hors schéma structuré — reçoit la liste filtrée des
   contraintes qui le concernent (`utils/global_constraints.py`). Coût de
   contexte borné : on ne donne jamais le texte brut ni la spec entière à
   ces agents, seulement les quelques contraintes pertinentes.

2. **Boucle Generator <-> Validator (`ValidationError`)** : Agent 3
   distingue maintenant les problèmes MÉCANIQUES (qu'il corrige lui-même,
   comme avant) des problèmes de FOND — sécurité manquante, violation de
   schéma — qu'il signale sous forme structurée plutôt que de les corriger
   silencieusement. Le Générateur (Agent 2) reçoit ce retour explicite et
   tente une correction ciblée. Borné à `MAX_ITERATIONS` tentatives.

3. **Réparation bornée (`RepairRequest`)** : Agent 5, qui voit tout le
   manifeste (y compris le best-effort), peut émettre des demandes de
   réparation structurées et actionnables pour les gaps de contraintes
   globales, au lieu de seulement les documenter en texte libre. Un nœud
   dédié (`agents/agent_repair.py`) patch **ciblé** le document concerné,
   puis Agent 5 revérifie. Borné à `MAX_REPAIR_ATTEMPTS` passages.

Ce que ce projet NE fait PAS : donner le texte brut à tous les agents.
C'est délibéré — Agent 4 (Énergie), en particulier, continue de n'avoir
JAMAIS accès au texte original ni aux autres composants dans leur
intégralité, seulement aux contraintes globales filtrées et à un résumé
court (`application_context`) qui le concernent. Le risque inverse
(plusieurs agents réinterprétant indépendamment un texte ambigu, et se
contredisant) reste évité.

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

Ce pipeline n'est plus strictement à sens unique sur un point précis : la
boucle de réparation bornée post-Agent 5 (voir plus haut). En dehors de ce
seul cycle, rien n'est perdu silencieusement : l'utilisateur voit
précisément ce qui a été compris, ce qui a été supposé, et ce qui reste
ouvert (y compris après une tentative de réparation infructueuse), et peut
relancer une exécution avec une demande précisée si besoin.

> Autrement dit : dans une chaîne stricte, on ne peut pas éliminer le risque
> qu'un agent en amont se trompe, mais on peut (a) réduire ce risque avec de
> l'auto-vérification interne à l'étape, et (b) rendre toute perte
> **visible et traçable** plutôt que silencieuse.

## Le débat multi-agents (Agent 4) : Consolidation vs Sizing vs Autoscaling

### Pourquoi un débat plutôt qu'un seul agent Énergie

La littérature sur l'ordonnancement énergétique dans Kubernetes documente
des **stratégies concurrentes, parfois contradictoires**, plutôt qu'une
méthode consensuelle unique : consolider les pods sur peu de nœuds
réduit le nombre de nœuds actifs, mais étaler la charge protège mieux les
contraintes de SLA/disponibilité. Un agent Énergie unique (Architecture C)
applique SA heuristique, quelle qu'elle soit, sans jamais confronter son
choix à un angle différent. L'Agent 4 d'Architecture D remplace cet agent
unique par trois personas concurrentes qui débattent, puis un Agent Juge
qui tranche explicitement — voir le rapport d'avancement n°1 (état de
l'art, §2.6 et §5.4) pour la justification complète du choix du patron
Debate.

### Déroulement, par composant (indépendant d'un composant à l'autre)

```
                    ┌──> Stratégie A : Consolidation ─┐
[YAML validé] ──────┼──> Stratégie B : Sizing         ┼──> [critique croisée]* ──> Agent Juge ──> YAML final
                    └──> Stratégie C : Autoscaling   ──┘      (1-2 tours, borné)
```

1. **Fan-out (parallèle, 3 threads réels)** : les trois agents-stratégies
   reçoivent tous EXACTEMENT la même information que l'ancien Agent 4 de
   C — le YAML déjà validé du composant, ses champs énergie
   (`energy_goals`/`resource_hints`/`traffic_windows`/`constraints`),
   `global_constraints` filtrées, `application_context`. Ce qui change
   n'est **pas l'accès à l'information, mais l'angle d'attaque** imposé
   par leur prompt système (`prompts/strategy_*_system.txt`) :
   - **Consolidation** : densité des nœuds — `nodeAffinity`/`nodeSelector`
     vers un pool partagé, pas de sur-marge sur les `requests`, pas
     d'anti-affinité par défaut.
   - **Sizing** : ratio `requests`/`limits` resserré par profilage
     (`resource_hints` si fourni, sinon estimation prudente calibrée sur
     `workload_type`).
   - **Autoscaling** : HPA classique ou `ScaledObject` KEDA selon que
     `traffic_windows` est renseigné ou non ; explicitement désactivé sur
     `Job`/`CronJob` (non applicable).
2. **Débat (parallèle, 1 à `DEBATE_MAX_TURNS` tours, PLAFONNÉ EN DUR à 2
   quelle que soit la config)** : chaque stratégie reçoit les deux autres
   propositions et doit dire, pour chacune, `agrees: true` ou `false` —
   avec obligation de justifier un **conflit concret sur le YAML**, pas un
   désaccord de principe. Elle peut réviser sa proposition sur le point
   contesté (jamais en abandonnant son angle).
3. **Agent Juge (séquentiel, 1 seul appel)** : reçoit les 3 propositions
   finales + tout le transcript des critiques. Fusionne ce qui est
   complémentaire (cas le plus fréquent : Sizing touche `resources`,
   Autoscaling touche le HPA, Consolidation touche l'affinity — trois
   sections différentes du même YAML), et **tranche explicitement** chaque
   conflit réel relevé, en pesant gain énergétique attendu vs risque
   SLA/performance vs `application_context`. Produit un `reasoning`
   explicite, un `strategy_scores` (0-10 par stratégie), et
   `chosen_elements` (quelle section vient de quelle stratégie).

Le transcript complet (toutes les propositions, tous les tours, toutes les
critiques) est conservé dans `output/run_.../agent4_debate_transcript.json`
pour l'audit — voir la section Structure du projet.

### ⚠️ Coût réel : 7 appels LLM par composant, contre 1 en Architecture C

À `DEBATE_MAX_TURNS=1` (valeur par défaut) : 3 propositions initiales + 3
critiques + 1 verdict du Juge = **7 appels LLM par composant**, contre un
seul en Architecture C. À `DEBATE_MAX_TURNS=2` : 3 + 6 + 1 = **10 appels**.
Sur un scénario à plusieurs composants (ex: microservices), ce coût se
multiplie mécaniquement par composant — donnée à comparer explicitement
face au gain de qualité observé lors du benchmark A/B/C/D, dans l'esprit
du rapport d'avancement n°2 (étude comparative A vs B : ×17 en tokens pour
B, sans gain mesurable sur les scénarios simples).

### Thread-safety du client LLM

Architecture D est le **premier appelant réellement multi-thread** de
`call_llm` dans tout le projet (fan-out parallèle des stratégies).
`llm_client.py::_get_client()` protège l'initialisation paresseuse du
client `google-genai` par un `threading.Lock()` pour éviter une race sur
la toute première requête du run — coût négligeable, le verrou n'est
retenu qu'à cette première initialisation.



| Agent | Entrée | Rôle | Ne fait PAS |
|---|---|---|---|
| **1. Analyse** | Texte brut utilisateur | Produire `NormalizedSpec` (`architecture_type` + `components[]` + `global_constraints[]` + `application_context`) + auto-vérification | Générer du YAML |
| **2. Template** | Un `ServiceComponent` à la fois (champs structurels) + `global_constraints` filtrées | Manifeste K8s de base **+ sidecars** **+ hardening sécurité** **+ scrape Prometheus** | Resources, HPA |
| **2bis. Correction sur retour** (nouveau) | `current_yaml` complet + `validation_errors` d'Agent 3 | Corriger CHAQUE erreur signalée, sans rien casser d'autre | Ajouter des fonctionnalités non demandées, optimiser l'énergie |
| **3. Validation** | `current_yaml` (tous composants) + `components[]` + `global_constraints` | Corriger mécaniquement (YAML/cohérence) ; **signaler** (pas corriger) les problèmes de schéma/sécurité en `validation_errors` | Optimisation énergie, corriger elle-même la sécurité de fond |
| **4. Débat (Consolidation/Sizing/Autoscaling + Juge)** | Un `ServiceComponent` à la fois + son YAML isolé + `global_constraints` filtrées + `application_context` — identique pour les 3 stratégies ET le Juge | 3 propositions concurrentes en parallèle, 1-2 tours de critique croisée bornés, puis fusion + arbitrage explicite par le Juge (voir section dédiée plus haut) | Toucher à l'identité du workload ; le Juge ne moyenne jamais silencieusement deux choix contradictoires |
| **5. Vérification finale** | Manifeste v3/final (tous composants, y compris best-effort) + spec + tous les rapports | Contrôle syntaxique + audit + détection de gaps réparables (`repair_requests`) | Corriger elle-même les choix métier — délègue au noeud repair |
| **Réparation ciblée** | UN document précis + le gap signalé par Agent 5 | Patch ciblé de CE document, rien d'autre | Ré-optimiser ou régénérer depuis zéro |

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
charges sont couverts par l'implémentation actuelle, **à une exception
explicite près** :
- **Chaîne à 5 agents, presque entièrement linéaire** : `graph.py` a
  exactement DEUX cycles possibles dans tout le graphe — `agent3 <->
  agent2_generator_fix` (borné par `MAX_ITERATIONS`) et `agent5 <->
  repair` (borné par `MAX_REPAIR_ATTEMPTS`) — ce n'est PAS "zéro boucle",
  contrairement à l'Architecture B. C'est un choix architectural assumé et
  documenté plus haut, pas un oubli : si votre cahier des charges exige
  zéro cycle sous aucune condition, c'est l'Architecture B (voir
  `Architecture-2-pipeline/`) qu'il faut utiliser, pas celle-ci.
- **Orchestrateur + mémoire partagée (Blackboard) + boucle
  auto-correctrice Generator<->Validator** : `graph.py` (LangGraph
  `StateGraph`) joue le rôle d'orchestrateur central ; `PipelineState`
  (`current_yaml`, `validation_errors`, `iteration_count`) est le
  blackboard partagé entre Agent 2 et Agent 3 ; le Validateur poste des
  erreurs structurées (`ValidationError` : `line`/`rule`/`message`), le
  Générateur tente de les résoudre itérativement, borné par
  `MAX_ITERATIONS` (variable d'env, défaut 3) — voir
  `agents/agent3_validation.py`, `agents/agent2_template.py::run_generator_fix`,
  `graph.py::_route_after_agent3`.
- **Prompt système dédié et spécialisé par agent** : un fichier par agent
  dans `prompts/`, chacun rappelant explicitement ce qui n'est PAS son rôle.
- **Isolation de contexte stricte, avec des exceptions ciblées et
  documentées** : `raw_user_request` n'est lu par AUCUN prompt des agents
  2 à 5 — seul l'Agent 1 y a accès. Les agents 2/3/4 reçoivent en plus les
  `global_constraints` filtrées (jamais le texte brut, jamais les autres
  composants dans leur intégralité), et l'Agent 4 reçoit aussi
  `application_context` (résumé de 1-3 phrases, pas le texte brut) pour
  calibrer ses décisions de scaling — voir la section "Pourquoi cette
  architecture existe" plus haut pour pourquoi ces exceptions ont été
  introduites.
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

`GEMMA_MODEL` (ou `LLM_MODEL`, alias plus explicite) dans `.env` est réglé
par défaut sur `gemini-3.6-flash`, aligné sur l'Architecture B pour une
comparaison de benchmark à modèle égal. Vérifiez dans votre compte AI
Studio le nom exact du modèle disponible pour votre clé et ajustez cette
variable si besoin — les noms de modèles évoluent régulièrement côté
Google.

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
avant de lancer le pipeline complet (5 agents, avec ses deux cycles
bornés habituels — voir plus haut). Ce mode ne modifie rien à la
structure du graphe : il choisit juste, en amont, d'attendre une
clarification plutôt que de lancer un run complet sur une hypothèse
incertaine. Si aucune clarification n'est apportée, les hypothèses
initiales de l'Agent 1 sont conservées.

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

156 tests, tous avec LLM entièrement mocké (aucun appel réseau, aucune clé
API requise) : câblage du `StateGraph`, parsing JSON→Pydantic, non-
régression sur chaque bug réel rencontré au fil du développement (cron KEDA
inversé, faux positifs de cross-référence StatefulSet/CronJob, clé de
secret non documentée...), scénarios Job/CronJob/microservices/sidecars
multiples/dépendances circulaires, les modules déterministes
(`cost_estimate`, `cluster_validate`, `admission_policies`,
`dependency_graph`) testés isolément avec `subprocess`/`input` mockés, et
le sous-système de débat (`tests/test_agent4_debate.py`, 7 tests) :
parallélisme réel prouvé par chronométrage + identité de threads (pas
seulement "3 appels ont eu lieu"), borne `DEBATE_MAX_TURNS` respectée y
compris son plafond dur à 2, conflit réel entre stratégies détecté et
tranché explicitement par le Juge.

## Structure du projet

```
pipeline-kubegen/
├── main.py                     # CLI (+ --interactive, --kubeconform, --dry-run-apply,
│                                #   --check-cluster-deps, --metrics-source, --cost-estimate)
├── graph.py                     # Point d'entrée de compatibilité, délègue à orchestrator.py
├── orchestrator.py               # Classe Orchestrator : construction du graphe (noeuds,
│                                  #   arêtes, les 2 cycles bornés) + décisions de routage
│                                  #   (route_after_generation_validation, route_after_final_verification)
├── schemas.py                    # NormalizedSpec, ServiceComponent, PipelineState...
├── config.py                     # Lecture .env
├── llm_client.py                  # Appel Gemini via Google AI Studio (thread-safe : lock
│                                  #   sur l'init paresseuse du client, cf. Agent 4/débat)
├── prompts/
│   ├── agent1_system.txt / agent2_system.txt / agent3_system.txt / agent5_system.txt
│   ├── strategy_consolidation_system.txt      # Persona Stratégie A (Agent 4/débat)
│   ├── strategy_sizing_system.txt              # Persona Stratégie B (Agent 4/débat)
│   ├── strategy_autoscaling_system.txt          # Persona Stratégie C (Agent 4/débat)
│   ├── strategy_critique_instructions.txt        # Tour de critique (3 stratégies)
│   └── debate_judge_system.txt                    # Agent Juge (Agent 4/débat)
├── agents/
│   ├── agent1_analyse.py           # Extraction + auto-vérification + réparation
│   ├── agent2_template.py           # Template + sidecars + Ingress/RBAC/PVC/ConfigMap/
│   │                                #   NetworkPolicy/Rollout/policies d'admission/
│   │                                #   Gateway API/cert-manager/multi-cluster/best-effort
│   ├── agent3_validation.py          # Validation structurelle
│   ├── agent4_energie.py              # Hérité de C, plus branché au graphe : réutilisé
│   │                                  #   par agent4_debate.py (découpage par composant,
│   │                                  #   dimensionnement déterministe --metrics-source)
│   ├── agent4_debate.py                # Débat Consolidation/Sizing/Autoscaling + Juge (D)
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
└── tests/                                       # 156 tests, LLM/subprocess/input mockés
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
  exigences (une fois pour toute la spec, pas par composant), toujours
  précédé d'un commentaire `⚠️ GÉNÉRATION LIBRE`. Le chemin structuré
  habituel (`include={...}`) n'est jamais modifié par ce mécanisme.
- Si le fragment généré n'est pas du YAML syntaxiquement valide, il est
  automatiquement mis en **quarantaine** (transformé en commentaire inerte)
  plutôt que de faire planter le reste du pipeline — une génération
  best-effort ne doit jamais pouvoir couler la partie connue et correcte.
- L'audit final a une section dédiée, structurellement garantie : tant que
  `unmapped_requirements` n'est pas vide, le rapport ne peut plus jamais
  afficher "Aucun point ouvert détecté" (vérification indépendante de la
  bonne propagation par les agents, en défense en profondeur).

