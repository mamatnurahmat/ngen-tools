# 🏗️ Build Plan Template: Python CLI Package

> **Template ini adalah panduan untuk membangun Python package dengan CLI dan REST API.**
> Ganti `{package-name}` dengan nama package Anda (contoh: `my-tool`, `ngen-gitops`, dll).

---

## 📌 Quick Reference

| Komponen | Wajib? | Deskripsi |
|----------|--------|-----------|
| `__init__.py` | ✅ Wajib | Package metadata |
| `cli.py` | ✅ Wajib | CLI entry point |
| `config.py` | ✅ Wajib | Configuration management |
| `server.py` | ⭕ Opsional | REST API server (jika butuh API) |
| `{service}.py` | 🔧 Custom | Modul bisnis logic (sesuai kebutuhan) |
| `{notify}.py` | 🔧 Custom | Modul notifikasi (sesuai kebutuhan) |

---

## Project Overview

**{package-name}** adalah Python package yang menyediakan:
- CLI interface untuk [deskripsi fungsi utama]
- REST API server untuk integrasi (opsional)
- [Fitur lainnya sesuai kebutuhan]

---

## 📋 Project Structure

```
{package-name}/
├── {package_name}/              # Main package directory (underscore)
│   ├── __init__.py              # ✅ WAJIB: Package metadata
│   ├── cli.py                   # ✅ WAJIB: CLI entry point
│   ├── config.py                # ✅ WAJIB: Configuration management
│   ├── server.py                # ⭕ OPSIONAL: REST API server
│   │
│   │   # 🔧 CUSTOM MODULES (sesuai kebutuhan project)
│   │   # Contoh untuk GitOps:
│   ├── bitbucket.py             # Custom: Bitbucket API (contoh)
│   ├── git_wrapper.py           # Custom: Git commands (contoh)
│   └── teams_notify.py          # Custom: Teams notification (contoh)
│
├── pyproject.toml               # ✅ WAJIB: Package configuration
├── README.md                    # ✅ WAJIB: Documentation
├── MANIFEST.in                  # Include non-Python files
├── setup.py                     # Legacy setup (opsional)
└── .gitignore                   # Git ignore rules
```

---

## 🔧 Step-by-Step Implementation

### Step 1: Initialize Project Structure

```bash
mkdir -p {package-name}/{package_name}
cd {package-name}
```

Create initial files:
1. `pyproject.toml` - Package configuration
2. `{package_name}/__init__.py` - Package metadata
3. `.gitignore` - Git ignore rules

---

### Step 2: Create Configuration Module (`config.py`) ✅ WAJIB

**Purpose:** Manage application configuration dari `.env` file dan environment variables.

**Features:**
- Config directory: `~/.{package-name}/`
- Config file: `~/.{package-name}/.env`
- Auto-create sample `.env` on first run
- Priority: Environment variables > .env file

**Functions to implement:**

```python
# Constants
CONFIG_DIR = Path.home() / ".{package-name}"
ENV_FILE = CONFIG_DIR / ".env"

# 1. Directory/file management
ensure_config_dir()              # Create config dir if not exists
create_default_env()             # Create sample .env with comments
config_exists() -> bool          # Check if .env exists
get_config_file_path() -> str    # Return path to .env

# 2. Load configuration
load_config() -> Dict[str, Any]  # Load all config as dictionary

# 3. Get specific config sections (sesuaikan dengan kebutuhan)
get_credentials() -> Dict[str, str]     # API credentials
get_server_config() -> Dict[str, Any]   # host, port
get_current_user() -> str               # Current user name
```

**Configuration structure (.env format):**

```bash
# {package-name} Configuration
# Uncomment and fill in the values

# API Credentials (sesuaikan dengan kebutuhan)
# API_USER=your-username
# API_TOKEN=your-token

# Server Settings
# SERVER_HOST=0.0.0.0
# SERVER_PORT=8080
```

**Dependencies:** `python-dotenv`

---

### Step 3: Create Custom Business Logic Modules 🔧 CUSTOM

> ⚠️ **CATATAN:** Modul-modul di bawah ini adalah **CONTOH** dari project `ngen-gitops`.
> Ganti dengan modul sesuai kebutuhan project Anda.

#### Contoh A: API Integration Module (e.g., `bitbucket.py`)

Jika project Anda butuh integrasi dengan API eksternal:

