"""Shared pytest fixtures for bluelock tests."""
import sys

import pytest


@pytest.fixture
def tmp_config_path(tmp_path):
    """Return a temp path for a config file."""
    return tmp_path / "config.toml"


@pytest.fixture(scope="session")
def qapp():
    """Provide a QCoreApplication for tests that instantiate QObject subclasses.

    Session-scoped because Qt does not support creating multiple QCoreApplications.
    """
    from PyQt6.QtCore import QCoreApplication
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app
