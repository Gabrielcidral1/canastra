#!/usr/bin/env python3
"""Main entry point for Canastra game."""

import subprocess
import sys


def main():
    """Start the Streamlit application."""
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])


if __name__ == "__main__":
    main()
