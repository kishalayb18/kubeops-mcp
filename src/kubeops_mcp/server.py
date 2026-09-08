"""MCP tools for making reviewed Kubernetes changes in GitHub repositories."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from mcp.server.fastmcp import FastMCP

from .kubernetes import suggest_hpa, update_manifests
from .scenarios import KUBERNETES_SCENARIOS

mcp = FastMCP("KubeOps MCP")


def _run(command: list[str], cwd: Path | None = None, token: str | None = None) -> str:
    environment = os.environ.copy()
    if token:
        environment["GIT_CONFIG_COUNT"] = "1"
        environment["GIT_CONFIG_KEY_0"] = "http.extraHeader"
        environment["GIT_CONFIG_VALUE_0"] = f"Authorization: Bearer {token}"
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _repo_parts(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)
    path = parsed.path.strip("/").removesuffix(".git").split("/")
    if parsed.netloc not in {"github.com", "www.github.com"} or len(path) != 2:
        raise ValueError("repository_url must be a GitHub URL such as https://github.com/org/repo")
    return path[0], path[1]


def _github_request(url: str, token: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    if payload is not None:
        request.add_header("Content-Type", "application/json")
        request.data = json.dumps(payload).encode()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API error {error.code}: {detail}") from error


def _yaml_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix in {".yaml", ".yml"} and ".git" not in path.parts)


@mcp.tool()
def inspect_repository(repository_url: str) -> dict[str, Any]:
    """Inspect Kubernetes YAML resources in a public GitHub repository."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "repo"
        _run(["git", "clone", "--depth", "1", repository_url, str(root)])
        resources: list[dict[str, str]] = []
        for path in _yaml_files(root):
            try:
                documents = list(yaml.safe_load_all(path.read_text()))
            except yaml.YAMLError:
                continue
            for document in documents:
                if isinstance(document, dict) and document.get("kind"):
                    resources.append({"file": str(path.relative_to(root)), "kind": document["kind"], "name": document.get("metadata", {}).get("name", "")})
        return {"repository": repository_url, "resources": resources}


@mcp.tool()
def suggest_hpa_for_deployment(repository_url: str, deployment_name: str, namespace: str | None = None) -> dict[str, Any]:
    """Read a Deployment's replicas and return a reviewable HPA YAML suggestion.

    The suggested range is minReplicas=0 and maxReplicas equal to the Deployment's
    configured spec.replicas value. This tool does not modify, commit, push, or open
    a pull request.
    """
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "repo"
        _run(["git", "clone", "--depth", "1", repository_url, str(root)])
        for path in _yaml_files(root):
            try:
                documents = list(yaml.safe_load_all(path.read_text()))
            except (yaml.YAMLError, UnicodeDecodeError):
                continue
            for document in documents:
                if not isinstance(document, dict) or document.get("kind") != "Deployment":
                    continue
                metadata = document.get("metadata") or {}
                document_namespace = metadata.get("namespace", "default")
                if metadata.get("name") != deployment_name or (namespace is not None and document_namespace != namespace):
                    continue
                replicas, hpa = suggest_hpa(document)
                return {
                    "repository": repository_url,
                    "deployment": {
                        "name": deployment_name,
                        "namespace": document_namespace,
                        "file": str(path.relative_to(root)),
                        "replicas": replicas,
                    },
                    "suggestion": {"minReplicas": 0, "maxReplicas": replicas},
                    "hpa_file": "hpa.yaml",
                    "hpa_yaml": yaml.safe_dump(hpa, sort_keys=False, explicit_start=True),
                }
    raise ValueError(f"Deployment {deployment_name!r} was not found")


@mcp.tool()
def list_kubernetes_scenarios(status: str | None = None) -> list[dict[str, Any]]:
    """List common Kubernetes change scenarios that KubeOps MCP understands.

    Use this catalog to map a natural-language request to a Kubernetes workflow before
    calling a mutation tool. Supported scenarios are implemented today; planned scenarios
    document the next safe mutation workflows.
    """
    if status is not None and status not in {"supported", "planned"}:
        raise ValueError("status must be 'supported' or 'planned'")
    return [scenario for scenario in KUBERNETES_SCENARIOS if status is None or scenario["status"] == status]


@mcp.tool()
def modify_kubernetes_repository(
    repository_url: str,
    deployment_name: str,
    hpa_min: int | None = None,
    hpa_max: int | None = None,
    ensure_service: bool = False,
    service_port: int = 80,
    namespace: str | None = None,
    branch_name: str | None = None,
    commit_message: str | None = None,
    create_pull_request: bool = True,
    pull_request_title: str | None = None,
    pull_request_body: str | None = None,
) -> dict[str, Any]:
    """Modify a Deployment's YAML, optionally add an HPA and Service, then push a branch and open a PR.

    Set GITHUB_TOKEN for branch push and pull request creation. The branch is always created from the
    repository's current default branch; this tool refuses to write directly to main.
    """
    if hpa_min is None and hpa_max is not None or hpa_min is not None and hpa_max is None:
        raise ValueError("Provide both hpa_min and hpa_max for an HPA change")
    owner, repository = _repo_parts(repository_url)
    token = os.getenv("GITHUB_TOKEN")
    branch = branch_name or f"kubeops/{re.sub(r'[^a-z0-9]+', '-', deployment_name.lower()).strip('-')}-hpa-service"
    if branch in {"main", "master"}:
        raise ValueError("branch_name must be different from main")
    commit = commit_message or f"Configure {deployment_name} autoscaling and service"
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "repo"
        _run(["git", "clone", "--depth", "1", repository_url, str(root)])
        _run(["git", "checkout", "-b", branch], cwd=root)
        changed_files: list[str] = []
        changes: list[str] = []
        for path in _yaml_files(root):
            try:
                documents = list(yaml.safe_load_all(path.read_text()))
                updated, file_changes = update_manifests(documents, deployment_name, namespace, hpa_min, hpa_max, ensure_service, service_port)
            except (yaml.YAMLError, UnicodeDecodeError):
                continue
            if file_changes:
                path.write_text(yaml.safe_dump_all(updated, sort_keys=False, explicit_start=True))
                changed_files.append(str(path.relative_to(root)))
                changes.extend(f"{path.relative_to(root)}: {change}" for change in file_changes)
        if not changed_files:
            raise ValueError(f"No Kubernetes YAML was changed for Deployment {deployment_name!r}")
        _run(["git", "add", *changed_files], cwd=root)
        _run(["git", "commit", "-m", commit], cwd=root)
        if not token:
            return {"branch": branch, "changed_files": changed_files, "changes": changes, "status": "committed locally; set GITHUB_TOKEN to push and open a PR"}
        _run(["git", "push", "origin", f"HEAD:{branch}"], cwd=root, token=token)
    pr: dict[str, Any] | None = None
    if create_pull_request:
        pr = _github_request(
            f"https://api.github.com/repos/{owner}/{repository}/pulls",
            token,
            method="POST",
            payload={"title": pull_request_title or commit, "body": pull_request_body or "Created by KubeOps MCP.", "head": branch, "base": "main"},
        )
    return {"branch": branch, "changed_files": changed_files, "changes": changes, "pull_request_url": pr.get("html_url") if pr else None}


def main() -> None:
    mcp.run(transport="stdio")