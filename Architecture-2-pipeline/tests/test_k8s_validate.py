"""
tests/test_k8s_validate.py

Test de non-régression pour un bug réel rencontré en usage : le cross-check
déterministe (utils/k8s_validate.py) ne reconnaissait que `kind ==
"Deployment"`, ce qui faisait remonter des faux positifs ("Service/HPA
orphelin") dès que l'Agent 1/2 choisissait à juste titre un StatefulSet ou
un DaemonSet (ex: pour un besoin de traitement de flux avec identité
stable). Corrigé en généralisant à WORKLOAD_KINDS.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.k8s_validate import (  # noqa: E402
    full_validation, check_cross_references, check_keda_cron_triggers,
    check_cronjob_schedules, check_ingress_cross_references,
    check_rbac_cross_references, check_pvc_cross_references,
    check_resource_quantities,
)


def _statefulset_service_hpa_pdb(kind: str) -> list[dict]:
    workload = {
        "apiVersion": "apps/v1",
        "kind": kind,
        "metadata": {"name": "data-processor", "namespace": "default"},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "data-processor"}},
            "template": {
                "metadata": {"labels": {"app": "data-processor"}},
                "spec": {
                    "containers": [{
                        "name": "data-processor",
                        "image": "data-processor:latest",
                        "resources": {
                            "requests": {"cpu": "250m", "memory": "512Mi"},
                            "limits": {"cpu": "500m", "memory": "1Gi"},
                        },
                    }]
                },
            },
        },
    }
    if kind == "StatefulSet":
        workload["spec"]["serviceName"] = "data-processor"

    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "data-processor", "namespace": "default"},
        "spec": {"selector": {"app": "data-processor"}, "ports": [{"port": 9090}]},
    }
    hpa = {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": "data-processor-hpa", "namespace": "default"},
        "spec": {
            "scaleTargetRef": {"apiVersion": "apps/v1", "kind": kind, "name": "data-processor"},
            "minReplicas": 1,
            "maxReplicas": 3,
        },
    }
    pdb = {
        "apiVersion": "policy/v1",
        "kind": "PodDisruptionBudget",
        "metadata": {"name": "data-processor-pdb", "namespace": "default"},
        "spec": {"minAvailable": 1, "selector": {"matchLabels": {"app": "data-processor"}}},
    }
    return [service, workload, hpa, pdb]


def test_statefulset_is_recognized_as_workload():
    docs = _statefulset_service_hpa_pdb("StatefulSet")
    errors = check_cross_references(docs)
    assert errors == [], f"Faux positifs détectés sur un StatefulSet valide : {errors}"


def test_daemonset_is_recognized_as_workload():
    docs = _statefulset_service_hpa_pdb("DaemonSet")
    errors = check_cross_references(docs)
    assert errors == [], f"Faux positifs détectés sur un DaemonSet valide : {errors}"


def test_deployment_still_works_as_before():
    docs = _statefulset_service_hpa_pdb("Deployment")
    errors = check_cross_references(docs)
    assert errors == []


def test_genuinely_orphaned_service_is_still_caught():
    """S'assure qu'on n'a pas supprimé la détection légitime en généralisant."""
    docs = _statefulset_service_hpa_pdb("StatefulSet")
    # On casse volontairement le selector du Service
    docs[0]["spec"]["selector"] = {"app": "wrong-app-name"}
    errors = check_cross_references(docs)
    assert any("data-processor" in e and "selector" in e for e in errors)


def test_full_validation_passes_on_real_generated_manifest():
    docs = _statefulset_service_hpa_pdb("StatefulSet")
    assert full_validation(docs) == []


def test_keda_scaledobject_is_cross_checked():
    docs = _statefulset_service_hpa_pdb("Deployment")
    # On retire le HPA classique et on ajoute un ScaledObject KEDA à la place
    docs = [d for d in docs if d.get("kind") != "HorizontalPodAutoscaler"]
    scaledobject = {
        "apiVersion": "keda.sh/v1alpha1",
        "kind": "ScaledObject",
        "metadata": {"name": "data-processor-so", "namespace": "default"},
        "spec": {
            "scaleTargetRef": {"name": "data-processor"},
            "minReplicaCount": 2,
            "maxReplicaCount": 8,
            "triggers": [
                {"type": "cron", "metadata": {
                    "timezone": "UTC", "start": "0 0 * * *", "end": "0 6 * * *",
                    "desiredReplicas": "2",
                }},
                {"type": "cpu", "metadata": {"type": "Utilization", "value": "60"}},
            ],
        },
    }
    docs.append(scaledobject)
    assert check_cross_references(docs) == []

    # ScaledObject pointant vers un workload inexistant -> doit être détecté
    scaledobject["spec"]["scaleTargetRef"]["name"] = "typo-name"
    errors = check_cross_references(docs)
    assert any("ScaledObject" in e for e in errors)


