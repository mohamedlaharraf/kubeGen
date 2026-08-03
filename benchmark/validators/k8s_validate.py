"""
benchmark/validators/k8s_validate.py

VENDORED depuis le projet pipeline-kubegen (Architecture B, utils/k8s_validate.py),
copié tel quel ici pour servir de VALIDATEUR UNIQUE ET COMMUN à toutes les
architectures (A, B, C, D) -- exigence E6 (instrumentation homogène) :
on ne veut PAS faire confiance au flag "yaml_valid" auto-rapporté par
chaque architecture (de rigueur très inégale -- l'architecture A n'a
volontairement qu'une validation légère), donc on applique ce même
module en post-traitement sur le YAML produit par n'importe quelle
architecture.

Aucune dépendance externe (pas de réseau, pas de binaire à installer) :
vérifications structurelles + cohérence inter-ressources (Service -> pods,
HPA -> workload, RoleBinding -> Role/ServiceAccount, PVC/ConfigMap
référencés, etc.) sur des documents déjà parsés en dict Python.

Si vous modifiez ce fichier, pensez à reporter le changement dans
pipeline-kubegen/utils/k8s_validate.py (ou inversement) pour ne pas
diverger entre les deux copies.
"""


from __future__ import annotations

import re

REQUIRED_TOP_LEVEL = {"apiVersion", "kind", "metadata"}
QUANTITY_RE = re.compile(r"^\d+(\.\d+)?(m|Mi|Gi|Ki|G|M|K)?$")

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Rollout"}
POD_TEMPLATE_KINDS = WORKLOAD_KINDS | {"Job", "CronJob"}
CROSS_CUTTING_KINDS = {"Namespace", "ServiceMonitor", "VirtualService", "DestinationRule",
                       "ClusterPolicy", "ApplicationSet", "Gateway", "Certificate"}


def _pod_template(doc: dict) -> dict:
    """
    Renvoie le `template` du Pod (contenant `metadata` et `spec`) quel que
    soit le kind — la structure diffère pour `CronJob`, dont le pod
    template est niché sous `spec.jobTemplate.spec.template` (un niveau de
    plus que Deployment/StatefulSet/DaemonSet/Job dont c'est directement
    `spec.template`). Sans ce helper, un CronJob n'est reconnu ni pour le
    matching de labels (Service/PDB orphelins à tort) ni pour la
    validation de ses quantités de ressources.
    """
    if doc.get("kind") == "CronJob":
        return (
            doc.get("spec", {}).get("jobTemplate", {}).get("spec", {}).get("template", {})
        )
    return doc.get("spec", {}).get("template", {})


def check_required_fields(doc: dict) -> list[str]:
    errors = []
    missing = REQUIRED_TOP_LEVEL - doc.keys()
    if missing:
        errors.append(f"Champs racine manquants: {sorted(missing)}")
    if "metadata" in doc and "name" not in doc.get("metadata", {}):
        errors.append("metadata.name manquant")
    return errors


def check_resource_quantities(doc: dict) -> list[str]:
    """Vérifie que les quantités CPU/mémoire (containers) et stockage (PVC)
    respectent le format Kubernetes (ex: '250m', '512Mi', '1', '2Gi')."""
    errors = []
    containers = _pod_template(doc).get("spec", {}).get("containers", [])
    for c in containers:
        res = c.get("resources", {})
        for kind in ("requests", "limits"):
            for k, v in res.get(kind, {}).items():
                if not QUANTITY_RE.match(str(v)):
                    errors.append(
                        f"Quantité invalide pour {c.get('name', '?')}.resources."
                        f"{kind}.{k} = '{v}'"
                    )

    if doc.get("kind") == "PersistentVolumeClaim":
        storage = doc.get("spec", {}).get("resources", {}).get("requests", {}).get("storage")
        if storage is not None and not QUANTITY_RE.match(str(storage)):
            errors.append(f"Quantité de stockage invalide : '{storage}'")

    return errors


def _pod_labels(workload: dict) -> dict:
    return _pod_template(workload).get("metadata", {}).get("labels", {})


