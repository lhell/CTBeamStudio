"""Tests for the pure startup-load decision (no Streamlit, no I/O)."""

from visualization.sidebar import create_demo_volume_job, startup_loader


def test_data_path_set_defers_to_sidebar():
    assert startup_loader(True, True, cache_lookup=lambda: ["x.dcm"]) is None


def test_without_cache_returns_the_demo_job():
    loader = startup_loader(False, True, cache_lookup=lambda: None)

    volume = loader()
    assert volume is not None
    assert hasattr(volume, "array")


def test_cache_disabled_returns_the_demo_job():
    loader = startup_loader(False, False, cache_lookup=lambda: ["x.dcm"])

    volume = loader()
    assert hasattr(volume, "array")


def test_cache_lookup_is_not_consulted_when_disabled():
    calls = []

    def lookup():
        calls.append(1)
        return ["x.dcm"]

    startup_loader(False, False, cache_lookup=lookup)
    assert calls == []


def test_cache_hit_returns_a_callable_that_loads_those_files(monkeypatch):
    import visualization.sidebar as sidebar

    seen = {}

    def fake_load(files):
        seen["files"] = files
        return "loaded-volume"

    monkeypatch.setattr(sidebar, "load_volume_cached", fake_load)

    loader = startup_loader(False, True, cache_lookup=lambda: ["a.dcm", "b.dcm"])

    assert loader() == "loaded-volume"
    assert seen["files"] == ["a.dcm", "b.dcm"]


def test_demo_job_is_pure_and_repeatable():
    job = create_demo_volume_job()

    first = job()
    second = job()

    assert first.array.shape == second.array.shape
