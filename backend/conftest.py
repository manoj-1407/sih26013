"""Pytest configuration for GeoSamanvay tests."""
import os
import tempfile
import pytest

# Set test data dir before any app imports
_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("GS_DATA_DIR", _tmpdir)
os.environ.setdefault("GS_DEMO_MODE", "1")
