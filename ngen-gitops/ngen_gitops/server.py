#!/usr/bin/env python3
"""FastAPI web server for ngen-gitops."""
from __future__ import annotations

import sys
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from . import __version__
from .bitbucket import (
    create_branch,
    set_image_in_yaml,
    create_pull_request,
    merge_pull_request,
    run_k8s_pr_workflow,
    GitOpsError
)


# Request models
class CreateBranchRequest(BaseModel):
    """Request model for create-branch endpoint."""
    repo: str
    src_branch: str
    dest_branch: str


class SetImageYamlRequest(BaseModel):
    """Request model for set-image-yaml endpoint."""
    repo: str
    refs: str
    yaml_path: str
    image: str
    dry_run: bool = False


class PullRequestRequest(BaseModel):
    """Request model for pull-request endpoint."""
    repo: str
    src_branch: str
    dest_branch: str
    delete_after_merge: bool = False


class MergeRequest(BaseModel):
    """Request model for merge endpoint."""
    pr_url: str
    delete_after_merge: bool = False


class K8sPRRequest(BaseModel):
    """Request model for k8s-pr endpoint."""
    cluster: str
    namespace: str
    deploy: str
    image: str
    approve_merge: bool = False
    repo: str = "gitops-k8s"


# Create FastAPI app
app = FastAPI(
    title="ngen-gitops API",
    description="GitOps API server for Bitbucket operations",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "ngen-gitops API",
        "version": __version__,
        "endpoints": {
            "create_branch": "POST /v1/gitops/create-branch",
            "set_image_yaml": "POST /v1/gitops/set-image-yaml",
            "pull_request": "POST /v1/gitops/pull-request",
            "merge": "POST /v1/gitops/merge",
            "k8s_pr": "POST /v1/gitops/k8s-pr"
        },
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.post("/v1/gitops/create-branch")
async def api_create_branch(request: CreateBranchRequest):
    """Create a new branch in Bitbucket repository.
    
    Args:
        request: CreateBranchRequest with repo, src_branch, dest_branch
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = create_branch(
            repo=request.repo,
            src_branch=request.src_branch,
            dest_branch=request.dest_branch
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


@app.post("/v1/gitops/set-image-yaml")
async def api_set_image_yaml(request: SetImageYamlRequest):
    """Update image reference in YAML file.
    
    Args:
        request: SetImageYamlRequest with repo, refs, yaml_path, image, dry_run
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = set_image_in_yaml(
            repo=request.repo,
            refs=request.refs,
            yaml_path=request.yaml_path,
            image=request.image,
            dry_run=request.dry_run
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


@app.post("/v1/gitops/pull-request")
async def api_pull_request(request: PullRequestRequest):
    """Create a pull request in Bitbucket repository.
    
    Args:
        request: PullRequestRequest with repo, src_branch, dest_branch, delete_after_merge
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = create_pull_request(
            repo=request.repo,
            src_branch=request.src_branch,
            dest_branch=request.dest_branch,
            delete_after_merge=request.delete_after_merge
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


@app.post("/v1/gitops/merge")
async def api_merge(request: MergeRequest):
    """Merge a pull request.
    
    Args:
        request: MergeRequest with pr_url, delete_after_merge
    
    Returns:
        JSON response with operation result
    
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = merge_pull_request(
            pr_url=request.pr_url,
            delete_after_merge=request.delete_after_merge
        )
        
        if result['success']:
            return JSONResponse(content=result, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=result)
            
    except GitOpsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'GitOpsError'
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'ValueError'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }
        )


def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the FastAPI server.
    
    Args:
        host: Server host address
        port: Server port number
    """
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    start_server()
