"""Conftest for unit tests.

Unit tests use the same pytest-homeassistant-custom-component fixtures
as integration tests. No custom event_loop or pytest_configure needed
since asyncio_mode=auto handles everything.
"""
