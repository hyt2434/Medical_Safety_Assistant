"""Backend tests use the canonical repository src/ package tree."""
import pytest


@pytest.fixture(autouse=True)
def explicit_test_identity_configuration(monkeypatch):
    monkeypatch.setenv('AUTH_SEED_DEMO', '1')
    monkeypatch.setenv('AUTH_ENV', 'test')
