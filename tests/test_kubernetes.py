from kubeops_mcp.kubernetes import suggest_hpa, update_manifests
from kubeops_mcp.scenarios import KUBERNETES_SCENARIOS


def test_adds_hpa_and_service_for_deployment() -> None:
    documents = [
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "web"},
            "spec": {
                "replicas": 5,
                "selector": {"matchLabels": {"app": "web"}},
                "template": {"metadata": {"labels": {"app": "web"}}},
            },
        }
    ]

    updated, changes = update_manifests(documents, "web", None, 0, 7, True, 8080)

    assert [document["kind"] for document in updated] == ["Deployment", "HorizontalPodAutoscaler", "Service"]
    assert updated[1]["spec"]["minReplicas"] == 0
    assert updated[1]["spec"]["maxReplicas"] == 7
    assert updated[2]["spec"]["selector"] == {"app": "web"}
    assert "created HPA web" in changes
    assert "created Service web" in changes


def test_rejects_invalid_hpa_range() -> None:
    try:
        update_manifests([], "web", None, 8, 2, False, 80)
    except ValueError as error:
        assert "hpa_min" in str(error)
    else:
        raise AssertionError("invalid HPA range should fail")


def test_suggests_hpa_from_deployment_replicas() -> None:
    replicas, hpa = suggest_hpa({"kind": "Deployment", "metadata": {"name": "be"}, "spec": {"replicas": 5}})

    assert replicas == 5
    assert hpa["metadata"]["name"] == "be"
    assert hpa["spec"]["minReplicas"] == 0
    assert hpa["spec"]["maxReplicas"] == 5


def test_has_fifteen_kubernetes_scenarios() -> None:
    assert len(KUBERNETES_SCENARIOS) == 15
    assert len({scenario["id"] for scenario in KUBERNETES_SCENARIOS}) == 15
    assert [scenario["id"] for scenario in KUBERNETES_SCENARIOS if scenario["status"] == "supported"] == [
        "add-hpa",
        "expose-service",
    ]