def _scaledobject_with_crons(start: str, end: str) -> list[dict]:
    return [{
        "apiVersion": "keda.sh/v1alpha1",
        "kind": "ScaledObject",
        "metadata": {"name": "checkout-api-scaler", "namespace": "payments"},
        "spec": {
            "scaleTargetRef": {"name": "checkout-api"},
            "minReplicaCount": 2,
            "maxReplicaCount": 8,
            "triggers": [
                {"type": "cron", "metadata": {"timezone": "UTC", "start": start, "end": end,
                                               "desiredReplicas": "2"}},
                {"type": "cpu", "metadata": {"type": "Utilization", "value": "60"}},
            ],
        },
    }]


def test_keda_cron_with_inverted_minute_hour_is_caught():
    """
    Bug réel rencontré en usage : le LLM a généré '0 * * * *' / '6 * * * *'
    pour représenter "minuit" et "6h" — syntaxiquement valide, mais ces
    expressions s'exécutent TOUTES LES HEURES (champ heure = '*') au lieu
    d'une fois par jour. Doit être détecté même sans traffic_windows.
    """
    docs = _scaledobject_with_crons("0 * * * *", "6 * * * *")
    errors = check_keda_cron_triggers(docs)
    assert len(errors) == 2
    assert all("HEURE est '*'" in e for e in errors)


def test_keda_cron_correct_format_is_not_flagged():
    docs = _scaledobject_with_crons("0 0 * * *", "0 6 * * *")
    errors = check_keda_cron_triggers(docs)
    assert errors == []


def test_keda_cron_wrong_field_count_is_caught():
    docs = _scaledobject_with_crons("0 0 * *", "0 6 * * *")  # 4 champs au lieu de 5
    errors = check_keda_cron_triggers(docs)
    assert len(errors) == 1
    assert "4 trouvé" in errors[0]


def test_keda_cron_hour_mismatch_with_traffic_windows_is_caught():
    docs = _scaledobject_with_crons("0 3 * * *", "0 6 * * *")  # 3h au lieu de 0h attendu
    traffic_windows = [{"start_time": "00:00", "end_time": "06:00", "level": "low"}]
    errors = check_keda_cron_triggers(docs, traffic_windows)
    assert len(errors) == 1
    assert "l'heure 3" in errors[0]


def test_full_validation_catches_broken_cron_end_to_end():
    """Reproduit exactement le manifeste bogué signalé par l'utilisateur."""
    workload = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "checkout-api", "namespace": "payments"},
        "spec": {
            "selector": {"matchLabels": {"app": "checkout-api"}},
            "template": {
                "metadata": {"labels": {"app": "checkout-api"}},
                "spec": {"containers": [{
                    "name": "checkout-api",
                    "resources": {"requests": {"cpu": "100m", "memory": "256Mi"},
                                  "limits": {"cpu": "500m", "memory": "512Mi"}},
                }]},
            },
        },
    }
    scaledobject = {
        "apiVersion": "keda.sh/v1alpha1",
        "kind": "ScaledObject",
        "metadata": {"name": "checkout-api-scaler", "namespace": "payments"},
        "spec": {
            "scaleTargetRef": {"name": "checkout-api"},
            "minReplicaCount": 2,
            "maxReplicaCount": 8,
            "triggers": [
                {"type": "cron", "metadata": {"timezone": "UTC", "start": "0 * * * *",
                                               "end": "6 * * * *", "desiredReplicas": "2"}},
                {"type": "cron", "metadata": {"timezone": "UTC", "start": "9 * * * *",
                                               "end": "12 * * * *", "desiredReplicas": "8"}},
                {"type": "cpu", "metadata": {"type": "Utilization", "value": "60"}},
            ],
        },
    }
    docs = [workload, scaledobject]
    traffic_windows = [
        {"start_time": "00:00", "end_time": "06:00", "level": "low"},
        {"start_time": "09:00", "end_time": "12:00", "level": "high"},
    ]
    errors = full_validation(docs, traffic_windows)
    assert len(errors) == 4  # start+end pour chacun des 2 triggers cron


# ---------------------------------------------------------------------------
# Nouveaux contrôles : CronJob.spec.schedule, Ingress, RBAC, PVC
# ---------------------------------------------------------------------------

