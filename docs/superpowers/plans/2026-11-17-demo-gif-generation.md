# Demo GIF generation plan (high quality, ≤ 32 MB)

Date: 2026-11-17
Status: ready to execute
Owner: build agent (any machine with Edge + Docker + `ct-viewer` env)

## Why: root cause of the current blurry GIF

The current `ctbeam_demo.gif` (13.2 MB, 480×258, 329 frames, ~6 fps) was
generated in the session "Server and dummy interaction video" with this final
encode:

```
fps=6, scale=480:-2:flags=lanczos, palettegen max_colors=96, paletteuse dither=bayer:bayer_scale=5:diff_mode=rectangle
```

The screencast source was already **1280×720** (CDP `Page.startScreencast`,
`maxWidth=1280, maxHeight=720`). So the pipeline downscaled **1280 → 480
(≈3.75×)** and crushed the palette to **96 colors** with bayer dithering. The
README then renders that 480 px-wide GIF at `width="960"` — an upscale of an
upscale. That combination, not the recording itself, is what looks bad.

Conclusion: keep the encode close to the capture resolution (1280×720), use a
full palette, and spend the file size headroom. Budget: **≤ 32 MB**.

## Goal & budget

| Parameter | Current | Target |
|---|---|---|
| Width | 480 px | **960–1280 px** (prefer 1280) |
| Aspect | 16:9 | 16:9 |
| Colors | 96 | **192–256** |
| Dither | bayer/bayer_scale=5 | **sierra2_4a** (or bayer only if size forces it) |
| Playback fps | ~6 | **6–10** (source cadence ~8 fps) |
| Size | 13.2 MB | **≤ 32 MB** |
| README width | 960 | keep 960 (1280 source downsamples cleanly) |

Quality rule: never solve a size problem by dropping below **960 px width** or
**128 colors** — reduce fps first, then colors, then width.

## Prerequisites

- Machine: Windows with Edge, Docker Desktop running (ffmpeg runs in Docker).
- App served at `http://localhost:8501` inside the conda env `ct-viewer`
  (`python -m streamlit run src/visualization/app.py --server.headless true`).
- Free port for CDP: **9223**.
- Working dir for artifacts: `%TEMP%\opencode\ctvideo` (frames must not be
  committed — `*.jpeg` frames are untracked; only the final GIF enters the repo).

## Phase 1 — start the app

```powershell
cmd /c "call C:\Users\<user>\miniforge3\Scripts\activate.bat ct-viewer && python -m streamlit run src/visualization/app.py --server.headless true --server.port 8501"
```

Wait until `Invoke-WebRequest localhost:8501` returns 200 and the page text
contains `Load Demo Phantom`.

## Phase 2 — launch the recording browser

```powershell
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList `
  '--remote-debugging-port=9223',
  "--user-data-dir=$env:TEMP\edge-ctbeam-demo",
  '--no-first-run','--no-default-browser-check','--no-proxy-server',
  '--disable-extensions',
  '--lang=en-US',
  '--disable-features=Translate,TranslateUI',
  '--start-maximized',
  'http://localhost:8501'
```

Rules learned the hard way (keep all of them):

- `--disable-extensions` — Teleparty auto-re-enables in new profiles and opens
  a landing tab that pollutes the recording.
- `--lang=en-US` + `--disable-features=Translate,TranslateUI` — Edge
  auto-translated the app to German on a German OS, which also broke the
  `waitText('Load Demo Phantom')` step ("Demo Phantom laden").
- Exact 16:9 viewport via CDP `Emulation.setDeviceMetricsOverride`
  (`width=1440, height=810, deviceScaleFactor=2`), window maximized at native
  scaling. Do **not** use `--force-device-scale-factor=1` (UI looks tiny).
- A visible cursor in the GIF comes from a JS overlay (synthetic
  `Input.dispatchMouseEvent` does not move the OS pointer). Inject the overlay
  before Phase 3 and drive it from the choreography.

## Phase 3 — choreography

Two JS phases, evaluated via CDP `Runtime.evaluate` (`awaitPromise`), with real
waits on Streamlit text (`waitText` / `waitTextGone` for `RUNNING`):

- Phase A (viewer):
  1. Click **Load Demo Phantom**, wait `Loaded demo phantom`, wait `RUNNING` gone.
  2. Radio **2D**.
  3. Scrub **Axial Slice** slowly, ~31 → 49 (keyboard-arrow fallback on the
     slider thumb if a synthetic drag does not move it).
  4. Close the **Slice Options** expander again (otherwise it overlays the 3D
     plot and shifts legend coordinates).
  5. Radio **3D**; read the **Source Trajectory** legend item coordinates and
     return them (`toggleX`, `toggleY`).
- Trusted toggles (winning detail): after Phase A, dispatch CDP
  `Input.dispatchMouseEvent` clicks at the returned coordinates to toggle the
  red Source Trajectory off → on. Plotly legend entries are SVG `<g.traces>`,
  not Streamlit checkboxes; plain JS `.click()` on them is unreliable.
- Phase B (sinogram): switch **Sinogram Inspection** tab, click **Run Forward
  Projection**, wait through `RUNNING`, then scrub **Projection index**
  slowly (0 → ~28) as the finish.

Keep the tour short (~30 s real time) — same storyboard as the current GIF:
load → 2D → slice scrub → 3D → trajectory toggle → sinogram → forward
projection → index scrub.

## Phase 4 — recorder

### 4a. Page.startScreencast (primary — matches the original session)

`Page.startScreencast` with `format=jpeg, quality=85,
maxWidth=1440, maxHeight=810, everyNthFrame=1`; ack each frame, save when
`timestamp - lastSaved >= MinFrameGap` (0.12 s). Emit the `ffconcat` list with
invariant-culture decimals, 1.6× slowdown, 6 s gap cap. Reference:
`%TEMP%\opencode\ctvideo\cdp_recorder.ps1`.

Caveat: screencast only emits while the window keeps painting. If the window is
occluded/minimized or the screen locks, capture silently stops and the GIF
freezes on whatever was last painted. Keep the Edge window in the foreground
for the whole run.

### 4b. Screenshot polling (fallback when the window cannot stay visible)

Poll `Page.captureScreenshot` every ~200 ms (`clip={x:0,y:0,width:1440,
height:810,scale:1}`, jpeg q82), deduplicate identical frames by hash, and
interleave with the choreography `Runtime.evaluate` promise. Forces fresh
frames regardless of compositor throttling; slightly lower effective fps.
Reference: `%TEMP%\opencode\ctvideo\cdp_recorder_poll.ps1`.

## Phase 5 — encode (the actual fix)

Source: `frames_short/list.txt` (ffconcat at full 1440×810 capture with
per-frame durations). Run ffmpeg from Docker:

```
docker run --rm -v %TEMP%\opencode\ctvideo:/data jrottenberg/ffmpeg:latest -y \
  -f concat -safe 0 -i /data/frames_short/list.txt \
  -vf "fps=8,scale=1280:-2:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];[s1][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle" \
  /data/ctbeam_demo_hq.gif
