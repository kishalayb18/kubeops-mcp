"""Common Kubernetes change scenarios exposed as MCP guidance."""

from __future__ import annotations

from typing import Any


KUBERNETES_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "add-hpa",
        "name": "Add or update an HPA",
        "request": "Add an HPA for the web Deployment with min 2 and max 10 replicas.",
        "resources": ["Deployment", "HorizontalPodAutoscaler"],
        "status": "supported",
    },
    {
        "id": "expose-service",
        "name": "Create or update a Service",
        "request": "Expose the web Deployment internally on port 8080.",
        "resources": ["Deployment", "Service"],
        "status": "supported",
    },
    {
        "id": "add-ingress",
        "name": "Expose an application with Ingress",
        "request": "Route api.example.com to the api Service with TLS.",
        "resources": ["Service", "Ingress"],
        "status": "planned",
    },
    {
        "id": "add-configmap",
        "name": "Add application configuration",
        "request": "Add LOG_LEVEL=info to a ConfigMap and mount it into the web Deployment.",
        "resources": ["ConfigMap", "Deployment"],
        "status": "planned",
    },
    {
        "id": "add-secret-reference",
        "name": "Reference a Secret safely",
        "request": "Inject DATABASE_URL from the existing database Secret into the api Deployment.",
        "resources": ["Secret", "Deployment"],
        "status": "planned",
    },
    {
        "id": "set-resources",
        "name": "Set resource requests and limits",
        "request": "Set the web container CPU and memory requests and limits.",
        "resources": ["Deployment"],
        "status": "planned",
    },
    {
        "id": "add-health-probes",
        "name": "Add liveness and readiness probes",
        "request": "Add HTTP readiness and liveness probes on /healthz port 8080.",
        "resources": ["Deployment"],
        "status": "planned",
    },
    {
        "id": "configure-rollout",
        "name": "Configure a rolling update",
        "request": "Set the Deployment rollout to maxUnavailable 0 and maxSurge 1.",
        "resources": ["Deployment"],
        "status": "planned",
    },
    {
        "id": "add-pdb",
        "name": "Protect availability with a PDB",
        "request": "Add a PodDisruptionBudget requiring two web pods to remain available.",
        "resources": ["PodDisruptionBudget", "Deployment"],
        "status": "planned",
    },
    {
        "id": "add-network-policy",
        "name": "Restrict network traffic",
        "request": "Allow the api pods to receive traffic only from the frontend namespace.",
        "resources": ["NetworkPolicy", "Namespace"],
        "status": "planned",
    },
    {
        "id": "schedule-cronjob",
        "name": "Schedule recurring work",
        "request": "Run the cleanup container every night at 2 AM as a CronJob.",
        "resources": ["CronJob"],
        "status": "planned",
    },
    {
        "id": "run-job",
        "name": "Run a one-time Job",
        "request": "Create a Job that runs the database migration image once.",
        "resources": ["Job"],
        "status": "planned",
    },
    {
        "id": "add-stateful-storage",
        "name": "Add persistent storage to a StatefulSet",
        "request": "Add a 20Gi persistent volume claim for each database replica.",
        "resources": ["StatefulSet", "PersistentVolumeClaim"],
        "status": "planned",
    },
    {
        "id": "standardize-metadata",
        "name": "Standardize labels and annotations",
        "request": "Apply team, environment, and cost-center labels to all web resources.",
        "resources": ["Deployment", "Service", "ConfigMap"],
        "status": "planned",
    },
    {
        "id": "configure-rbac",
        "name": "Configure workload permissions",
        "request": "Give the api ServiceAccount read-only access to ConfigMaps in its namespace.",
        "resources": ["ServiceAccount", "Role", "RoleBinding"],
        "status": "planned",
    },
]