def test_cronjob_schedule_inverted_minute_hour_is_caught():
    docs = [{"apiVersion": "batch/v1", "kind": "CronJob", "metadata": {"name": "nightly"},
             "spec": {"schedule": "3 * * * *"}}]
    errors = check_cronjob_schedules(docs)
    assert len(errors) == 1
    assert "HEURE est '*'" in errors[0]


def test_cronjob_schedule_correct_is_not_flagged():
    docs = [{"apiVersion": "batch/v1", "kind": "CronJob", "metadata": {"name": "nightly"},
             "spec": {"schedule": "0 3 * * *"}}]
    assert check_cronjob_schedules(docs) == []


def test_cronjob_schedule_missing_is_caught():
    docs = [{"apiVersion": "batch/v1", "kind": "CronJob", "metadata": {"name": "nightly"},
             "spec": {}}]
    errors = check_cronjob_schedules(docs)
    assert len(errors) == 1
    assert "manquant" in errors[0]


def test_ingress_backend_service_must_exist():
    docs = [
        {"apiVersion": "networking.k8s.io/v1", "kind": "Ingress", "metadata": {"name": "api-ing"},
         "spec": {"rules": [{"http": {"paths": [{"backend": {"service": {"name": "api"}}}]}}]}},
    ]
    errors = check_ingress_cross_references(docs)
    assert len(errors) == 1
    assert "'api'" in errors[0]

    docs.append({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "api"}, "spec": {}})
    assert check_ingress_cross_references(docs) == []


def test_rolebinding_must_reference_existing_role_and_serviceaccount():
    docs = [
        {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding",
         "metadata": {"name": "api-rb"}, "roleRef": {"name": "api-role"},
         "subjects": [{"kind": "ServiceAccount", "name": "api-sa"}]},
    ]
    errors = check_rbac_cross_references(docs)
    assert len(errors) == 2  # role manquant + SA manquant

    docs += [
        {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role", "metadata": {"name": "api-role"}},
        {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "api-sa"}},
    ]
    assert check_rbac_cross_references(docs) == []


def test_pvc_reference_must_exist():
    docs = [
        {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "api"},
         "spec": {"template": {"spec": {"volumes": [
             {"name": "data", "persistentVolumeClaim": {"claimName": "api-data"}}
         ]}}}},
    ]
    errors = check_pvc_cross_references(docs)
    assert len(errors) == 1
    assert "api-data" in errors[0]

    docs.append({"apiVersion": "v1", "kind": "PersistentVolumeClaim",
                 "metadata": {"name": "api-data"}, "spec": {}})
    assert check_pvc_cross_references(docs) == []


def test_pvc_storage_quantity_is_validated():
    docs = [{"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": {"name": "d"},
             "spec": {"resources": {"requests": {"storage": "10 gigs"}}}}]
    errors = check_resource_quantities(docs[0])
    assert len(errors) == 1


# ---------------------------------------------------------------------------
# ConfigMap et Rollout (Argo Rollouts)
# ---------------------------------------------------------------------------

def test_configmap_reference_via_envfrom_must_exist():
    from utils.k8s_validate import check_configmap_cross_references
    docs = [
        {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "api"},
         "spec": {"template": {"spec": {"containers": [
             {"name": "api", "envFrom": [{"configMapRef": {"name": "api-config"}}]}
         ]}}}},
    ]
    errors = check_configmap_cross_references(docs)
    assert len(errors) == 1
    assert "api-config" in errors[0]

    docs.append({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "api-config"}, "data": {}})
    assert check_configmap_cross_references(docs) == []


def test_configmap_reference_via_env_key_must_exist():
    from utils.k8s_validate import check_configmap_cross_references
    docs = [
        {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "api"},
         "spec": {"template": {"spec": {"containers": [
             {"name": "api", "env": [{"name": "LOG_LEVEL",
              "valueFrom": {"configMapKeyRef": {"name": "missing-cm", "key": "LOG_LEVEL"}}}]}
         ]}}}},
    ]
    errors = check_configmap_cross_references(docs)
    assert len(errors) == 1
    assert "missing-cm" in errors[0]


def test_rollout_is_recognized_as_workload_for_hpa():
    docs = [
        {"apiVersion": "argoproj.io/v1alpha1", "kind": "Rollout", "metadata": {"name": "api"},
         "spec": {"selector": {"matchLabels": {"app": "api"}},
                  "template": {"metadata": {"labels": {"app": "api"}},
                               "spec": {"containers": [{"name": "api"}]}}}},
        {"apiVersion": "autoscaling/v2", "kind": "HorizontalPodAutoscaler",
         "metadata": {"name": "api-hpa"},
         "spec": {"scaleTargetRef": {"name": "api"}, "minReplicas": 1, "maxReplicas": 3}},
        {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "api"},
         "spec": {"selector": {"app": "api"}}},
    ]
    assert full_validation(docs) == []


