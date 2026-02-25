# UV Setup Guide

This project is configured to work with [uv](https://github.com/astral-sh/uv), a fast Python package installer and resolver.

## Quick Start

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or on Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install the package

```bash
# Install in development/editable mode
uv pip install -e .

# Or install globally
uv pip install .
```

### 3. Run the CLI

After installation, use the `canastra` command:

```bash
canastra "AS,AS,AD,2C,KD,KD,KC" 50 11 11 "KD" 50
```

## Development Workflow

### Using uv sync (recommended for development)

```bash
# This creates a virtual environment and installs the package
uv sync

# Activate the virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate      # Windows

# Run the script
python main.py "AS,AS,AD" 50 11 11
```

### Using uv run (no activation needed)

```bash
# Run directly without activating venv
uv run python main.py "AS,AS,AD" 50 11 11
```

## Project Structure

The project uses a flat structure where all Python files are in the root directory:
- `main.py` - CLI entry point
- `player.py`, `card.py`, etc. - Package modules
- `__init__.py` - Package initialization
- `pyproject.toml` - Project configuration

## Dependencies

This project has **no external dependencies** - it uses only Python standard library.

## Building

To build a distribution:

```bash
uv build
```

This creates a wheel and source distribution in the `dist/` directory.
