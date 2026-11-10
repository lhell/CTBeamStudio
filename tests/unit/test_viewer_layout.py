"""Tests for the viewer view-switcher geometry (pure, no Streamlit)."""

from visualization.app import viewer_column_spec, viewer_has_3d, viewer_has_mpr


def test_all_view_uses_the_one_to_two_split():
    assert viewer_column_spec("All") == [1, 2]


def test_2d_view_collapses_only_the_3d_column():
    left, right = viewer_column_spec("2D")
    assert left == 1
    assert right < 0.01  # renders at 0 px
    assert viewer_has_mpr("2D") is True
    assert viewer_has_3d("2D") is False


def test_3d_view_collapses_only_the_mpr_column():
    left, right = viewer_column_spec("3D")
    assert left < 0.01
    assert right == 1
    assert viewer_has_mpr("3D") is False
    assert viewer_has_3d("3D") is True


def test_unknown_view_falls_back_to_the_split():
    assert viewer_column_spec("nonsense") == [1, 2]


def test_collapsed_ratio_is_positive_because_zero_is_rejected():
    """st.columns raises StreamlitInvalidColumnSpecError on a literal 0."""
    for view in ("2D", "3D"):
        assert all(width > 0 for width in viewer_column_spec(view))
