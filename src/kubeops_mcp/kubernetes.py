"""Small, deterministic Kubernetes manifest transformations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _metadata(document: dict[str, Any]) -> dict[str, Any]:
    return document.setdefault("metadata", {})


def _labels(document: dict[str, Any]) -> dict[str, str]:
    return _metadata(document).setdefault("labels", {})


def _deployment_selector(deployment: dict[str, Any]) -> dict[str, str]:
    spec = deployment.setdefault("spec", {})
    selector = spec.setdefault("selector", {})
    labels = selector.get("matchLabels")
    if labels:
        return dict(labels)
    template = spec.setdefault("template", {})
    return dict(_labels(template))


def suggest_hpa(deployment: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Build an HPA suggestion using the Deployment's configured replica count."""
    metadata = _metadata(deployment)
    spec = deployment.get("spec") or {}
    replicas = spec.get("replicas", 1)
    if not isinstance(replicas, int) or isinstance(replicas, bool) or replicas < 1:
        raise ValueError("Deployment spec.replicas must be a positive integer")
    namespace = metadata.get("namespace", "default")
    name = metadata.get("name")
    if not name:
        raise ValueError("Deployment metadata.name is required")
    hpa = {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": name,
            },
            "minReplicas": 0,
            "maxReplicas": replicas,
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {"type": "Utilization", "averageUtilization": 80},
                    },
                }
            ],
        },
    }
    return replicas, hpa


def update_manifests(
    documents: list[Any],
    deployment_name: str,
    namespace: str | None,
    hpa_min: int | None,
    hpa_max: int | None,
    ensure_service: bool,
    service_port: int,
) -> tuple[list[Any], list[str]]:
    """Update one Deployment and add/update related HPA and Service resources."""
    if hpa_min is not None and hpa_max is not None and hpa_min > hpa_max:
        raise ValueError("hpa_min must be less than or equal to hpa_max")
    if hpa_min is not None and hpa_min < 0:
        raise ValueError("hpa_min cannot be negative")
    if hpa_max is not None and hpa_max < 1:
        raise ValueError("hpa_max must be at least 1")
    if not 1 <= service_port <= 65535:
        raise ValueError("service_port must be between 1 and 65535")

    deployment_index = next(
        (
            index
            for index, document in enumerate(documents)
            if isinstance(document, dict)
            and document.get("kind") == "Deployment"
            and _metadata(document).get("name") == deployment_name
            and (namespace is None or _metadata(document).get("namespace", "default") == namespace)
        ),
        None,
    )
    if deployment_index is None:
        raise ValueError(f"Deployment {deployment_name!r} was not found")

    deployment = documents[deployment_index]
    deployment_namespace = _metadata(deployment).get("namespace", namespace or "default")
    selector = _deployment_selector(deployment)
    changed: list[str] = []

    if hpa_min is not None and hpa_max is not None:
        hpa = next(
            (
                document
                for document in documents
                if isinstance(document, dict)
                and document.get("kind") == "HorizontalPodAutoscaler"
                and _metadata(document).get("name") == deployment_name
                and _metadata(document).get("namespace", "default") == deployment_namespace
            ),
            None,
        )
        if hpa is None:
            hpa = {
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {"name": deployment_name, "namespace": deployment_namespace},
                "spec": {},
            }
            documents.append(hpa)
            changed.append(f"created HPA {deployment_name}")
        spec = hpa.setdefault("spec", {})
        spec.update(
            {
                "minReplicas": hpa_min,
                "maxReplicas": hpa_max,
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": deployment_name,
                },
            }
        )
        if "metrics" not in spec:
            spec["metrics"] = [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {"type": "Utilization", "averageUtilization": 80},
                    },
                }
            ]
        if not changed or changed[-1] != f"created HPA {deployment_name}":
            changed.append(f"updated HPA {deployment_name}")

    if ensure_service:
        service = next(
            (
                document
                for document in documents
                if isinstance(document, dict)
                and document.get("kind") == "Service"
                and _metadata(document).get("name") == deployment_name
                and _metadata(document).get("namespace", "default") == deployment_namespace
            ),
            None,
        )
        if service is None:
            service = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": deployment_name, "namespace": deployment_namespace},
                "spec": {},
            }
            documents.append(service)
            changed.append(f"created Service {deployment_name}")
        service.setdefault("spec", {}).update(
            {
                "selector": deepcopy(selector),
                "ports": [{"name": "http", "port": service_port, "targetPort": service_port}],
            }
        )
        service["spec"].setdefault("type", "ClusterIP")
        if not changed or changed[-1] != f"created Service {deployment_name}":
            changed.append(f"updated Service {deployment_name}")

    return documents, changed