```python
"""API integration module."""

class ApiError(Exception):
    """Base exception for API operations."""
    pass

# Implementasi sesuai kebutuhan
def call_api(endpoint, method="GET", data=None) -> Dict:
    """Generic API call."""
    pass

def specific_operation_1(...) -> Dict:
    """Operasi spesifik 1."""
    pass

def specific_operation_2(...) -> Dict:
    """Operasi spesifik 2."""
    pass
```

#### Contoh B: Command Wrapper Module (e.g., `git_wrapper.py`)

Jika project Anda butuh wrapper untuk command-line tools:

```python
"""Command wrapper module."""

class CommandError(Exception):
    """Base exception for command operations."""
    pass

def run_command(args, cwd=None) -> CompletedProcess:
    """Run shell command safely."""
    pass

def tool_operation_1(...):
    """Wrap specific tool operation."""
    pass
```

#### Contoh C: Notification Module (e.g., `teams_notify.py`)

Jika project Anda butuh notifikasi:

```python
"""Notification module."""

def send_notification(title, message, **kwargs) -> bool:
    """Send notification to external service."""
    pass

def notify_success(operation, details) -> None:
    """Send success notification."""
    pass

def notify_error(operation, error) -> None:
    """Send error notification."""
    pass
```

---

### Step 4: Create Web Server Module (`server.py`) ⭕ OPSIONAL

> Buat modul ini **hanya jika** project membutuhkan REST API.

**Purpose:** FastAPI REST API server.

**Framework:** FastAPI + Uvicorn

**Basic Structure:**

```python
#!/usr/bin/env python3
"""FastAPI web server for {package-name}."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from . import __version__

# Request Models
class ExampleRequest(BaseModel):
    field1: str
    field2: str
    optional_field: str = "default"

# Create FastAPI app
app = FastAPI(
    title="{package-name} API",
    description="API server for {package-name}",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints
@app.get("/")
async def root():
    return {"name": "{package-name}", "version": __version__}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/v1/{package-name}/operation")
async def api_operation(request: ExampleRequest):
    # Implement operation
    pass

def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Start the server."""
    uvicorn.run(app, host=host, port=port)
```

**Endpoints Pattern:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Welcome/info |
| GET | `/health` | Health check |
| POST | `/v1/{package-name}/{operation}` | API operations |

---

### Step 5: Create CLI Module (`cli.py`) ✅ WAJIB

**Purpose:** Command-line interface using argparse.

**Entry Points (pyproject.toml):**
- `{package-name}` → `{package_name}.cli:main`
- `{alias}` → `{package_name}.cli:main` (opsional alias pendek)

**Basic Structure:**

```python
#!/usr/bin/env python3
"""CLI entry point for {package-name}."""
import argparse
import sys

from . import __version__
from .config import load_config, get_config_file_path

def cmd_config(args):
    """Show configuration."""
    config = load_config()
    print(f"📋 {package-name} Configuration")
    print(f"   Config file: {get_config_file_path()}")
    # Print config details

def cmd_operation1(args):
    """Handle operation 1."""
    pass

def cmd_operation2(args):
    """Handle operation 2."""
    pass

def cmd_server(args):
    """Start REST API server."""
    from .server import start_server
    start_server(host=args.host, port=args.port)

def main():
    parser = argparse.ArgumentParser(
        prog="{package-name}",
        description="{Package description}"
    )
    parser.add_argument("--version", action="version", version=__version__)
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Config command
    subparsers.add_parser("config", help="Show configuration")
    
    # Operation commands (sesuaikan dengan kebutuhan)
    op1_parser = subparsers.add_parser("operation1", help="Do operation 1")
    op1_parser.add_argument("arg1", help="Argument 1")
    op1_parser.add_argument("--flag", action="store_true", help="Optional flag")
    
    # Server command (jika ada server.py)
    server_parser = subparsers.add_parser("server", help="Start API server")
    server_parser.add_argument("--host", default="0.0.0.0", help="Host")
    server_parser.add_argument("--port", type=int, default=8080, help="Port")
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    # Route to handlers
    handlers = {
        "config": cmd_config,
        "operation1": cmd_operation1,
        "server": cmd_server,
    }
    
    handler = handlers.get(args.command)
    if handler:
        handler(args)

if __name__ == "__main__":
    main()
```

**Common Flags Pattern:**
- `--json` - Output as JSON
- `--dry-run` - Preview without executing
- `--verbose, -v` - Verbose output
- `--quiet, -q` - Quiet mode

