# Long-running actions

Four UI actions run on a per-session FIFO queue instead of the Streamlit script
thread:

| Action | Where |
|---|---|
| Load Series | Sidebar → Image |
| Load Measurements | Sidebar → Measurements |
| 🎲 Generate dummy measurement | Sidebar → Measurements |
| Run Forward Projection | Sinogram Inspection tab → Sample options |

Each click freezes the inputs (file list, selection, geometry, energy, volume)
and appends one item. A click never interrupts the item that is running and
never discards its result: the worker thread completes it, and the result is
applied to session state at the top of the next full app run. Actions run one
at a time in click order. There is no dependency graph between items — a
forward projection needs a volume at click time.

## Where to see the queue

Sidebar → **Show queue** (plain checkbox, off by default, at the bottom below
the collapsible sections). The panel
shows every item with its status, elapsed time, progress when known, and any
error message. Hiding the panel does **not** stop the queue: an invisible
one-second poller forces an app rerun whenever an item changes state, so
results are applied even with the panel closed. Each click also shows an
`Added to queue` toast as acknowledgement.

**✕ Cancel** appears only on *pending* items. A running item is inside a
backend call (often a compiled C kernel) and cannot be stopped, so it has no
cancel control. `Clear finished` removes completed rows. Clear Cache drops
the whole queue for that session.

If a worker does not report back within 10 minutes, its item is shown as
failed with a timeout error; the thread itself is not killed.

## What does not queue

Startup data loading, demo-phantom loading, geometry file upload/edit, axis
order changes and cache restore stay synchronous. They are either fast or
have their own status UI.

## Testing note

`AppTest` cannot advance a `run_every` fragment. The integration suite sets
`actions_inline` in session state so submissions execute on the calling
thread, preserving the existing click-then-assert tests. Polling, hidden-panel
result application, click responsiveness, live progress and cancel were
verified in a real browser (see T-109 in `docs/plan.md`). Verification with
real DICOM/projection files and on a CUDA device is still open: this machine
has no CUDA device, though `use_cuda=True` falls back to the CPU with identical
numbers and the worker run with the CUDA option completes normally.
