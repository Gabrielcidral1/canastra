# UV Setup Guide

This project is configured to work with [uv](https://github.com/astral-sh/uv).

## Quick Start

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install the package

**Option A – Use uv’s project venv (`.venv`)**

```bash
uv sync
source .venv/bin/activate   # Linux/Mac
# Then in your IDE, select the interpreter: .venv/bin/python
```

**Option B – Use an existing venv (e.g. one named `canastra`)**

Activate that venv, then install the project and all dependencies (including Streamlit) into it:

```bash
# With (canastra) or your venv already activated:
uv pip install -e .
```

This installs `streamlit` and everything from `pyproject.toml` into the active environment.

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

This project depends on **streamlit** (see `pyproject.toml`). Use **Option B** above if you rely on an existing venv so that `uv pip install -e .` installs Streamlit into it; otherwise use **Option A** and the project’s `.venv`.

## Building

To build a distribution:

```bash
uv build
```

This creates a wheel and source distribution in the `dist/` directory.