```

Budget ladder — try in order, stop at the first result **≤ 32 MB**:

| Step | fps | width | colors | dither | Notes |
|---|---|---|---|---|---|
| 1 | 8 | 1280 | 256 | sierra2_4a | preferred |
| 2 | 7 | 1280 | 256 | sierra2_4a | -12% frames |
| 3 | 7 | 1280 | 192 | sierra2_4a | |
| 4 | 6 | 1280 | 192 | bayer 5 | |
| 5 | 6 | 960 | 192 | sierra2_4a | floor: do not go lower |

Do not reintroduce `max_colors=96` or `scale=480`. `diff_mode=rectangle` is
what keeps the size sane on mostly-static UI frames — keep it at every step.

Expected: 1280×720, 256 colors puts the file in the high-20s/low-30s MB range
after delta compression; the ladder exists for a reason.

> **Actual result (2026-11-17):** 1280×720, 515 frames, 64 s, 256 colors,
> sierra2_4a + rectangle delta → **3.79 MB**. Delta compression on the mostly
> static dark UI is far cheaper than the old dither-everything encode. Local
> ffmpeg 9.0.2 (installed into the env) was used instead of Docker; command
> shape unchanged.

## Phase 6 — QA gate (all must pass)

1. `Image.open('ctbeam_demo.gif')` → width ≥ 960, aspect 16:9, frame count
   consistent with ~50 s at chosen fps.
2. File size ≤ 32 MB (`Get-Item .Length`).
3. Visual spot-check of 5 frames (start, 2D, 3D with toggle, sinogram,
   projection scrub): text legible, no bayer mush, no translated UI, no
   Teleparty tab, no "not connected to a server" panel.
4. Play once in the browser via `tools.browser.preview` (or open the raw file)
   — check the cursor movement reads smoothly at the 1.6× slowdown.
5. README renders: `<img src="ctbeam_demo.gif" width="960" …>` stays; a 1280
   source downsamples in the browser and looks crisp.

## Phase 7 — land it

1. Replace `ctbeam_demo.gif` at repo root (binary is fine; the data-file ban
   covers `.dcm/.ima/.npy/.npz` only).
2. Commit: `docs(readme): regenerate demo GIF at 1280px / 256 colors (≤32 MB)`.
3. Keep `width="960"` in `README.md`; push.
4. Note in the commit/PR body: source = CDP screencast at 1440×810 @2x,
   encoded at 1280×720, fps/colors per ladder step used, final size.

## Pitfalls checklist (all seen in previous runs)

- [ ] First captured frame before the emulation override has the wrong size
      (1439×689 vs 1439×810) — ffmpeg then scales everything to the first
      frame's aspect (1280×612). Drop that frame or force the output size.
- [ ] 3D Plotly legend not rendered yet right after the radio switch →
      poll for `text.legendtext` up to ~20 s before failing.
- [ ] Teleparty extension polluting tabs → `--disable-extensions`
- [ ] Edge auto-translate to German → `--lang=en-US --disable-features=Translate,TranslateUI`
- [ ] German locale decimal comma in `list.txt` → invariant culture
- [ ] Streamlit websocket "not connected" after reload → reload once, wait for `Load Demo Phantom`
- [ ] Slice Options popover covering the 3D legend → close it before 3D
- [ ] Plotly legend toggles not clickable via `.click()` → trusted CDP mouse events
- [ ] Slider drags not registering → keyboard-arrow fallback
- [ ] Forward projection spinner dominating runtime → 4 s duration cap (6 s if slowed)
- [ ] Recorder hang with no output → flush progress markers, run in background with log file

## Rollback

The old GIF is one `git checkout -- ctbeam_demo.gif` away; the plan itself is
committed separately, so revert is independent of the asset.
