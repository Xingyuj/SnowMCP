# Helm Deployment Guide

This directory contains the Helm chart for deploying the servicenowautomation-mcp FastMCP server to Kubernetes.

## Chart Structure

- `servicenowautomation-mcp/` - Helm chart for the FastMCP server
  - `Chart.yaml` - Chart metadata
  - `values.yaml` - Default values
  - `gvalues-dev.yaml` - Dev environment overrides
  - `gvalues-test.yaml` - Test environment overrides
  - `.helmignore` - Packaging excludes
  - `templates/` - Kubernetes manifests
    - `deployment.yaml` - Deployment specification (Azure Workload Identity, AppDynamics init container)
    - `service.yaml` - ClusterIP Service
    - `configmap.yaml` - ConfigMap for environment configuration
    - `serviceaccount.yaml` - Optional Workload-Identity-federated Service Account
    - `pdb.yaml` - Pod Disruption Budget
    - `virtualservice.yaml` - Istio VirtualService
    - `authpolicy.yaml` - Istio AuthorizationPolicy
    - `_helpers.tpl` - Helm template helpers
    - `NOTES.txt` - Post-install usage notes
    - `tests/test-connection.yaml` - `helm test` connectivity check

## Deploying the Chart

### Prerequisites
- Kubernetes cluster access
- Helm 3.1.2 or later
- Azure CLI configured with appropriate subscription

### Deploy to Dev

```bash
helm upgrade --install servicenowautomation-mcp-dev ./servicenowautomation-mcp \
  -n servicenowautomation-dev-ns \
  --create-namespace \
  -f ./servicenowautomation-mcp/values.yaml \
  -f ./servicenowautomation-mcp/gvalues-dev.yaml \
  --set image.tag=<BUILD_ID>
```

### Deploy to Test

```bash
helm upgrade --install servicenowautomation-mcp-test ./servicenowautomation-mcp \
  -n servicenowautomation-test-ns \
  --create-namespace \
  -f ./servicenowautomation-mcp/values.yaml \
  -f ./servicenowautomation-mcp/gvalues-test.yaml \
  --set image.tag=<BUILD_ID>
```

The CI pipeline (`devops/build/templates/deployMcpImage.yaml`) performs this same `helm upgrade` automatically per environment.

## Configuration

### gvalues Files
- `gvalues-dev.yaml` contains environment-specific overrides for DEV
- `gvalues-test.yaml` contains environment-specific overrides for TEST
- Create additional files as needed for UAT and PROD environments

### Common Values to Override
- `image.tag` - Docker image tag (typically the build ID)
- `replicaCount` - Number of pod replicas
- `resources.limits` - CPU and memory limits
- `resources.requests` - CPU and memory requests
- `serviceAccount.name` - Name of the Kubernetes service account

## Health Checks

`probes.liveness` / `probes.readiness` in `values.yaml` are disabled by default (`enabled: false`). If enabled, set their `path` to the FastMCP server's actual health endpoints — `/mcp/health`, `/mcp/ready`, `/mcp/live` (see `src/servicenowautomation_mcp/README.md`) — not the `/api/health` default, which is for the FastAPI variant of this template.

## Troubleshooting

### Check Deployment Status
```bash
kubectl get deployments -n servicenowautomation-dev-ns
kubectl describe deployment servicenowautomation-mcp-dev -n servicenowautomation-dev-ns
```

### View Logs
```bash
kubectl logs -n servicenowautomation-dev-ns <pod-name>
```

### Check Service
```bash
kubectl get svc -n servicenowautomation-dev-ns
```

### Access Application
```bash
kubectl port-forward -n servicenowautomation-dev-ns svc/servicenowautomation-mcp-dev-svc 8080:8080
curl http://localhost:8080/mcp/health
```
