"""FastAPI server for ArgoCD API proxy with Swagger UI."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime
import os
import uvicorn

from .argocd import ArgocdClient

# Get version from environment variable or fallback to package version
def get_version():
    """Get application version from environment variable or package."""
    env_version = os.environ.get("ARGOAPI_VERSION")
    if env_version:
        return env_version
    try:
        from . import __version__
        return __version__
    except ImportError:
        return "unknown"

APP_VERSION = get_version()

app = FastAPI(
    title="ArgoAPI - ArgoCD API Proxy",
    description="REST API proxy for ArgoCD with simplified endpoints",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

def get_client() -> ArgocdClient:
    """Get ArgoCD client instance."""
    try:
        return ArgocdClient()
    except SystemExit:
        raise HTTPException(
            status_code=500,
            detail="ArgoCD credentials not configured. Run 'argoapi login' first."
        )

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {"status": "ok", "service": "argoapi", "version": APP_VERSION}

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for Kubernetes liveness/readiness probes.
    
    Returns:
    - status: "healthy" or "unhealthy"
    - version: Application version
    - timestamp: Current server time
    - argocd_connected: Whether ArgoCD connection is available
    - token: Token status information (valid, username, error)
    """
    health_status = {
        "status": "healthy",
        "version": APP_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "argoapi"
    }
    
    # Try to verify ArgoCD connection and token status
    try:
        client = get_client()
        health_status["argocd_connected"] = True
        
        # Check token status
        token_status = client.check_token_status()
        health_status["token"] = {
            "valid": token_status.get("valid", False),
            "username": token_status.get("username"),
            "error": token_status.get("error")
        }
        
        # If token is not valid, mark status as degraded (but still healthy for k8s probe)
        if not token_status.get("valid"):
            health_status["status"] = "degraded"
            
    except Exception as e:
        health_status["argocd_connected"] = False
        health_status["argocd_error"] = str(e)
        health_status["token"] = {
            "valid": False,
            "username": None,
            "error": "Cannot check token - ArgoCD not configured"
        }
    
    return health_status

@app.get("/app/list", tags=["Applications"])
async def list_applications():
    """
    List all ArgoCD applications with their sync and health status.
    """
    try:
        client = get_client()
        apps = client.list_applications()
        
        result = []
        for app_data in apps:
            name = app_data.get('metadata', {}).get('name', 'N/A')
            status = app_data.get('status', {})
            spec = app_data.get('spec', {})
            sync_status = status.get('sync', {}).get('status', 'Unknown')
            health_status = status.get('health', {}).get('status', 'Unknown')
            
            # Check auto sync
            sync_policy = spec.get('syncPolicy', {})
            auto_sync = sync_policy.get('automated') is not None
            
            result.append({
                "name": name,
                "syncStatus": sync_status,
                "healthStatus": health_status,
                "autoSync": auto_sync
            })
        
        return {"applications": result, "count": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/app/refresh-all", tags=["Applications"])
async def refresh_all_applications(hard: bool = False):
    """
    Refresh all applications (invalidate cache for all).
    
    - **hard**: If true, performs a hard refresh for all apps
    """
    try:
        client = get_client()
        apps = client.list_applications()
        
        results = []
        errors = []
        
        for app_data in apps:
            app_name = app_data.get('metadata', {}).get('name')
            if not app_name:
                continue
                
            try:
                result = client.refresh_application(app_name, hard=hard)
                status = result.get('status', {})
                results.append({
                    "name": app_name,
                    "refreshed": True,
                    "syncStatus": status.get('sync', {}).get('status', 'Unknown'),
                    "healthStatus": status.get('health', {}).get('status', 'Unknown')
                })
            except Exception as e:
                errors.append({
                    "name": app_name,
                    "error": str(e)
                })
        
        return {
            "refreshed": len(results),
            "errors": len(errors),
            "hard": hard,
            "results": results,
            "errorDetails": errors if errors else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/app/refresh/{app_name}", tags=["Applications"])
async def refresh_application(app_name: str, hard: bool = False):
    """
    Refresh an application (invalidate cache).
    
    - **app_name**: Name of the application
    - **hard**: If true, performs a hard refresh
    """
    try:
        client = get_client()
        result = client.refresh_application(app_name, hard=hard)
        
        status = result.get('status', {})
        return {
            "name": app_name,
            "refreshed": True,
            "hard": hard,
            "syncStatus": status.get('sync', {}).get('status', 'Unknown'),
            "healthStatus": status.get('health', {}).get('status', 'Unknown')
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/app/diff/{app_name}", tags=["Applications"])
async def get_application_diff(app_name: str):
    """
    Get diff information for an out-of-sync application.
    
    Returns list of resources that are out of sync.
    """
    try:
        client = get_client()
        app_data = client.get_application(app_name)
        
        sync_status = app_data.get('status', {}).get('sync', {}).get('status', 'Unknown')
        
        if sync_status == 'Synced':
            return {
                "name": app_name,
                "synced": True,
                "syncStatus": sync_status,
                "outOfSyncResources": [],
                "message": "Application is fully synced. No diffs."
            }
        
        # Get out of sync resources
        resources = app_data.get('status', {}).get('resources', [])
        out_of_sync = [r for r in resources if r.get('status') == 'OutOfSync']
        
        diff_results = []
        for res in out_of_sync:
            group = res.get('group', '')
            kind = res.get('kind', '')
            name = res.get('name', '')
            namespace = res.get('namespace', '')
            version = res.get('version', '')
            
            # Get diff for this resource
            diff_data = client.get_resource_diff(app_name, group, kind, name, namespace, version)
            
            diff_results.append({
                "kind": kind,
                "name": name,
                "namespace": namespace,
                "status": res.get('status', 'Unknown'),
                "diff": diff_data.get('diff', None)
            })
        
        return {
            "name": app_name,
            "synced": False,
            "syncStatus": sync_status,
            "outOfSyncResources": diff_results,
            "count": len(diff_results)
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/app/auto/{app_name}", tags=["Applications"])
async def set_auto_sync(app_name: str, enabled: bool = True, prune: bool = False, self_heal: bool = False):
    """
    Enable or disable auto-sync for an application.
    
    - **app_name**: Name of the application
    - **enabled**: True to enable, False to disable
    - **prune**: Enable pruning (only when enabled=True)
    - **self_heal**: Enable self-healing (only when enabled=True)
    """
    try:
        client = get_client()
        result = client.set_auto_sync(app_name, enabled, prune=prune, self_heal=self_heal)
        
        return {
            "name": app_name,
            "autoSync": enabled,
            "prune": prune if enabled else None,
            "selfHeal": self_heal if enabled else None,
            "success": True
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# NOTE: This route MUST be last because {app_name} catches everything
@app.get("/app/{app_name}", tags=["Applications"])
async def get_application(app_name: str):
    """
    Get detailed information about a specific application.
    """
    try:
        client = get_client()
        app_data = client.get_application(app_name)
        return app_data
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "0.0.0.0", port: int = 8899):
    """Run the FastAPI server."""
    print(f"Starting ArgoAPI server on http://{host}:{port}")
    print(f"Swagger UI available at http://{host}:{port}/docs")
    print(f"ReDoc available at http://{host}:{port}/redoc")
    uvicorn.run(app, host=host, port=port)
