# Build Pipeline Guide

This directory contains the Azure DevOps build pipeline configuration for the ServiceNowAutomation FastMCP server (Sync pattern, FastMCP framework).

## Pipelines

- `Bupa.ServiceNowAutomation-mcp.yaml`
  - Main CI/CD pipeline, triggered by commits to `develop`. It requires the SonarQube quality gate to pass before building and pushing the application image to `ACR2:TEST`. Deployment stages consume that validated image; Checkmarx is currently disabled.
- `Bupa.ServiceNowAutomation-pr-policy.yaml`
  - PR validation pipeline for an Azure Repos build-validation policy on `develop`. It runs the SonarQube quality gate first, then verifies the Docker build without pushing an image. Attach the `ServiceNowAutomation MCP PR` pipeline to `develop` as a branch policy because Azure Repos does not use YAML `pr` triggers.

## Pipeline Templates (`templates/`)

- `buildMcpImage.yaml`
  - Installs `uv`, copies `.env.local` to `.env`, installs locked dependencies once, runs Ruff and pytest from that environment, then builds and pushes the `Dockerfile-Mcp` image.
- `deployMcpImage.yaml`
  - Installs Helm/kubectl, connects to the target AKS cluster (`az aks get-credentials`), and runs `helm upgrade --install` using the environment's `gvalues-<env>.yaml`.
- `registerMcpApim.yaml`
  - Registers/updates an APIM backend and an APIM API of type `mcp` (streamable transport) so the server is reachable through Bupa's API gateway.
- `security_scans.yaml`
  - SonarQube scan job with PR-specific and branch-specific analysis parameters. It authenticates to `ACR:TEST` to pull the private Sonar base image. Checkmarx can be enabled with the `runCheckmarx` template parameter.

## Common Variables

- `imageTag`: `$(Build.BuildId)`
- `helmVersion`: `3.1.2`
- `expName`: `ServiceNowAutomation`
- `projectName`: `servicenowautomation-mcp`
- `repository`: `$(expName)/$(projectName)`

## Prerequisites

- `Dockerfile-Mcp` exists in the repository root.
- `.env.local` exists in `src/servicenowautomation_mcp/`.
- `.dockerignore.sonar` exists in the repository root and retains `.git` for SonarQube analysis.
- Matching Helm chart exists at `devops/deploy/helm/servicenowautomation-mcp/`.

## Support

For pipeline issues, contact the DevOps/platform team.
