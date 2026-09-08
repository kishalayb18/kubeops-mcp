# KubeOps MCP

This project uses the official [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk) and `FastMCP`.

The server edits Kubernetes YAML in a temporary clone, creates a branch, commits changes, and optionally pushes the branch and opens a GitHub pull request. Keep repository mutations explicit and idempotent.