def check_cross_references(docs: list[dict]) -> list[str]:
    """
    Vérifie la cohérence entre le(s) workload(s) (Deployment/StatefulSet/
    DaemonSet) et les ressources qui le référencent (Service, HPA,
    ScaledObject, PDB).
    """
    errors = []
    # Pour Service/PDB : tout kind qui produit des pods labellisés, y
    # compris Job/CronJob (un Service PEUT légitimement cibler les pods
    # d'un Job/CronJob, même si c'est un usage plus rare).
    pod_producing = {
        d["metadata"]["name"]: d for d in docs if d.get("kind") in POD_TEMPLATE_KINDS
    }
    # Pour HPA/ScaledObject : UNIQUEMENT Deployment/StatefulSet/DaemonSet —
    # un Job/CronJob n'a pas de notion de réplicas scalables dans le temps.
    scalable_workloads = {
        d["metadata"]["name"]: d for d in docs if d.get("kind") in WORKLOAD_KINDS
    }
    services = [d for d in docs if d.get("kind") == "Service"]
    hpas = [d for d in docs if d.get("kind") == "HorizontalPodAutoscaler"]
    scaledobjects = [d for d in docs if d.get("kind") == "ScaledObject"]
    pdbs = [d for d in docs if d.get("kind") == "PodDisruptionBudget"]

    for svc in services:
        selector = svc.get("spec", {}).get("selector", {})
        matched = any(
            selector and all(_pod_labels(w).get(k) == v for k, v in selector.items())
            for w in pod_producing.values()
        )
        if not matched:
            errors.append(
                f"Service '{svc.get('metadata', {}).get('name')}' : selector "
                f"{selector} ne correspond à aucun workload connu "
                f"(Deployment/StatefulSet/DaemonSet/Job/CronJob)."
            )

    for hpa in hpas:
        target = hpa.get("spec", {}).get("scaleTargetRef", {}).get("name")
        if target not in scalable_workloads:
            errors.append(
                f"HPA '{hpa.get('metadata', {}).get('name')}' cible "
                f"'{target}' qui n'existe pas parmi les workloads scalables connus."
            )

    for so in scaledobjects:
        target = so.get("spec", {}).get("scaleTargetRef", {}).get("name")
        if target not in scalable_workloads:
            errors.append(
                f"ScaledObject (KEDA) '{so.get('metadata', {}).get('name')}' "
                f"cible '{target}' qui n'existe pas parmi les workloads scalables connus."
            )

    for pdb in pdbs:
        selector = pdb.get("spec", {}).get("selector", {}).get("matchLabels", {})
        matched = any(
            selector and all(_pod_labels(w).get(k) == v for k, v in selector.items())
            for w in pod_producing.values()
        )
        if not matched:
            errors.append(
                f"PodDisruptionBudget '{pdb.get('metadata', {}).get('name')}' : "
                f"selector {selector} ne correspond à aucun workload connu."
            )

    return errors


