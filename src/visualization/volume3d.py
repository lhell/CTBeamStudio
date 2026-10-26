"""3D volume visualization using scipy, plotly, and pyvista."""

import io
import math

import numpy as np
import plotly.graph_objects as go
from scipy import ndimage
from skimage import measure

# PyVista is optional - only import if rendering with PyVista
try:
    import pyvista as pv

    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False


def get_source_position(geometry, source_angle: float = 0.0):
    """Calculate source position from ProjectionGeometry.

    Args:
        geometry: ProjectionGeometry object
        source_angle: Source angle in degrees (0 = anterior = +X, positive = CCW)

    Returns:
        (x, y, z) source position in mm
    """
    angle_rad = math.radians(source_angle)

    # Base position: on circle at SID distance, at anterior (0°) = +X direction
    base_x = geometry.sid * math.cos(angle_rad)
    base_y = geometry.sid * math.sin(angle_rad)
    base_z = 0.0

    # Apply source offsets
    x = base_x + geometry.source_offset_x
    y = base_y + geometry.source_offset_y
    z = base_z + geometry.source_offset_z

    return (x, y, z)


def get_detector_position(geometry, source_angle: float = 0.0):
    """Calculate detector position from ProjectionGeometry.

    Args:
        geometry: ProjectionGeometry object
        source_angle: Source angle in degrees

    Returns:
        (x, y, z) detector position in mm
    """
    angle_rad = math.radians(source_angle)

    # Detector is opposite to source on the central beam
    base_x = -geometry.sid * math.cos(angle_rad)
    base_y = -geometry.sid * math.sin(angle_rad)
    base_z = 0.0

    # Apply detector offsets (independent of source)
    x = base_x + geometry.detector_offset_x
    y = base_y + geometry.detector_offset_y
    # Detector Z follows source Z offset

    return (x, y, base_z)


def get_trajectory_positions(geometry, n_projections: int):
    """Generate source and detector positions for all projections.

    Args:
        geometry: ProjectionGeometry object
        n_projections: Total number of projections in the scan

    Returns:
        (source_positions, detector_positions) as lists of (x,y,z) tuples
    """
    source_positions = []
    detector_positions = []

    # For helical scan, total angle > 360°
    # Calculate total angle based on number of projections
    # Each projection is evenly spaced
    total_angle = 360.0 * (n_projections / 2304)  # 2304 projections per rotation

    for i in range(n_projections):
        source_angle = (i / n_projections) * total_angle

        src = get_source_position(geometry, source_angle)
        det = get_detector_position(geometry, source_angle)

        source_positions.append(src)
        detector_positions.append(det)

    return source_positions, detector_positions


def add_trajectory_to_figure(
    fig: go.Figure,
    source_positions: list,
    detector_positions: list,
    downsample: int = 1,
) -> go.Figure:
    """Add source and detector trajectory to Plotly figure.

    Args:
        fig: Plotly figure
        source_positions: List of (x, y, z) source positions
        detector_positions: List of (x, y, z) detector positions
        downsample: Show every Nth position

    Returns:
        Updated Plotly figure
    """
    # Downsample positions
    src_x = [p[0] for p in source_positions[::downsample]]
    src_y = [p[1] for p in source_positions[::downsample]]
    src_z = [p[2] for p in source_positions[::downsample]]

    det_x = [p[0] for p in detector_positions[::downsample]]
    det_y = [p[1] for p in detector_positions[::downsample]]
    det_z = [p[2] for p in detector_positions[::downsample]]

    # Add source trajectory (red/orange small markers)
    fig.add_trace(
        go.Scatter3d(
            x=src_x,
            y=src_y,
            z=src_z,
            mode="markers",
            marker=dict(size=3, color="orange", opacity=0.8),
            name="Source Trajectory",
            showlegend=True,
        )
    )

    # Add detector trajectory (turquoise small markers)
    fig.add_trace(
        go.Scatter3d(
            x=det_x,
            y=det_y,
            z=det_z,
            mode="markers",
            marker=dict(size=3, color="turquoise", opacity=0.8),
            name="Detector Trajectory",
            showlegend=True,
        )
    )

    return fig


