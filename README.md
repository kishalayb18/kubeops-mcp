# KubeOps MCP

KubeOps MCP is a small [Model Context Protocol](https://modelcontextprotocol.io/)
server for reviewing and making focused Kubernetes YAML changes in GitHub
repositories. It uses the MCP `stdio` transport, so it is intended to be
started by an MCP client such as VS Code, Claude Desktop, or another MCP host.

## Requirements

- macOS, Linux, or Windows
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Git on the server's `PATH`
- An MCP-compatible client

The server does not connect to a Kubernetes cluster. It clones GitHub
repositories, reads Kubernetes YAML files, and creates a branch containing the
requested change.

## Install and verify

From the repository root:

```bash
uv sync --group dev
uv run --group dev python -m pytest -q
```

The `uv sync --group dev` command creates or updates the local virtual environment,
installs runtime dependencies, and installs the development dependencies used
by the tests. The package also exposes a console command named `kubeops-mcp`.

## Configure GitHub access

`inspect_repository` works with public repositories without a token.
`modify_kubernetes_repository` can inspect and commit changes locally without a
token, but it needs `GITHUB_TOKEN` to push a branch and create a pull request.

Create a fine-grained GitHub token for the target repositories and grant it:

- **Contents: Read and write**, to clone, push branches, and create commits
- **Pull requests: Read and write**, to open a pull request

Set the token in the environment of the MCP client. Do not put the token in
this file or commit it to the repository.

For a shell-launched server:

```bash
export GITHUB_TOKEN="github_pat_..."
uv run kubeops-mcp
```

The command intentionally waits for MCP JSON-RPC messages on standard input;
it is not an interactive command prompt. Start it from an MCP client instead
of typing a blank line into a terminal.

## Configure in VS Code

This repository includes `.vscode/mcp.json`. When the repository is opened as
the workspace folder, it starts the server with:

```json
{
	"servers": {
		"kubeops-mcp": {
			"type": "stdio",
			"command": "uv",
			"args": ["--directory", "${workspaceFolder}", "run", "kubeops-mcp"]
		}
	}
}
```

To use it:

1. Open this repository as the VS Code workspace.
2. Ensure `uv` is available in the environment used by VS Code.
3. Set `GITHUB_TOKEN` before launching VS Code if mutation and pull-request
	 operations are required.
4. Open the Command Palette and run **MCP: List Servers**.
5. Start `kubeops-mcp`, then approve the server if VS Code asks for permission.

If the repository is nested inside a larger workspace, replace
`${workspaceFolder}` in `.vscode/mcp.json` with the absolute repository path,
or open this repository directly as the workspace.

## Configure another MCP client

The equivalent generic stdio configuration is:

```json
{
	"command": "uv",
	"args": ["--directory", "/absolute/path/to/kubeops-mcp", "run", "kubeops-mcp"],
	"env": {
		"GITHUB_TOKEN": "${GITHUB_TOKEN}"
	}
}
```

Use the client-specific configuration file and environment-variable syntax
for your MCP host. Prefer an environment variable or secret manager rather
than writing the token directly in a client configuration file.

## Available tools

### `inspect_repository`

Clones a public GitHub repository and returns Kubernetes resources found in
`.yaml` and `.yml` files. It reports each resource's file, kind, and name.

This is an inventory tool, not a full YAML reader. It deliberately returns
resource summaries, so it does not expose fields such as `spec.replicas`.

### `suggest_hpa_for_deployment`

Reads the repository YAML, finds a named Deployment, and returns its configured
`spec.replicas` value plus a complete `hpa.yaml` suggestion. It does not modify
the repository, create a branch, push, or open a pull request.

The current recommendation follows this rule:

```text
minReplicas = 0
maxReplicas = Deployment.spec.replicas
```

For example, if the `be` Deployment contains `spec.replicas: 5`, the tool
reports `5` replicas and returns an HPA with `minReplicas: 0` and
`maxReplicas: 5`.

Example input:

```json
{
	"repository_url": "https://github.com/kishalayb18/kubernetes-yaml-mcp",
	"deployment_name": "be"
}
```

The response includes the source YAML file, namespace, replica count, the
recommended range, and an `hpa_yaml` string ready to save as `hpa.yaml`.

Example input:

```json
{
	"repository_url": "https://github.com/example/platform-manifests"
}
```

### `list_kubernetes_scenarios`

Lists supported or planned Kubernetes workflows. Pass `status` as `supported`
or `planned` to filter the catalog. The currently implemented scenarios are
adding or updating an HPA and creating or updating a Service. Use
`suggest_hpa_for_deployment` first when the requested HPA should be based on the
Deployment's current replica count.

### `modify_kubernetes_repository`

Finds a named Deployment and can:

- create or update an `autoscaling/v2` HPA with `hpa_min` and `hpa_max`;
- create or update a same-named internal `ClusterIP` Service;
- create a branch, commit the YAML change, push it, and open a pull request.

Example request:

```json
{
	"repository_url": https://github.com/kishalayb18/kubernetes-yaml-mcp.git",
	"deployment_name": "be",
	"hpa_min": 1,
	"hpa_max": 7,
	"ensure_service": true,
	"service_port": 8080,
	"namespace": "be",
	"create_pull_request": true
}
```

The tool never writes directly to `main` or `master`. Without
`GITHUB_TOKEN`, it reports the changes after committing them in its temporary
clone, but it cannot push or open a pull request. The clone is removed after
the tool finishes.

## Supported repository and YAML behavior

- Repository URLs must be GitHub URLs in the form
	`https://github.com/OWNER/REPOSITORY`.
- YAML files are discovered recursively, excluding `.git` paths.
- Invalid YAML files are skipped during inspection and modification.
- A Deployment must already exist with the requested name.
- HPA changes require both minimum and maximum replica values.
- Service ports must be between 1 and 65535.
- Pull requests are opened against `main`.

## Troubleshooting

### `uv: command not found`

Install uv and restart VS Code so its updated `PATH` is visible. Confirm with:

```bash
uv --version
```

### `No module named ...` or missing `pytest`

Run:

```bash
uv sync --group dev
```

Then invoke the server and tests through `uv run`.

### The MCP server reports invalid JSON

The server speaks JSON-RPC over stdin/stdout. Do not run it as an interactive
shell command and type ordinary text or blank lines. Start it from the MCP
client, which manages the protocol messages.

### GitHub push or pull-request failure

Check that `GITHUB_TOKEN` is present in the MCP server process environment,
the token has access to the target repository, and the repository permits the
token to create branches and pull requests. The repository's default branch
must also be `main` for pull-request creation.

## Development

Run the test suite with:

```bash
uv run --group dev python -m pytest -q
```

Run the installed server directly with:

```bash
uv run kubeops-mcp
```

That last command is a protocol server and will wait for an MCP client.
