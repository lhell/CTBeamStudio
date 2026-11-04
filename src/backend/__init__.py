"""Computational backend for the CT orientation viewer.

Holds the non-UI, numerical / data-processing code (geometry, forward
projection, parallelproj integration, volume handling, ...). The Streamlit /
Plotly UI lives in :mod:`visualization` and imports from here.
"""

from . import parallelproj

__all__ = ["parallelproj"]