def downsample_volume(volume_array: np.ndarray, factor: int = 4) -> np.ndarray:
    """Downsample volume by integer factor.

    Args:
        volume_array: 3D numpy array (z, y, x)
        factor: Downsampling factor (1, 2, or 4)

    Returns:
        Downsampled volume array
    """
    if factor <= 1:
        return volume_array

    # Ensure dimensions are divisible by factor
    z, y, x = volume_array.shape
    z_crop = (z // factor) * factor
    y_crop = (y // factor) * factor
    x_crop = (x // factor) * factor

    volume_cropped = volume_array[:z_crop, :y_crop, :x_crop]

    # Downsample using mean pooling
    return volume_cropped.reshape(
        z_crop // factor, factor, y_crop // factor, factor, x_crop // factor, factor
    ).mean(axis=(1, 3, 5))


def get_camera_preset(preset: str, bounds: tuple) -> dict:
    """Get camera position and direction for preset views.

    Args:
        preset: Preset name ("iso", "front", "back", "left", "right", "top", "bottom")
        bounds: (xmin, xmax, ymin, ymax, zmin, zmax) of the volume

    Returns:
        dict with "position", "focal_point", and "view_up" keys
    """
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    center = ((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)

    # Calculate diagonal for distance
    diagonal = math.sqrt((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2)
    distance = diagonal * 1.0

    presets = {
        "iso": {
            "position": (distance, -distance, distance),
            "focal_point": center,
            "view_up": (0, 0, 1),
        },
        "front": {
            "position": (center[0], center[1] + distance, center[2]),
            "focal_point": center,
            "view_up": (0, 0, 1),
        },
        "back": {
            "position": (center[0], center[1] - distance, center[2]),
            "focal_point": center,
            "view_up": (0, 0, 1),
        },
        "left": {
            "position": (center[0] - distance, center[1], center[2]),
            "focal_point": center,
            "view_up": (0, 0, 1),
        },
        "right": {
            "position": (center[0] + distance, center[1], center[2]),
            "focal_point": center,
            "view_up": (0, 0, 1),
        },
        "top": {
            "position": (center[0], center[1], center[2] + distance),
            "focal_point": center,
            "view_up": (0, 1, 0),
        },
        "bottom": {
            "position": (center[0], center[1], center[2] - distance),
            "focal_point": center,
            "view_up": (0, 1, 0),
        },
    }

    return presets.get(preset, presets["iso"])


def extract_isosurface(volume: np.ndarray, level: float) -> tuple:
    """Extract isosurface mesh from volume using marching cubes.

    Args:
        volume: 3D numpy array
        level: Isosurface level

    Returns:
        Tuple of (vertices, faces) or (None, None) if no surface found
    """
    try:
        verts, faces, normals, values = measure.marching_cubes(volume, level=level)
        return verts, faces
    except (ValueError, RuntimeError):
        return None, None


def create_volume_figure(
    volume_array: np.ndarray,
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0),
    render_mode: str = "iso",
    opacity: float = 0.5,
    surface_opacity: float = 0.7,
    colormap: str = "bone",
    downsample: int = 4,
    camera_preset: str = "iso",
    n_iso_levels: int = 5,
    iso_threshold: tuple = None,
) -> go.Figure:
    """Create a Plotly figure with 3D volume rendering.

    Args:
        volume_array: 3D numpy array (z, y, x)
        spacing: Voxel spacing (z, y, x)
        render_mode: "iso" for isosurface, "volume" for volume rendering
        opacity: Opacity for volume rendering (0-1)
        surface_opacity: Opacity for iso-surface rendering (0-1)
        colormap: Colormap name
        downsample: Downsampling factor (1, 2, or 4) for performance
        camera_preset: Camera preset ("iso", "front", "back", "left", "right", "top", "bottom")
        n_iso_levels: Number of iso-surface levels to extract
        iso_threshold: Tuple (min, max) HU values for iso-surface threshold

    Returns:
        Plotly figure
    """
    # Downsample for performance
    if downsample > 1:
        volume_array = downsample_volume(volume_array, downsample)
        # Adjust spacing to account for downsampling
        spacing = tuple(s * downsample for s in spacing)

    fig = go.Figure()

    # Calculate physical bounds - center volume at origin
    z, y, x = volume_array.shape
    # Physical extent in mm
    extent_x = x * spacing[2]
    extent_y = y * spacing[1]
    extent_z = z * spacing[0]

    # Center the volume at origin
    origin_x = -extent_x / 2
    origin_y = -extent_y / 2
    origin_z = -extent_z / 2

    bounds = (
        origin_x,
        origin_x + extent_x,
        origin_y,
        origin_y + extent_y,
        origin_z,
        origin_z + extent_z,
    )

    # Get camera preset
    cam = get_camera_preset(camera_preset, bounds)

    # Create spacing info for display
    spacing_info = (
        f"Voxel spacing: ({spacing[0]:.2f}, {spacing[1]:.2f}, {spacing[2]:.2f}) mm"
    )

    if render_mode == "iso":
        # Isosurface rendering - extract contours at multiple levels
        if iso_threshold is not None:
            vmin, vmax = iso_threshold
        else:
            vmin, vmax = np.percentile(volume_array, [5, 95])
            vmin = vmin + 50
            vmax = vmax - 50

        n_levels = n_iso_levels
        levels = np.linspace(vmin, vmax, n_levels)

        # Colors for different levels (grayscale gradient)
        gray_levels = np.linspace(0.2, 0.8, n_levels)
        colors = [
            f"rgb({int(g * 255)}, {int(g * 255)}, {int(g * 255)})" for g in gray_levels
        ]

        for i, level in enumerate(levels):
            verts, faces = extract_isosurface(volume_array, level)
            if verts is not None and len(verts) > 0:
                # Convert vertex indices to physical coordinates and offset to center at origin
                # verts is (z, y, x) - need to convert to (x, y, z)
                px = verts[:, 2] * spacing[2] + origin_x
                py = verts[:, 1] * spacing[1] + origin_y
                pz = verts[:, 0] * spacing[0] + origin_z

                # Get triangle indices
                if len(faces) > 0:
                    ix = faces[:, 0]
                    iy = faces[:, 1]
                    iz = faces[:, 2]

                    fig.add_trace(
                        go.Mesh3d(
                            x=px,
                            y=py,
                            z=pz,
                            i=ix,
                            j=iy,
                            k=iz,
                            color=colors[i % len(colors)],
                            opacity=surface_opacity,
                            name=f"Level {i + 1}",
                            showlegend=True,
                        )
                    )
    else:
        # Volume rendering - use voxel visualization with interpolated appearance
        # Use less aggressive downsampling for smoother look
        ds = max(downsample, 4)
        vol_ds = downsample_volume(volume_array, ds)

        # Get voxel values for coloring
        voxel_vals = vol_ds.flatten()

        # Create coordinates - flatten first to match voxel_vals (centered at origin)
        z, y, x = vol_ds.shape
        # Actual spacing after downsampling (in mm)
        vol_spacing = tuple(s * ds for s in spacing)
        zz, yy, xx = np.meshgrid(
            np.arange(z) * vol_spacing[0] + origin_z,
            np.arange(y) * vol_spacing[1] + origin_y,
            np.arange(x) * vol_spacing[2] + origin_x,
            indexing="ij",
        )

        # Calculate marker size based on voxel spacing (approximate pixels per mm)
        # Scale factor: 8 pixels per mm of spacing
        avg_spacing = np.mean(vol_spacing)
        marker_size = max(4, int(avg_spacing * 8))

        # Flatten coordinates to match voxel_vals
        xx_flat = xx.flatten()
        yy_flat = yy.flatten()
        zz_flat = zz.flatten()

        # Filter to only non-air voxels and normalize HU values for coloring
        mask = voxel_vals > -300  # Only show tissue/bone

        if np.any(mask):
            # Normalize values for better color mapping
            vals = voxel_vals[mask]
            vals_norm = (vals - vals.min()) / (vals.max() - vals.min() + 1e-8)

            fig.add_trace(
                go.Scatter3d(
                    x=xx_flat[mask],
                    y=yy_flat[mask],
                    z=zz_flat[mask],
                    mode="markers",
                    marker=dict(
                        size=marker_size,  # Based on voxel spacing
                        color=vals_norm,
                        colorscale="Greys",  # Use Plotly's built-in colorscale
                        opacity=opacity,  # User-adjustable transparency
                        showscale=True,
                        colorbar=dict(
                            title="HU",
                            x=1.02,
                            len=0.5,
                            y=0.75,
                            tickfont=dict(color="white"),
                            title_font=dict(color="white"),
                        ),
                    ),
                    name="Volume",
                    showlegend=True,
                )
            )

    # Apply camera preset
    camera = dict(
        eye=dict(
            x=cam["position"][0] / (bounds[1] + bounds[3] + bounds[5]) * 3,
            y=cam["position"][1] / (bounds[1] + bounds[3] + bounds[5]) * 3,
            z=cam["position"][2] / (bounds[1] + bounds[3] + bounds[5]) * 3,
        ),
        center=dict(x=0, y=0, z=0),
    )

    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=True, showgrid=True, gridcolor="#333", title="X (mm)"),
            yaxis=dict(visible=True, showgrid=True, gridcolor="#333", title="Y (mm)"),
            zaxis=dict(visible=True, showgrid=True, gridcolor="#333", title="Z (mm)"),
            bgcolor="#111",
            camera=camera,
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#111",
        font=dict(color="white"),
        showlegend=True,
        legend=dict(
            x=0.02, y=0.98, font=dict(color="white", size=10), bgcolor="rgba(0,0,0,0.5)"
        ),
        annotations=[
            dict(
                text=spacing_info,
                x=0.02,
                y=0.02,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color="white", size=12),
                bgcolor="rgba(0,0,0,0.5)",
                borderpad=4,
            )
        ],
    )

    return fig


def add_source_detector_figure(
    fig: go.Figure,
    volume_array: np.ndarray,
    spacing: tuple[float, float, float],
    isocenter: tuple[float, float, float] = None,
    sid: float = 1000.0,
    sdd: float = 1000.0,
    gantry_angle: float = 0.0,
    show_source: bool = True,
    show_detector: bool = True,
    source_pos: tuple[float, float, float] = None,
    detector_pos: tuple[float, float, float] = None,
) -> go.Figure:
    """Add source and detector visualization to Plotly figure.

    Args:
        fig: Plotly figure
        volume_array: 3D numpy array for bounds calculation
        spacing: Voxel spacing
        isocenter: (x, y, z) position of isocenter in mm (default: center of volume)
        sid: Source-to-Isocenter distance in mm
        sdd: Source-to-Detector distance in mm
        gantry_angle: Gantry angle in degrees
        show_source: Show source sphere
        show_detector: Show detector plane
        source_pos: Manual source position
        detector_pos: Manual detector position

    Returns:
        Updated Plotly figure
    """
    # Use provided isocenter, or default to center of volume (now at origin)
    if isocenter is None:
        isocenter = (0.0, 0.0, 0.0)

    # Calculate source/detector positions if not manually provided
    if source_pos is None or detector_pos is None:
        angle_rad = math.radians(gantry_angle)

        if source_pos is None:
            source_pos = (
                isocenter[0] - sid * math.sin(angle_rad),
                isocenter[1] + sid * math.cos(angle_rad),
                isocenter[2],
            )

        if detector_pos is None:
            detector_pos = (
                isocenter[0] + sdd * math.sin(angle_rad),
                isocenter[1] - sdd * math.cos(angle_rad),
                isocenter[2],
            )

    if show_source:
        # Add source as a marker
        fig.add_trace(
            go.Scatter3d(
                x=[source_pos[0]],
                y=[source_pos[1]],
                z=[source_pos[2]],
                mode="markers",
                marker=dict(size=5, color="yellow", symbol="circle"),
                name="X-ray Source",
                showlegend=True,
            )
        )

    if show_detector:
        # Add detector origin as marker
        fig.add_trace(
            go.Scatter3d(
                x=[detector_pos[0]],
                y=[detector_pos[1]],
                z=[detector_pos[2]],
                mode="markers",
                marker=dict(size=5, color="cyan", symbol="square"),
                name="Detector",
                showlegend=True,
            )
        )

        # Add detector as a plane (large square perpendicular to beam)
        det_x = detector_pos[0]
        det_y = detector_pos[1]
        det_z = detector_pos[2]

        # Detector size (100mm x 100mm)
        half_size = 50
        angle_rad = math.radians(gantry_angle)

        # Create a square in the detector plane (perpendicular to beam direction)
        # Beam is along the line from source to detector, so detector face is perpendicular
        # Using cross product to get perpendicular vectors in the detector plane
        beam_dir = np.array(
            [
                detector_pos[0] - source_pos[0],
                detector_pos[1] - source_pos[1],
                detector_pos[2] - source_pos[2],
            ]
        )
        beam_dir = (
            beam_dir / np.linalg.norm(beam_dir)
            if np.linalg.norm(beam_dir) > 0
            else np.array([1, 0, 0])
        )

        # Create perpendicular vectors for the detector plane
        if abs(beam_dir[2]) < 0.9:
            up = np.array([0, 0, 1])
        else:
            up = np.array([1, 0, 0])

        right = np.cross(beam_dir, up)
        right = right / np.linalg.norm(right) * half_size
        up_norm = np.cross(right, beam_dir)
        up_norm = up_norm / np.linalg.norm(up_norm) * half_size

        # Four corners of the detector
        c0 = np.array([det_x, det_y, det_z]) - right - up_norm
        c1 = np.array([det_x, det_y, det_z]) + right - up_norm
        c2 = np.array([det_x, det_y, det_z]) + right + up_norm
        c3 = np.array([det_x, det_y, det_z]) - right + up_norm

        corners_x = [c0[0], c1[0], c2[0], c3[0]]
        corners_y = [c0[1], c1[1], c2[1], c3[1]]
        corners_z = [c0[2], c1[2], c2[2], c3[2]]

        # Add detector as a surface (two triangles forming a quad)
        fig.add_trace(
            go.Mesh3d(
                x=corners_x,
                y=corners_y,
                z=corners_z,
                i=[0, 0],
                j=[1, 2],
                k=[2, 3],
                color="cyan",
                opacity=0.4,
                name="Detector Plane",
                showlegend=True,
            )
        )

    # Add beam path line (from source to detector)
    fig.add_trace(
        go.Scatter3d(
            x=[source_pos[0], detector_pos[0]],
            y=[source_pos[1], detector_pos[1]],
            z=[source_pos[2], detector_pos[2]],
            mode="lines",
            line=dict(color="red", width=4),
            name="Central beam",
            showlegend=True,
        )
    )

    # Add isocenter marker
    fig.add_trace(
        go.Scatter3d(
            x=[isocenter[0]],
            y=[isocenter[1]],
            z=[isocenter[2]],
            mode="markers",
            marker=dict(size=5, color="green", symbol="diamond"),
            name="Isocenter",
            showlegend=True,
        )
    )

    return fig


def get_volume_center(
    volume_array: np.ndarray, spacing: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Calculate the center of a volume in physical coordinates.

    Args:
        volume_array: 3D numpy array (z, y, x)
        spacing: Voxel spacing (z, y, x) in mm

    Returns:
        (x, y, z) center position in mm - now returns (0,0,0) since volume is centered at origin
    """
    # Volume is now centered at origin, so center is (0, 0, 0)
    return (0.0, 0.0, 0.0)


def get_dicom_geometry(series) -> dict:
    """Extract geometry info from DICOM series if available.

    Args:
        series: Series object with DICOM metadata

    Returns:
        dict with keys: sid, sdd, gantry_angle, or None if not available
    """
    geometry = {}

    # Try to get GantryAngle from DICOM metadata
    if hasattr(series, "gantry_angle"):
        try:
            geometry["gantry_angle"] = float(series.gantry_angle)
        except (TypeError, ValueError):
            geometry["gantry_angle"] = 0.0
    else:
        geometry["gantry_angle"] = 0.0

    # Default SID/SDD for CT (canonically 1000mm)
    geometry["sid"] = 1000.0
    geometry["sdd"] = 1000.0

    return geometry


# Backwards compatibility alias
def create_volume_plotter(
    volume_array: np.ndarray,
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0),
    render_mode: str = "iso",
    opacity: float = 0.5,
    colormap: str = "bone",
    show_axes: bool = True,
    background_color: str = "black",
    downsample: int = 4,
    camera_preset: str = "iso",
):
    """Create volume figure (backwards compatibility wrapper).

    Returns:
        Dict with 'figure' key containing the Plotly figure
    """
    return {
        "figure": create_volume_figure(
            volume_array=volume_array,
            spacing=spacing,
            render_mode=render_mode,
            opacity=opacity,
            colormap=colormap,
            downsample=downsample,
            camera_preset=camera_preset,
        )
    }


def create_plotly_figure(plotter_data):
    """Convert volume data to Plotly figure for Streamlit rendering.

    Args:
        plotter_data: Dict with 'figure' key or direct figure

    Returns:
        Plotly figure
    """
    if hasattr(plotter_data, "figure"):
        return plotter_data["figure"]
    return plotter_data


# Backwards compatibility for add_source_detector
def add_source_detector(
    plotter_data,
    isocenter=(0, 0, 0),
    sid=1000.0,
    sdd=1000.0,
    gantry_angle=0.0,
    show_source=True,
    show_detector=True,
    source_pos=None,
    detector_pos=None,
    plotter=None,
):
    """Add source/detector to volume (backwards compatibility wrapper).

    Returns:
        Updated dict with 'figure' key
    """
    if plotter is not None and hasattr(plotter, "figure"):
        volume_array = plotter.get("volume_array", np.zeros((10, 10, 10)))
        spacing = plotter.get("spacing", (1.0, 1.0, 1.0))
    else:
        # Default values if not provided
        volume_array = np.zeros((10, 10, 10))
        spacing = (1.0, 1.0, 1.0)

    fig = create_volume_figure(volume_array, spacing)

    fig = add_source_detector_figure(
        fig,
        volume_array=volume_array,
        spacing=spacing,
        isocenter=isocenter,
        sid=sid,
        sdd=sdd,
        gantry_angle=gantry_angle,
        show_source=show_source,
        show_detector=show_detector,
        source_pos=source_pos,
        detector_pos=detector_pos,
    )

    return {"figure": fig}


def create_pyvista_volume(
    volume_array: np.ndarray,
    spacing: tuple[float, float, float] = (1.0, 1.0, 1.0),
    opacity: float = 0.5,
    colormap: str = "bone",
    downsample: int = 4,
    camera_preset: str = "iso",
):
    """Create PyVista volume rendering and return screenshot.

    Args:
        volume_array: 3D numpy array (z, y, x) in HU
        spacing: Voxel spacing in mm (z, y, x)
        opacity: Volume opacity (0-1)
        colormap: Matplotlib colormap name
        downsample: Downsampling factor for performance
        camera_preset: Camera view preset

    Returns:
        Dict with 'screenshot' (bytes), 'spacing' info
    """
    if not PYVISTA_AVAILABLE:
        raise ImportError("PyVista is not available. Install with: pip install pyvista")

    # Enable off-screen rendering
    pv.OFF_SCREEN = True

    # Downsample for performance
    if downsample > 1:
        vol_ds = downsample_volume(volume_array, downsample)
        ds_spacing = tuple(s * downsample for s in spacing)
    else:
        vol_ds = volume_array
        ds_spacing = spacing

    # Create ImageData with proper spacing
    grid = pv.ImageData()
    grid.dimensions = vol_ds.shape[::-1]  # PyVista uses (x, y, z)
    grid.spacing = ds_spacing
    grid.origin = (0, 0, 0)

    # Add volume data - PyVista expects Fortran order for ImageData
    grid.point_data["values"] = vol_ds.flatten(order="F")

    # Create plotter with explicit window size
    plotter = pv.Plotter(off_screen=True, window_size=(900, 900))
    plotter.set_background("#111111")

    # Add volume with opacity
    plotter.add_volume(
        grid,
        scalars="values",
        opacity=opacity,
        cmap=colormap,
        show_scalar_bar=False,
    )

    # Set camera based on preset (using available methods)
    camera_views = {
        "iso": ("iso", 1),
        "front": ("xz", 1),  # view from front (+Y)
        "back": ("xz", -1),  # view from back (-Y)
        "left": ("yz", -1),  # view from left (-X)
        "right": ("yz", 1),  # view from right (+X)
        "top": ("xy", 1),  # view from top (+Z)
        "bottom": ("xy", -1),  # view from bottom (-Z)
    }

    view, direction = camera_views.get(camera_preset, ("iso", 1))

    # Get bounds for camera positioning
    b = grid.bounds
    center = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2)
    diagonal = ((b[1] - b[0]) ** 2 + (b[3] - b[2]) ** 2 + (b[5] - b[4]) ** 2) ** 0.5
    distance = diagonal * 1.0  # Closer zoom to match Plotly

    camera_positions = {
        "iso": (distance, -distance, distance),
        "xz": (center[0], center[1] + distance * direction, center[2]),
        "yz": (center[0] + distance * direction, center[1], center[2]),
        "xy": (center[0], center[1], center[2] + distance * direction),
    }

    pos = camera_positions.get(view, camera_positions["iso"])
    plotter.camera_position = [
        pos,  # position
        center,  # focal point
        (0, 0, 1),  # view up
    ]

    # Render and capture screenshot BEFORE closing
    try:
        plotter.render()
        # Use return_img=True to get numpy array directly
        screenshot = plotter.screenshot(return_img=True, transparent_background=False)
    finally:
        plotter.close()

    # Convert numpy array to bytes
    img_bytes = io.BytesIO()
    from PIL import Image

    Image.fromarray(screenshot).save(img_bytes, format="PNG")
    img_bytes.seek(0)

    return {
        "screenshot": img_bytes.getvalue(),
        "spacing": ds_spacing,
    }
