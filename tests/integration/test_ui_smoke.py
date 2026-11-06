"""Fast UI smoke test for the sidebar section layout.

One module-scoped ``AppTest`` instance is shared by all assertions: a single
``AppTest.run()`` costs 10-30 s (full Streamlit script run), so running it per
test made the suite unusable (see plan.md T-81).

The cache path is skipped explicitly: ``auto_load_cache=False`` stops
``load_initial_volume()`` from touching the 87 KB cache file with its hundreds
of dead network paths, which alone cost ~3.6 s per run.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "src" / "visualization" / "app.py"

SIDEBAR_SECTIONS = ["Image", "Projection Geometry", "Measurements"]


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(APP_PATH), default_timeout=90)
    at.session_state["auto_load_cache"] = False
    at.run()
    return at


def test_app_renders_without_exception(app):
    assert list(app.exception) == []


def test_sidebar_sections_are_collapsible_in_order(app):
    assert [expander.label for expander in app.sidebar.expander] == SIDEBAR_SECTIONS


def test_image_and_measurements_start_expanded_geometry_collapsed(app):
    """The two frequently used sections are open; the geometry section, which
    is only needed when a geometry file exists, starts collapsed."""
    expanded = {
        expander.label: expander.proto.expanded for expander in app.sidebar.expander
    }
    assert expanded == {
        "Image": True,
        "Projection Geometry": False,
        "Measurements": True,
    }


def test_sidebar_no_longer_has_a_data_header(app):
    headers = [h.value for h in app.sidebar.header]
    assert "Data" not in headers


def _label(element) -> str:
    return getattr(element, "label", None) or getattr(element, "value", "")


def _index_of_sidebar_child(app, predicate) -> int:
    for index, child in app.sidebar.children.items():
        if predicate(child):
            return index
    raise AssertionError("Sidebar element not found")


def test_cache_controls_are_above_the_image_section(app):
    """Cache controls must come before the image section, so they are visible
    without scrolling past the whole load section."""
    cache_index = _index_of_sidebar_child(
        app, lambda e: "Auto-load cache" in str(_label(e))
    )
    clear_index = _index_of_sidebar_child(
        app, lambda e: str(_label(e)).endswith("Clear Cache")
    )
    image_index = _index_of_sidebar_child(
        app, lambda e: getattr(e, "type", "") == "expander" and _label(e) == "Image"
    )

    assert cache_index < image_index
    assert clear_index < image_index
