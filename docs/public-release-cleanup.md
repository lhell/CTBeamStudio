# Public Release Cleanup Plan

## Completed
- ✅ Add FDA/CE disclaimer to README

### 1. Remove Debug Print Statements
Removed debug prints from the loader code paths:

| File | Removed | Note |
|------|---------|------|
| `src/visualization/loaders/npy.py` | 5 | `load_npy`, `load_npy_series` |
| `src/visualization/loaders/dicom.py` | 3 | `load_dicom_series` |

The `print()` calls in `src/visualization/phantom.py` were **kept**: they live in
the `if __name__ == "__main__":` demo block and are intentional CLI output, not
debug logging in the library path.

### 2. Clean Up Log Files
- ✅ Removed `app.log` and `src/app.log` from git tracking and deleted them

### 3. Add *.log to .gitignore
- ✅ Added `*.log` under a new `# Logs` section

## Notes
- No hardcoded paths found (✅ clean)
- No PHI/patient data in repo (✅ clean)
