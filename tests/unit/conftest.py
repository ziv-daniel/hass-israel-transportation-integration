"""Conftest for unit tests."""

import asyncio
import socket as socket_module
import sys

import pytest

# Store original socket class before any test framework can modify it
_original_socket = socket_module.socket


# Disable the homeassistant custom component plugin for unit tests
# to avoid conflicts with pure unit tests that don't need HA fixtures
def pytest_configure(config):
    """Configure pytest for unit tests."""
    # Enable socket for event loop creation
    socket_module.socket = _original_socket
    # Set timezone env to avoid timezone issues
    import os

    os.environ.setdefault("TZ", "UTC")


@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests.

    Temporarily restore the original socket for event loop creation.
    """
    # Restore original socket class for event loop creation
    socket_module.socket = _original_socket
    # Use selector event loop on Windows for compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