def _validate_cron_expression(expr: str, expected_hours: set[int] | None = None) -> str | None:
    """
    Valide UNE expression cron (5 champs). Renvoie un message d'erreur ou
    None si l'expression est valide. Mutualisé entre les triggers KEDA
    (`start`/`end`) et `CronJob.spec.schedule` : même format, même piège
    fréquent (heure laissée en '*' pour un horaire quotidien fixe).
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        return (
            f"expression cron '{expr}' invalide (attendu 5 champs 'minute "
            f"heure jour mois jour_semaine', {len(parts)} trouvé(s))."
        )

    minute, hour = parts[0], parts[1]
    if hour == "*" and minute != "*":
        return (
            f"expression cron '{expr}' probablement incorrecte — le champ "
            f"HEURE est '*' (se déclenche toutes les heures) alors que le "
            f"champ MINUTE est fixé à '{minute}'. Format attendu pour un "
            f"horaire quotidien fixe : '<minute> <heure> * * *' (ex: "
            f"'0 6 * * *' pour 6h00 chaque jour)."
        )

    if expected_hours and hour != "*" and hour.isdigit():
        if int(hour) not in expected_hours:
            return (
                f"expression cron '{expr}' indique l'heure {hour}, qui ne "
                f"correspond à aucune heure attendue ({sorted(expected_hours)})."
            )

    return None


def check_keda_cron_triggers(docs: list[dict], traffic_windows: list[dict] | None = None) -> list[str]:
    """
    Vérifie les expressions cron des triggers `type: cron` d'un
    `ScaledObject` KEDA. Un LLM peut produire un cron SYNTAXIQUEMENT
    valide (5 champs) mais SÉMANTIQUEMENT faux — ex: '0 * * * *' au lieu
    de '0 0 * * *' pour "minuit". Ce genre d'erreur ne casse pas le
    parsing YAML/JSON et n'est PAS détecté par un simple `yaml.safe_load` :
    il faut une vérification dédiée.
    """
    errors = []
    scaledobjects = [d for d in docs if d.get("kind") == "ScaledObject"]
    if not scaledobjects:
        return errors

    expected_hours: set[int] = set()
    for w in (traffic_windows or []):
        for key in ("start_time", "end_time"):
            t = w.get(key)
            if t and ":" in str(t):
                try:
                    expected_hours.add(int(str(t).split(":")[0]))
                except ValueError:
                    pass

    for so in scaledobjects:
        so_name = so.get("metadata", {}).get("name", "?")
        for trig in so.get("spec", {}).get("triggers", []):
            if trig.get("type") != "cron":
                continue
            meta = trig.get("metadata", {})
            for field in ("start", "end"):
                expr = str(meta.get(field, "")).strip()
                err = _validate_cron_expression(expr, expected_hours)
                if err:
                    errors.append(f"ScaledObject '{so_name}' ({field}) : {err}")
    return errors


def check_cronjob_schedules(docs: list[dict]) -> list[str]:
    """Valide `CronJob.spec.schedule` avec la même logique que les triggers
    KEDA (5 champs, piège de l'heure en '*')."""
    errors = []
    for doc in docs:
        if doc.get("kind") != "CronJob":
            continue
        name = doc.get("metadata", {}).get("name", "?")
        schedule = doc.get("spec", {}).get("schedule")
        if not schedule:
            errors.append(f"CronJob '{name}' : spec.schedule manquant ou vide.")
            continue
        err = _validate_cron_expression(str(schedule))
        if err:
            errors.append(f"CronJob '{name}' (spec.schedule) : {err}")
    return errors


def check_ingress_cross_references(docs: list[dict]) -> list[str]:
    """Vérifie qu'un Ingress référence bien un Service existant."""
    errors = []
    service_names = {d["metadata"]["name"] for d in docs if d.get("kind") == "Service"}

    for ing in (d for d in docs if d.get("kind") == "Ingress"):
        name = ing.get("metadata", {}).get("name", "?")
        for rule in ing.get("spec", {}).get("rules", []):
            for path in rule.get("http", {}).get("paths", []):
                backend_name = (
                    path.get("backend", {}).get("service", {}).get("name")
                )
                if backend_name and backend_name not in service_names:
                    errors.append(
                        f"Ingress '{name}' : référence le Service "
                        f"'{backend_name}' qui n'existe pas parmi les "
                        f"Services connus."
                    )
    return errors


def check_rbac_cross_references(docs: list[dict]) -> list[str]:
    """Vérifie qu'un RoleBinding référence bien un ServiceAccount et un
    Role existants (même namespace)."""
    errors = []
    sa_names = {d["metadata"]["name"] for d in docs if d.get("kind") == "ServiceAccount"}
    role_names = {d["metadata"]["name"] for d in docs if d.get("kind") == "Role"}

    for rb in (d for d in docs if d.get("kind") == "RoleBinding"):
        name = rb.get("metadata", {}).get("name", "?")
        role_ref = rb.get("roleRef", {}).get("name")
        if role_ref and role_ref not in role_names:
            errors.append(
                f"RoleBinding '{name}' : roleRef '{role_ref}' ne correspond "
                f"à aucun Role connu."
            )
        for subject in rb.get("subjects", []):
            if subject.get("kind") == "ServiceAccount":
                sa_name = subject.get("name")
                if sa_name and sa_name not in sa_names:
                    errors.append(
                        f"RoleBinding '{name}' : ServiceAccount '{sa_name}' "
                        f"référencé n'existe pas parmi les ServiceAccounts connus."
                    )
    return errors


def check_statefulset_volume_claim_templates(docs: list[dict]) -> list[str]:
    """
    Vérifie que, pour un `StatefulSet`, tout `volumeMount` d'un conteneur
    qui n'est pas satisfait par un `volumes[]` classique correspond bien à
    une entrée de `spec.volumeClaimTemplates` (le mécanisme natif de
    StatefulSet — un volume PAR RÉPLICA, jamais un PVC externe partagé).

    Complémentaire de `check_pvc_cross_references` : celle-ci couvre le cas
    "PVC externe classique" (Deployment/DaemonSet/Job/CronJob), celle-ci
    couvre le cas StatefulSet natif — les deux mécanismes ne doivent
    jamais être mélangés pour le même volume.
    """
    errors = []
    for doc in docs:
        if doc.get("kind") != "StatefulSet":
            continue
        wl_name = doc.get("metadata", {}).get("name", "?")
        vct_names = {
            vct.get("metadata", {}).get("name")
            for vct in doc.get("spec", {}).get("volumeClaimTemplates", [])
        }
        pod_spec = _pod_template(doc).get("spec", {})
        explicit_volume_names = {v.get("name") for v in pod_spec.get("volumes", [])}

        for container in pod_spec.get("containers", []):
            for mount in container.get("volumeMounts", []):
                vol_name = mount.get("name")
                if vol_name in explicit_volume_names:
                    continue  # satisfait par un volume classique (emptyDir, configMap...)
                if vol_name not in vct_names:
                    errors.append(
                        f"StatefulSet '{wl_name}' : volumeMount '{vol_name}' du "
                        f"conteneur '{container.get('name', '?')}' ne correspond à "
                        f"aucune entrée de volumeClaimTemplates ni de volumes classiques."
                    )

        # Anti-pattern à détecter explicitement : un StatefulSet qui utilise
        # encore le mécanisme PVC externe (persistentVolumeClaim.claimName)
        # au lieu de volumeClaimTemplates -> perte d'isolation par réplica.
        for vol in pod_spec.get("volumes", []):
            if "persistentVolumeClaim" in vol:
                errors.append(
                    f"StatefulSet '{wl_name}' : volume '{vol.get('name')}' utilise "
                    f"un PersistentVolumeClaim externe partagé au lieu de "
                    f"volumeClaimTemplates — tous les réplicas partageraient le même "
                    f"volume, ce qui casse l'isolation des données par pod."
                )
    return errors


def check_httproute_cross_references(docs: list[dict]) -> list[str]:
    """Vérifie qu'un HTTPRoute (Gateway API) référence bien un Service
    existant, de la même façon qu'un Ingress classique."""
    errors = []
    service_names = {d["metadata"]["name"] for d in docs if d.get("kind") == "Service"}

    for route in (d for d in docs if d.get("kind") == "HTTPRoute"):
        name = route.get("metadata", {}).get("name", "?")
        for rule in route.get("spec", {}).get("rules", []):
            for backend in rule.get("backendRefs", []):
                backend_name = backend.get("name")
                if backend_name and backend_name not in service_names:
                    errors.append(
                        f"HTTPRoute '{name}' : référence le Service "
                        f"'{backend_name}' qui n'existe pas parmi les Services connus."
                    )
    return errors


def check_pvc_cross_references(docs: list[dict]) -> list[str]:
    """Vérifie que tout `persistentVolumeClaim.claimName` référencé dans un
    workload correspond bien à un PersistentVolumeClaim généré."""
    errors = []
    pvc_names = {
        d["metadata"]["name"] for d in docs if d.get("kind") == "PersistentVolumeClaim"
    }

    for workload in (d for d in docs if d.get("kind") in POD_TEMPLATE_KINDS):
        wl_name = workload.get("metadata", {}).get("name", "?")
        pod_spec = _pod_template(workload).get("spec", {})
        for vol in pod_spec.get("volumes", []):
            claim = vol.get("persistentVolumeClaim", {}).get("claimName")
            if claim and claim not in pvc_names:
                errors.append(
                    f"Workload '{wl_name}' : référence le PersistentVolumeClaim "
                    f"'{claim}' qui n'existe pas parmi les PVC connus."
                )
    return errors


def check_configmap_cross_references(docs: list[dict]) -> list[str]:
    """Vérifie que toute référence à une ConfigMap (env, envFrom, volume)
    correspond bien à une ConfigMap générée."""
    errors = []
    cm_names = {d["metadata"]["name"] for d in docs if d.get("kind") == "ConfigMap"}

    for workload in (d for d in docs if d.get("kind") in POD_TEMPLATE_KINDS):
        wl_name = workload.get("metadata", {}).get("name", "?")
        pod_spec = _pod_template(workload).get("spec", {})

        for vol in pod_spec.get("volumes", []):
            cm = vol.get("configMap", {}).get("name")
            if cm and cm not in cm_names:
                errors.append(
                    f"Workload '{wl_name}' : référence la ConfigMap '{cm}' "
                    f"(volume) qui n'existe pas parmi les ConfigMaps connues."
                )

        for container in pod_spec.get("containers", []):
            for env_from in container.get("envFrom", []):
                cm = env_from.get("configMapRef", {}).get("name")
                if cm and cm not in cm_names:
                    errors.append(
                        f"Workload '{wl_name}' : référence la ConfigMap '{cm}' "
                        f"(envFrom) qui n'existe pas parmi les ConfigMaps connues."
                    )
            for env in container.get("env", []):
                cm = env.get("valueFrom", {}).get("configMapKeyRef", {}).get("name")
                if cm and cm not in cm_names:
                    errors.append(
                        f"Workload '{wl_name}' : référence la ConfigMap '{cm}' "
                        f"(env) qui n'existe pas parmi les ConfigMaps connues."
                    )
    return errors


def full_validation(docs: list[dict], traffic_windows: list[dict] | None = None) -> list[str]:
    errors: list[str] = []
    for doc in docs:
        errors += [f"[{doc.get('kind', '?')}] {e}" for e in check_required_fields(doc)]
        errors += [f"[{doc.get('kind', '?')}] {e}" for e in check_resource_quantities(doc)]
    errors += check_cross_references(docs)
    errors += check_keda_cron_triggers(docs, traffic_windows)
    errors += check_cronjob_schedules(docs)
    errors += check_ingress_cross_references(docs)
    errors += check_rbac_cross_references(docs)
    errors += check_pvc_cross_references(docs)
    errors += check_configmap_cross_references(docs)
    errors += check_statefulset_volume_claim_templates(docs)
    errors += check_httproute_cross_references(docs)
    return errors
