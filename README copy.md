# KubeOps MCP

An intentionally small MCP server for safe, reviewable Kubernetes YAML changes in GitHub repositories.

## Setup

```bash
uv sync
export GITHUB_TOKEN=your-github-token
```

The token needs permission to push branches and create pull requests in the target repository. Public repositories can be inspected without a token.

## What it can do

The `inspect_repository` tool lists Kubernetes resources in a public repository. The `modify_kubernetes_repository` tool finds a named Deployment and can:

- create or update an `autoscaling/v2` HPA with requested minimum and maximum replicas;
- create or update a same-named `ClusterIP` Service using the Deployment selector;
- create a branch from the cloned default branch, commit the YAML change, push it, and open a PR against `main`.

The `list_kubernetes_scenarios` tool exposes 15 common workflows: HPA, Service, Ingress, ConfigMap, Secret references, resource sizing, health probes, rolling updates, disruption budgets, network policies, CronJobs, Jobs, StatefulSet storage, metadata standardization, and RBAC. HPA and Service are supported currently; the catalog marks the remaining workflows as planned.

For example, an MCP client can translate “the `web` Deployment has 5 replicas; add an HPA from 0 to 7 and expose it on port 80” into `deployment_name="web", hpa_min=0, hpa_max=7, ensure_service=true, service_port=80`.

Without `GITHUB_TOKEN`, changes are still validated and committed in the temporary clone but cannot be pushed or turned into a PR.

## Start from VS Code

Use the MCP controls in VS Code to start `kubeops-mcp`. The included `.vscode/mcp.json` runs the server from this project directory.

Do not start `uv run kubeops-mcp` as an interactive terminal command and press Enter. MCP servers communicate over stdin/stdout using JSON-RPC, so a blank terminal line produces an invalid JSON error. To test the protocol manually, send a valid MCP JSON-RPC message through stdin.
