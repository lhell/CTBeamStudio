# T-63 Implementation — Cone-Beam Forward Projection via ListmodePETProjector

**Datum:** 2026-11-04
**Status:** In Arbeit (nach Freigaben)
**Ziel:** Den TODO in `src/visualization/forward_project.py` (`_forward_project_parallelproj`) durch eine echte parallelproj-Implementierung ersetzen.

## Erkenntnisse (Recherche, verifiziert in parallelproj v2.0.2)

- **`parallelproj.ConeBeamProjector` existiert NICHT** in keiner Version (v1.3–v2.0 geprüft). Der Plan referenziert eine nicht-existierende API.
- parallelproj liefert **`ListmodePETProjector(start, end, img_shape, voxel_size, img_origin)`**, einen `LinearOperator` mit
  - `in_shape = (n0, n1, n2)` (Voxel, parallelproj-Achsenordnung)
  - `out_shape = (num_events,)` (flach)
  - `_apply` / `_adjoint` rufen `parallelproj_core.joseph3d_fwd/back` auf.
- Cone-Beam wird erreicht, indem **jeder LOR als Source→Detektor-Pixel-Paar** definiert wird (Start = Source-Position, Ende = Detektor-Pixel-Position), berechnet pro Projektionswinkel.
- **Referenzlogik** aus `imtct/.../parallelproj_helper.py` (nur Logik, OHNE numba-CUDA und ohne imtct-Importe).

## Getroffene Architektur-Entscheidungen (User-Freigaben)

- Struktur: **Unterordner** `src/backend/parallelproj/` (nach User-Freigabe aus `visualization/` nach `backend/` verschoben; Rechenbackend vs. UI).
- Interne Aufteilung: `geometry.py` + `projector.py` + `layers.py` + `shape.py`.
- Reshape-Helfer: `shape.py` mit `to_parallelproj_batch()` / `from_parallelproj_batch()`.
- Achsen: parallelproj `(nx, ny, nz)` 1:1 zum imtct (`pixel_size_mm`, `slice_thickness_mm`, `pixel_size_mm`).
- Positionsberechnung: **Torch, device-parametrisierbar** (`dev="cpu"|"cuda"`), Variablennamen im imtct-Stil (`pos_beam_start/end`, `pos_source`, `pos_detector`, `R_angle`, `angle_radians`, `idx_cols`, `idx_start/idx_end`, `did`).
- Winkel: **spec-konform umgebaut** — Rotation um die **Z-Achse** (CCW von +Z), `0° = +X anterior`, `first_angle` wird respektiert. (NICHT die imtct-Y-Achsen-Konvention.)
- **Projektions-Orientierung (empirisch verifiziert, 0°-Vier-Regionen-Test):**
  - `col`-Achse = transaxial in-plane (**y**), horizontal im Bild; `col 0 = links (−y)`, steigend nach rechts (+y).
  - `row`-Achse = axial (**z**), vertikal im Bild; row 0 = oben (niedriges z).
  - Ergebnis: `(rows, cols)` zeigt Regionen von oben-links (kleinster Wert) nach unten-rechts (größter Wert).

## Datei-Struktur

```
src/backend/parallelproj/
├── __init__.py          # Public Exporte (keine schweren Importe zur Laufzeit erzwingen)
├── geometry.py          # ConeBeamGeometry dataclass + calculate_xray_beam_list (numpy/torch, keine numba)
├── projector.py         # ConeBeamProjector(LinearOperator) — delegiert an ListmodePETProjector, wrapped Reshape
├── layers.py            # LinearSingleChannelOperator, AdjointLinearSingleChannelOperator, ReshapeLayer (aus Docs)
└── shape.py             # Shape-Konvention: to_parallelproj_batch / from_parallelproj_batch + Docstring-Konstante
```

## Shape-Konvention (Kern — wird in shape.py + Spec dokumentiert)

- **Welt A (Projekt-Volume):** `(z, y, x)`, spacing `(dz, dy, dx)`, origin `(ox, oy, oz)`.
- **Welt B (parallelproj):** Voxel `(nx, ny, nz)`, spacing `(dx, dy, dz)`, origin `(ox, oy, oz)` samt Slice-Dicke in `dz`.
- **Batch-Eingang (Layer):** `(B, 1, nx, ny, nz)`.
- **Projektion (Operator out_shape):** `(n_projs * n_rows * n_cols,)` flach (ListmodePETProjector), internal LOR-Reihenfolge `(proj, col, row)`; `ConeBeamProjector` liefert `(n_projs, n_rows, n_cols)`.
- **Ergebnis aus forward_project:** batchfrei `(n_projs, n_rows, n_cols)`.

## Ablauf

1. `shape.py` anlegen — Achsen-/Batch-Helfer + Konventions-Konstante.
2. `geometry.py` anlegen — `ConeBeamGeometry` + `calculate_xray_beam_list` (Torch, CPU/CUDA, Z-Achsen-Rotation spec-konform). ✅ DONE (verifiziert)
3. `layers.py` anlegen — Docs-Layer (LinearSingleChannelOperator, Adjoint, ReshapeLayer). ✅ DONE
4. `projector.py` anlegen — `ConeBeamProjector` (umwickelt ListmodePETProjector). ✅ DONE (joseph3d verifiziert)
5. `__init__.py` anlegen. ✅ DONE
6. `forward_project.py` erweitern — TODO ersetzen, `PARALLELPROJ_AVAILABLE`-Pfad nutzen, Helfer einbinden. ⏳ TODO
7. Tests anlegen (Helfer-Roundtrip, Achsen-Inversion, ConeBeamProjector in_shape/out_shape, forward_project nicht-Null mit parallelproj). ⏳ Teilweise: `tests/unit/test_parallelproj.py` (4 Tests, grün)
8. Dokumentation: Modul-Docstring (kurz) + Spec Section 4.1 (ausführlich).
9. Verifikation: Tests im conda-Env `ct-viewer` (parallelproj 2.0.2) ausführen.
