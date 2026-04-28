"""Shared pytest fixtures for bluelock tests."""
import sys

import pytest


@pytest.fixture
def tmp_config_path(tmp_path):
    """Return a temp path for a config file."""
    return tmp_path / "config.toml"


@pytest.fixture(scope="session")
def qapp():
    """Provide a QApplication for tests that instantiate Qt objects.

    Widget tests need a real QApplication (not just QCoreApplication). The offscreen
    Qt platform plugin is forced so widgets can be constructed without a display.
    Session-scoped because Qt does not support creating multiple QApplications.
    """
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