---

### Step 6: Package Configuration (`pyproject.toml`) ✅ WAJIB

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{package-name}"
version = "0.1.0"
description = "{Package description}"
readme = "README.md"
requires-python = ">=3.7"
license = {text = "MIT"}
authors = [{name = "Your Name"}]
keywords = ["cli", "your", "keywords"]

# Sesuaikan dependencies
dependencies = [
    "python-dotenv>=0.19.0",     # Wajib untuk config
    # Tambahkan sesuai kebutuhan:
    # "requests>=2.25.0",        # Untuk HTTP client
    # "fastapi>=0.68.0",         # Untuk REST API
    # "uvicorn>=0.15.0",         # Untuk ASGI server
    # "pyyaml>=5.4.0",           # Untuk YAML parsing
]

classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]

[project.scripts]
{package-name} = "{package_name}.cli:main"
# {alias} = "{package_name}.cli:main"  # Opsional: alias pendek

[project.urls]
Homepage = "https://github.com/your-username/{package-name}"
Repository = "https://github.com/your-username/{package-name}"

[tool.setuptools.packages.find]
where = ["."]
include = ["{package_name}*"]
```

---

### Step 7: Create Package Init (`__init__.py`) ✅ WAJIB

```python
"""{package-name} - {Package description}."""

__version__ = "0.1.0"
__author__ = "Your Name"
```

---

### Step 8: Build & Test

**Development install:**
```bash
pip install -e .
```

**Test commands:**
```bash
{package-name} --version
{package-name} --help
{package-name} config
```

**Build package:**
```bash
pip install build
python -m build
```

**Publish to PyPI:**
```bash
pip install twine
twine upload dist/*
```

---

## 📊 Dependencies by Feature

| Feature | Dependencies |
|---------|--------------|
| Core (config) | `python-dotenv` |
| HTTP Client | `requests` |
| REST API Server | `fastapi`, `uvicorn` |
| YAML Processing | `pyyaml` |
| CLI Enhancements | `rich`, `click` (alternatif argparse) |

---

## 🔄 Architecture Pattern

```
CLI/API Request
      ↓
   config.py (load configuration)
      ↓
   ┌─────────────────┐
   │ Command Router  │
   └─────────────────┘
          ↓
   ┌─────────────────────────────────────┐
   │     Custom Business Logic Modules   │
   │  (sesuaikan dengan kebutuhan Anda)  │
   └─────────────────────────────────────┘
          ↓
   Optional: Notification Module
          ↓
   Return Response (JSON/Text)
```

---

## ✅ Implementation Checklist

### Wajib (Core)
- [ ] Create project structure
- [ ] Implement `__init__.py`
- [ ] Implement `config.py`
- [ ] Implement `cli.py`
- [ ] Configure `pyproject.toml`
- [ ] Write `README.md`

### Opsional (sesuai kebutuhan)
- [ ] Implement `server.py` (jika butuh REST API)
- [ ] Implement custom business modules
- [ ] Implement notification module
- [ ] Add unit tests
- [ ] Build & publish to PyPI

---

## 🎯 Key Design Principles

1. **Modular Design** - Setiap modul punya tanggung jawab tunggal
2. **Config Priority** - Environment variables > .env file
3. **Error Handling** - Custom exceptions untuk debugging lebih baik
4. **Dual Interface** - CLI + REST API (opsional) dengan logic yang sama
5. **Extensible** - Mudah menambah modul baru
6. **JSON Output** - Machine-readable output untuk automation

---

## 📝 Contoh Project yang Menggunakan Template Ini

| Project | Custom Modules | Deskripsi |
|---------|----------------|-----------|
| `ngen-gitops` | `bitbucket.py`, `git_wrapper.py`, `teams_notify.py` | GitOps automation |
| `ngen-j` | `jenkins.py` | Jenkins API CLI |
| `doq` | `docker.py`, `compose.py` | Docker management |

---

## 🚀 Quick Start untuk Project Baru

1. Copy template ini
2. Replace `{package-name}` dengan nama package (dengan dash: `my-tool`)
3. Replace `{package_name}` dengan nama Python module (dengan underscore: `my_tool`)
4. Hapus contoh custom modules yang tidak diperlukan
5. Tambahkan custom modules sesuai kebutuhan project
6. Update dependencies di `pyproject.toml`
