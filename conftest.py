"""Offline tests must not export scripted model runs into real Langfuse projects.

Live tracing acceptance is explicit in evals.phase1_acceptance. Individual
callback tests can still override this fixture with their own fake client.
"""
import pytest

@pytest.fixture(autouse=True)
def disable_live_telemetry_for_tests(monkeypatch):
    monkeypatch.setenv('ERP_LANGFUSE_ENABLED','false')