# ---------------------------------------------------------------------------
# StatefulSet + volumeClaimTemplates, HTTPRoute (Gateway API)
# ---------------------------------------------------------------------------

def test_statefulset_volume_claim_templates_correct_pattern():
    from utils.k8s_validate import check_statefulset_volume_claim_templates
    docs = [
        {"apiVersion": "apps/v1", "kind": "StatefulSet", "metadata": {"name": "db"},
         "spec": {
            "selector": {"matchLabels": {"app": "db"}},
            "volumeClaimTemplates": [
                {"metadata": {"name": "data"}, "spec": {"resources": {"requests": {"storage": "10Gi"}}}}
            ],
            "template": {"metadata": {"labels": {"app": "db"}},
                         "spec": {"containers": [{"name": "db", "volumeMounts": [
                             {"name": "data", "mountPath": "/var/lib/db"}
                         ]}]}},
         }},
    ]
    assert check_statefulset_volume_claim_templates(docs) == []


def test_statefulset_shared_external_pvc_is_anti_pattern():
    from utils.k8s_validate import check_statefulset_volume_claim_templates
    docs = [
        {"apiVersion": "apps/v1", "kind": "StatefulSet", "metadata": {"name": "db"},
         "spec": {
            "selector": {"matchLabels": {"app": "db"}},
            "template": {"metadata": {"labels": {"app": "db"}},
                         "spec": {
                             "containers": [{"name": "db", "volumeMounts": [
                                 {"name": "data", "mountPath": "/var/lib/db"}
                             ]}],
                             "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "shared"}}],
                         }},
         }},
    ]
    errors = check_statefulset_volume_claim_templates(docs)
    assert len(errors) == 1
    assert "isolation des données" in errors[0]


def test_statefulset_volume_mount_without_any_source_is_caught():
    from utils.k8s_validate import check_statefulset_volume_claim_templates
    docs = [
        {"apiVersion": "apps/v1", "kind": "StatefulSet", "metadata": {"name": "db"},
         "spec": {
            "selector": {"matchLabels": {"app": "db"}},
            "template": {"metadata": {"labels": {"app": "db"}},
                         "spec": {"containers": [{"name": "db", "volumeMounts": [
                             {"name": "orphan-mount", "mountPath": "/data"}
                         ]}]}},
         }},
    ]
    errors = check_statefulset_volume_claim_templates(docs)
    assert len(errors) == 1
    assert "orphan-mount" in errors[0]


def test_httproute_backend_service_must_exist():
    from utils.k8s_validate import check_httproute_cross_references
    docs = [
        {"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute",
         "metadata": {"name": "api-route"},
         "spec": {"rules": [{"backendRefs": [{"name": "api"}]}]}},
    ]
    errors = check_httproute_cross_references(docs)
    assert len(errors) == 1

    docs.append({"apiVersion": "v1", "kind": "Service", "metadata": {"name": "api"}, "spec": {}})
    assert check_httproute_cross_references(docs) == []


def test_full_validation_passes_statefulset_with_pvc_and_httproute():
    docs = [
        {"apiVersion": "apps/v1", "kind": "StatefulSet", "metadata": {"name": "api"},
         "spec": {
            "selector": {"matchLabels": {"app": "api"}},
            "volumeClaimTemplates": [
                {"metadata": {"name": "data"}, "spec": {"resources": {"requests": {"storage": "5Gi"}}}}
            ],
            "template": {"metadata": {"labels": {"app": "api"}},
                         "spec": {"containers": [{
                             "name": "api",
                             "resources": {"requests": {"cpu": "100m", "memory": "128Mi"},
                                           "limits": {"cpu": "200m", "memory": "256Mi"}},
                             "volumeMounts": [{"name": "data", "mountPath": "/data"}],
                         }]}},
         }},
        {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "api"},
         "spec": {"selector": {"app": "api"}}},
        {"apiVersion": "gateway.networking.k8s.io/v1", "kind": "HTTPRoute",
         "metadata": {"name": "api-route"},
         "spec": {"rules": [{"backendRefs": [{"name": "api"}]}]}},
        {"apiVersion": "cert-manager.io/v1", "kind": "Certificate", "metadata": {"name": "api-tls-cert"},
         "spec": {"secretName": "api-tls", "dnsNames": ["api.example.com"],
                  "issuerRef": {"name": "letsencrypt-prod", "kind": "ClusterIssuer"}}},
    ]
    assert full_validation(docs) == []
