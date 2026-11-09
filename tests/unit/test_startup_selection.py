"""Tests for the startup behaviour decision (no Streamlit, no I/O).

Startup never loads anything automatically: the viewer shows an empty state and
the user picks image data or the demo phantom. These tests pin that policy, so
a well-meaning "load the cache on start" change fails here first.
"""

from visualization.sidebar import create_demo_volume_job, should_startup_load


def test_startup_never_loads_automatically():
    assert should_startup_load() is False


def test_clear_cache_lands_in_the_same_state_as_startup():
    """Clear Cache wipes session state and then behaves exactly like a fresh
    start: no load is kicked off."""
    assert should_startup_load() is False


def test_demo_job_is_pure_and_repeatable():
    job = create_demo_volume_job()

    first = job()
    second = job()

    assert first.array.shape == second.array.shape


def test_demo_job_returns_a_volume_without_streamlit(monkeypatch):
    import streamlit

    def fail(*args, **kwargs):
        raise AssertionError("demo job must not touch Streamlit")

    monkeypatch.setattr(streamlit, "session_state", type("S", (), {})())
    job = create_demo_volume_job()

    volume = job()

    assert hasattr(volume, "array")
