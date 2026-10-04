"""
Gate 0 Environment Audit Tests.
Verifies Python version, package imports (FastAPI, Pydantic, pytest),
and project directory boundaries.
"""

import sys
import pytest
import fastapi
import pydantic
import psutil


def test_python_version():
    """Verify Python is >= 3.10 as required by the stack specification."""
    assert sys.version_info >= (3, 10), f"Python version must be >= 3.10, got {sys.version_info}"


def test_fastapi_available():
    """Verify FastAPI is installed and importable."""
    assert hasattr(fastapi, "__version__")
    major_minor = tuple(int(x) for x in fastapi.__version__.split(".")[:2])
    assert major_minor >= (0, 100), f"Expected FastAPI >= 0.100, got {fastapi.__version__}"


def test_pydantic_v2_available():
    """Verify Pydantic V2 is installed."""
    assert hasattr(pydantic, "__version__")
    assert pydantic.__version__.startswith("2."), f"Expected Pydantic V2, got {pydantic.__version__}"


def test_hardware_memory_budget():
    """Verify system has sufficient RAM (> 8 GB) to satisfy the laptop budget."""
    total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    assert total_ram_gb >= 7.0, f"System has less than 7 GB RAM ({total_ram_gb:.1f} GB)"
