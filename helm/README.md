# Agent Zero Helm Chart

Helm chart for deploying Agent Zero on Kubernetes.

## Prerequisites

- Kubernetes 1.23+
- Helm 3.0+
- PV provisioner support in the underlying infrastructure

## Installation

### Local Development (minikube, kind, Docker Desktop)

```bash
helm install agent-zero ./helm/agent-zero \
  -f ./helm/agent-zero/env/values-local.yaml \
  --set secrets.create=true \
  --set secrets.data.OPENAI_API_KEY="your-key"
```

### Google Kubernetes Engine (GKE)

```bash
# Create secrets first
kubectl create secret generic agent-zero-api-keys \
  --from-literal=OPENAI_API_KEY=your-key \
  --from-literal=ANTHROPIC_API_KEY=your-key

# Install chart
helm install agent-zero ./helm/agent-zero \
  -f ./helm/agent-zero/env/values-gke.yaml \
  --set ingress.hosts[0].host=your-domain.com
```

### Azure Kubernetes Service (AKS)

```bash
# Create secrets first
kubectl create secret generic agent-zero-api-keys \
  --from-literal=OPENAI_API_KEY=your-key \
  --from-literal=ANTHROPIC_API_KEY=your-key

# Install chart
helm install agent-zero ./helm/agent-zero \
  -f ./helm/agent-zero/env/values-azure.yaml \
  --set ingress.hosts[0].host=your-domain.com
```

### On-Premises / Self-Hosted

```bash
# Create secrets first
kubectl create secret generic agent-zero-api-keys \
  --from-literal=OPENAI_API_KEY=your-key \
  --from-literal=ANTHROPIC_API_KEY=your-key

# Install chart
helm install agent-zero ./helm/agent-zero \
  -f ./helm/agent-zero/env/values-onprem.yaml \
  --set ingress.hosts[0].host=agent-zero.internal.example.com
```

## Configuration

See `values.yaml` for all available configuration options.

### Common Customizations

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Image repository | `agent0ai/agent-zero` |
| `image.tag` | Image tag | `latest` |
| `service.type` | Kubernetes service type | `ClusterIP` |
| `ingress.enabled` | Enable ingress | `false` |
| `resources.limits.cpu` | CPU limit | `2` |
| `resources.limits.memory` | Memory limit | `4Gi` |
| `persistence.enabled` | Enable persistent storage | `true` |
| `autoscaling.enabled` | Enable HPA | `false` |

## Upgrading

```bash
helm upgrade agent-zero ./helm/agent-zero -f your-values.yaml
```

## Uninstalling

```bash
helm uninstall agent-zero
```

**Note:** PVCs are not deleted automatically. To remove them:

```bash
kubectl delete pvc -l app.kubernetes.io/name=agent-zero
```

## Environment-Specific Files

| File | Use Case |
|------|----------|
| `env/values-local.yaml` | Local development (minikube, kind) |
| `env/values-gke.yaml` | Google Kubernetes Engine |
| `env/values-azure.yaml` | Azure Kubernetes Service |
| `env/values-onprem.yaml` | Self-hosted / On-premises |

## Secrets Management

For production, use one of these approaches:

1. **External Secrets Operator** - Sync from cloud secret managers
2. **Sealed Secrets** - Encrypt secrets in git
3. **Vault** - HashiCorp Vault integration
4. **Cloud-native** - GCP Secret Manager, Azure Key Vault

Example with External Secrets Operator:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: agent-zero-api-keys
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: gcp-secret-store
    kind: ClusterSecretStore
  target:
    name: agent-zero-api-keys
  data:
    - secretKey: OPENAI_API_KEY
      remoteRef:
        key: openai-api-key
```
