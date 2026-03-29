"""Shared pytest fixtures for bluelock tests."""
import pytest


@pytest.fixture
def tmp_config_path(tmp_path):
    """Return a temp path for a config file."""
    return tmp_path / "config.toml"
