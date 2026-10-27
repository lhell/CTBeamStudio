# Public Release Cleanup Plan

## Completed
- ✅ Add FDA/CE disclaimer to README

## Pending

### 1. Remove Debug Print Statements
Remove 14 print statements from 3 files:

| File | Count | Lines |
|------|-------|-------|
| `src/visualization/loaders/npy.py` | 6 | 89, 92, 158, 159, 160 |
| `src/visualization/loaders/dicom.py` | 3 | 352, 356, 357 |
| `src/visualization/phantom.py` | 5 | 178, 179, 183, 184, 185, 186 |

### 2. Clean Up Log Files
- Remove `app.log` from git tracking and delete file
- Delete `src/app.log`

### 3. Add *.log to .gitignore
Add log file pattern to prevent future commits of debug logs.

## Notes
- No hardcoded paths found (✅ clean)
- No PHI/patient data in repo (✅ clean)
