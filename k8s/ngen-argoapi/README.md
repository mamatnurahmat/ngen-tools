# ArgoAPI Kubernetes Deployment

Konfigurasi Kustomize untuk deploy ArgoAPI server ke Kubernetes.

## Struktur

```
base/
├── kustomization.yaml
├── deployment.yaml
├── service.yaml
└── secret.yaml
```

## Konfigurasi Secret

Edit `base/secret.yaml` dan ganti nilai berikut:

| Variable | Description |
|----------|-------------|
| `ARGOCD_SERVER` | URL ArgoCD server (default: argocd-server.argocd.svc.cluster.local) |
| `ARGOCD_TOKEN` | Token autentikasi ArgoCD |
| `TEAMS_WEBHOOK` | (Optional) URL webhook Microsoft Teams untuk notifikasi |
| `HOST` | Host binding (default: 0.0.0.0) |
| `PORT` | Port server (default: 8899) |

## Deploy

### Build YAML

```bash
kustomize build base/
```

### Apply ke Cluster

```bash
# Create namespace terlebih dahulu
kubectl create namespace argoapi

# Apply konfigurasi
kubectl apply -k base/
```

### Atau langsung apply

```bash
kustomize build base/ | kubectl apply -f -
```

## Verifikasi

```bash
# Cek deployment
kubectl get deployments -n argoapi

# Cek pods
kubectl get pods -n argoapi

# Cek service
kubectl get svc -n argoapi

# Cek logs
kubectl logs -n argoapi -l app=argoapi
```

## Port Forward (untuk testing lokal)

```bash
kubectl port-forward -n argoapi svc/argoapi 8899:8899
```

Akses di: `http://localhost:8899`

## Dependency

- Python 3.11
- ngen-argoapi==1.0.8
