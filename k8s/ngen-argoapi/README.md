# ArgoAPI Kubernetes Deployment

Konfigurasi Kustomize untuk deploy ArgoAPI server ke Kubernetes.

## Struktur

```
k8s/ngen-argoapi/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── secret.yaml
└── overlays/
    ├── develop-qoin/
    ├── staging-qoin/
    ├── production-qoin/
    └── production-ue/
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ARGOAPI_VERSION` | Versi package ngen-argoapi yang akan diinstall |
| `ARGOCD_URL` | URL ArgoCD server |
| `ARGOCD_USER` | Username ArgoCD (default: admin) |
| `ARGOCD_PASSWORD` | Password ArgoCD |

## Health Check

ArgoAPI menyediakan health check endpoint untuk Kubernetes probes:

### Endpoint

- **`GET /health`** - Health check endpoint yang mengembalikan:
  - `status`: "healthy"
  - `version`: Versi aplikasi (dari `ARGOAPI_VERSION`)
  - `timestamp`: Waktu server saat ini
  - `argocd_connected`: Status koneksi ke ArgoCD

### Kubernetes Probes

Deployment sudah dikonfigurasi dengan:

| Probe | Path | Initial Delay | Period | Failure Threshold |
|-------|------|---------------|--------|-------------------|
| **Startup** | `/health` | 10s | 10s | 30 |
| **Liveness** | `/health` | 60s | 30s | 3 |
| **Readiness** | `/health` | 30s | 10s | 3 |

## Deploy dengan Overlays

### Build YAML

```bash
# Base configuration
kustomize build base/

# Overlay specfik environment
kustomize build overlays/develop-qoin/
kustomize build overlays/staging-qoin/
kustomize build overlays/production-qoin/
kustomize build overlays/production-ue/
```

### Apply ke Cluster

```bash
# Apply overlay spesifik
kubectl apply -k overlays/develop-qoin/
kubectl apply -k overlays/staging-qoin/
kubectl apply -k overlays/production-qoin/
kubectl apply -k overlays/production-ue/
```

### Atau langsung apply dengan pipe

```bash
kustomize build overlays/develop-qoin/ | kubectl apply -f -
```

## Update Versi Package

Untuk update versi ngen-argoapi, edit `ARGOAPI_VERSION` di patch file overlay:

```yaml
# overlays/<environment>/patch-deployment.yaml
env:
  - name: ARGOAPI_VERSION
    value: "0.1.9"  # Update ke versi baru
```

## Verifikasi Deployment

```bash
# Cek deployment
kubectl get deployments -n default -l app=argocd-develop-qoin

# Cek pods
kubectl get pods -n default -l app=argocd-develop-qoin

# Cek health endpoint
kubectl exec -it <pod-name> -- curl localhost:8899/health

# Cek logs
kubectl logs -l app=argocd-develop-qoin
```

## Port Forward (untuk testing lokal)

```bash
kubectl port-forward svc/argocd-develop-qoin-argoapi 8899:8899
```

Akses di: 
- UI: `http://localhost:8899/docs`
- Health: `http://localhost:8899/health`

## Dependency

- Python 3.11
- ngen-argoapi (versi dikontrol via `ARGOAPI_VERSION` env var)

