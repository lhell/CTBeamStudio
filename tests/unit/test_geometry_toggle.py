"""Tests for the in-plot projection-geometry on/off control.

The control is a pair of click buttons (Plotly ``updatemenus``) pinned to the
bottom-right corner of the 3D canvas, not a drag slider: it is shorter and
flips with a single click. Neither form reruns the Streamlit script.
"""

import plotly.graph_objects as go
import pytest

from visualization.volume3d import add_geometry_toggle


def _figure_with_geometry():
    """Volume trace plus three geometry overlay traces."""
    fig = go.Figure()
    fig.add_trace(go.Mesh3d(x=[0, 1, 1], y=[0, 0, 1], z=[0, 0, 0], i=[0], j=[1], k=[2]))
    fig.add_trace(go.Scatter3d(x=[1], y=[1], z=[1], mode="markers"))
    fig.add_trace(go.Scatter3d(x=[2], y=[2], z=[2], mode="lines"))
    fig.add_trace(go.Scatter3d(x=[3], y=[3], z=[3], mode="markers"))
    return fig


def test_geometry_toggle_adds_a_single_button_menu():
    fig = add_geometry_toggle(_figure_with_geometry(), n_base_traces=1)

    assert len(fig.layout.updatemenus) == 1
    assert fig.layout.updatemenus[0].type == "buttons"


def test_geometry_toggle_does_not_add_a_drag_slider():
    """The control must be clickable, not a slider to drag."""
    fig = add_geometry_toggle(_figure_with_geometry(), n_base_traces=1)

    assert len(fig.layout.sliders) == 0


def test_geometry_toggle_is_labelled_projection_geometry():
    fig = add_geometry_toggle(_figure_with_geometry(), n_base_traces=1)

    texts = [annotation.text for annotation in fig.layout.annotations]
    assert "Projection Geometry" in texts


def test_geometry_toggle_is_pinned_to_the_bottom_right_corner():
    fig = add_geometry_toggle(_figure_with_geometry(), n_base_traces=1)
    menu = fig.layout.updatemenus[0]

    assert menu.x == pytest.approx(0.99)
    assert menu.y == pytest.approx(0.02)
    assert menu.xanchor == "right"
    assert menu.yanchor == "bottom"


def test_geometry_toggle_has_on_and_off_buttons_and_starts_on():
    fig = add_geometry_toggle(_figure_with_geometry(), n_base_traces=1)
    menu = fig.layout.updatemenus[0]

    assert menu.active == 0
    assert [button.label for button in menu.buttons] == ["On", "Off"]


def test_geometry_toggle_off_hides_only_the_geometry_traces():
    fig = add_geometry_toggle(_figure_with_geometry(), n_base_traces=1)
    menu = fig.layout.updatemenus[0]
    on_visible = menu.buttons[0].args[0]["visible"]
    off_visible = menu.buttons[1].args[0]["visible"]

    assert on_visible == [True, True, True, True]
    assert off_visible == [True, False, False, False]


def test_geometry_toggle_keeps_a_single_volume_trace_for_any_base_count():
    """All traces before ``n_base_traces`` stay visible in both states."""
    fig = go.Figure()
    for index in range(2):
        fig.add_trace(go.Mesh3d(x=[index], y=[0], z=[0], i=[0], j=[0], k=[0]))
    fig.add_trace(go.Scatter3d(x=[9], y=[9], z=[9], mode="markers"))

    fig = add_geometry_toggle(fig, n_base_traces=2)
    buttons = fig.layout.updatemenus[0].buttons

    assert buttons[0].args[0]["visible"] == [True, True, True]
    assert buttons[1].args[0]["visible"] == [True, True, False]


def test_geometry_toggle_preserves_existing_annotations():
    """The figure already carries the voxel-spacing annotation; adding the
    label must not wipe it."""
    fig = _figure_with_geometry()
    fig.update_layout(annotations=[dict(text="Voxel spacing", x=0.02, y=0.02)])

    fig = add_geometry_toggle(fig, n_base_traces=1)

    texts = [annotation.text for annotation in fig.layout.annotations]
    assert "Voxel spacing" in texts
    assert "Projection Geometry" in texts


def test_geometry_toggle_is_a_noop_without_geometry_traces():
    fig = go.Figure()
    fig.add_trace(go.Mesh3d(x=[0], y=[0], z=[0], i=[0], j=[0], k=[0]))

    fig = add_geometry_toggle(fig, n_base_traces=1)

    assert len(fig.layout.updatemenus) == 0


def test_geometry_toggle_returns_the_same_figure():
    fig = _figure_with_geometry()

    assert add_geometry_toggle(fig, n_base_traces=1) is fig
