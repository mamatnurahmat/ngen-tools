# ngenctl

[![GitHub](https://img.shields.io/badge/GitHub-mamatnurahmat%2Fngenctl-blue)](https://github.com/mamatnurahmat/ngenctl)
[![PyPI](https://img.shields.io/pypi/v/ngenctl)](https://pypi.org/project/ngenctl/)

Universal command wrapper package that dispatches to `/usr/local/bin/ngenctl-*` scripts.

## Installation

Install from PyPI:

```bash
pip install ngenctl
```

Or install from source:

```bash
pip install .
```

**Note:** Installation to `/usr/local/bin` requires sudo/root permissions. The package will automatically install bundled scripts to `/usr/local/bin/ngenctl-*` during installation.

## Usage

The `ngenctl` command dispatches to scripts located at `/usr/local/bin/ngenctl-{command}`.

### Format

- Script location: `/usr/local/bin/ngenctl-{command}`
- Command usage: `ngenctl {command}`

### Examples

If you have a script at `/usr/local/bin/ngenctl-rancher`, you can use it as:

```bash
ngenctl rancher --help
ngenctl rancher version
```

If you have a script at `/usr/local/bin/ngenctl-git`, you can use it as:

```bash
ngenctl git clone https://github.com/user/repo.git
ngenctl git status
```

## How It Works

1. When you run `ngenctl {command}`, the CLI dispatcher looks for a script at `/usr/local/bin/ngenctl-{command}`
2. If found, it executes the script with any additional arguments passed
3. The script can be any executable file (bash, sh, Python, or binary)

## Adding New Commands

To add a new command:

1. Place a script at `/usr/local/bin/ngenctl-{your-command}`
2. Make sure it's executable: `chmod +x /usr/local/bin/ngenctl-{your-command}`
3. Use it with: `ngenctl {your-command}`

## Development

### Building the Package

```bash
python -m build
```

### Publishing to PyPI

Menggunakan script otomatis:

```bash
./publish.sh --test      # Publish ke Test PyPI
./publish.sh --publish   # Publish ke PyPI production
```

Atau manual:

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

Untuk panduan lengkap, lihat [PUBLISH.md](PUBLISH.md).

## Repository

- **GitHub**: https://github.com/mamatnurahmat/ngenctl
- **PyPI**: https://pypi.org/project/ngenctl/

## License

MIT

