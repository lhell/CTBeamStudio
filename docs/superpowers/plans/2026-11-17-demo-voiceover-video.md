# Demo voiceover script + narrated MP4 plan

Date: 2026-11-17 (final cut 2026-11-18)
Status: **built** — `media/demo/ctbeam_demo_voiceover.mp4` (1:27.6, 5.07 MB,
local only; build outputs are gitignored, see Git)
Source visual: `ctbeam_demo.gif` (1280×720, 515 frames, 64.4 s, ~8 fps, the
re-recorded high-quality GIF)
Storyboard source: `docs/superpowers/plans/2026-11-17-demo-gif-generation.md` § Phase 3
Text source: `README.md` (Core utility, Features, Usage) + app labels in `src/visualization/`

## Goal

One narrated MP4 that explains the workflow the GIF shows. The GIF is **never
sped up**; where the narration needs more time, the picture slows down (up to
1.8×) or holds. Where the picture holds a static panel for longer than the
narration needs, the panel is **cut**, not padded. 64 s of silent action became
1:27.6 of explained action.

## Voice

| Choice | Value | Why |
|---|---|---|
| Engine | `edge-tts` 7.3.1 (Microsoft neural) | Only engine here that sounds human; SAPI desktop voices are robotic |
| Voice | `en-US-MichelleNeural` | Calm, warm, low affect. Chosen from a five-voice audition |
| Rate | `+0%` | Engine's natural pace. `-10%` was tried and reverted as too slow |
| Pitch | `+0Hz` | No shift; a pitch trim is what makes TTS sound processed |
| Loudness | `loudnorm I=-16 LUFS, TP=-1.5` | Web standard; measured −16.9 dB mean, −1.5 dB peak |
| Music | none | A bed fights the VO on a 1:28 clip |
| Language | English | GIF UI is English, README is English (`AGENTS.md`: new docs in English) |

Rejected: `en-US-AvaNeural` — reads bright by design, described as "too happy
and unnatural". The audition (`media/demo/audition.py` →
`media/demo/work/audition/audition.mp4`) compares Michelle, Sonia, Jenny, Libby
and Aria on the same line if this is ever revisited.

Caveat: edge-tts has no emotion or style control — one flat read per voice. If
the intonation itself is the complaint, the options are a paid styled TTS
(Azure styles, ElevenLabs) or a human recording, not another edge voice.

## Scene map

Ranges are wall-clock in the current 64.4 s GIF, verified against contact
sheets at 0.5 s and 1.0 s spacing (`build_video.py sheet`). The re-record has a
different order than the old GIF: 2D and 3D share the screen from the first
second, the sinogram tab opens at 13.3 s, the forward projection runs from
24.5 s, and the results appear at 52 s.

| # | GIF range | On screen | Words | VO |
|---|---|---|---|---|
| S1 | 0.0–1.5 | Empty state, cursor → Load Demo Phantom | 9 | 5.1 s |
| S2 | 1.5–7.0 | 2D axial/coronal + 3D gantry side by side | 24 | 9.4 s |
| S3 | 7.0–13.3 | 3D full width, legend overlays, rotate tooltip | 23 | 11.0 s |
| S4 | 13.3–16.0 | Sinogram Inspection tab, measured sinogram | 14 | 5.9 s |
| S5 | 16.0–24.5 | Sample options, beam energy 70 keV | 25 | 12.5 s |
| S6 | 24.5–52.0, trimmed to 24.5–31.5 + 48.5–51.5 | Run Forward Projection, spinner start, completion toast | 32 | 14.4 s |
| S7 | 52.0–56.0 | Measured / simulated / difference, metrics table | 16 | 8.6 s |
| S8 | 56.0–64.4 | Curves, distributions, projection index scrub | 34 | 14.8 s |

177 words ⇒ 81.7 s of speech ⇒ **1:27.6** video (88.7 s timeline incl. padding).
Measured rate is 2.17 words/s at `+0%`.

## Script

Short clauses, present tense, no marketing adjectives. Arrows mark the UI
element on screen at that moment. Commas sit where a speaker would breathe.

**S1 — empty state (still, then the click)**
> This is CT Beam Studio. Load the demo phantom. →

**S2 — viewer, 2D and 3D together**
> No patient data needed, it runs a Shepp-Logan phantom. Axial and coronal
> slices on the left, → and the gantry in 3D on the right. →

**S3 — 3D geometry and overlays**
> The 3D view draws the projection geometry: source trajectory, detector,
> isocenter, and central beam. → Legend entries toggle each overlay, one at a
> time. →

**S4 — sinogram tab**
> Sinogram Inspection puts measured data side by side, with what this volume
> would produce. →

**S5 — sample options**
> Sample options restrict the run to a few projections, rows, or columns, of the
> selected geometry and detector size. → Beam energy sets the
> Hounsfield-to-attenuation conversion. →

**S6 — projection run (click, spinner, completion)**
> Run Forward Projection → traces rays through the volume with parallelproj.
> With a GPU when CUDA is available, otherwise on the CPU. One simulated
> projection per gantry angle, sixty in this case.

**S7 — results**
> Results: measured, simulated, and the difference, → scored per slice with mean
> absolute error, RMSE, and SSIM. →

**S8 — curves, scrub, close**
> Curves and distributions show where the two disagree. Scrub the index → to
> inspect a single view, then read its scores. That comparison, checking scanner
> geometry against real acquisitions, is the point of the tool.

`parallelproj` is spoken as "parallel proj": `scenes.json` carries a `spoken`
field for exactly this, so the TTS gets two words while the subtitle keeps the
real name.

## Timing engine

Audio is the clock. Per scene *i*:

```
D_i     = lead_in + clip + tail + extra_hold        (0.35 + clip + 0.45)
A_i     = natural duration of the scene's frames (after trim)
stretch = clamp(D_i / A_i, 1.0, 1.8)                # never speed up
motion  = A_i * stretch
D_i     = max(D_i, motion)                          # picture may not overrun
freeze  = D_i - motion                              # 30 % pre / 70 % post
```

- `freeze` is the literal pause: the frame is repeated. Total across the clip is
  only ~9 s, because the slower read is mostly absorbed by the slow-mo.
- The 1.8× cap exists because the source is ~8 fps: beyond that the cursor
  visibly jumps. Surplus time becomes a still instead.
- `D_i = max(D_i, motion)` is load-bearing: without it a scene whose narration
  ends early lets its frames run ahead of the voice and every later scene drifts
  out of sync. S6 exposed it at 20.1 s of speech over 23.1 s of action.
- `trim` on a scene keeps a list of `[start, end]` ranges from the source and
  skips the rest. S6 uses it to drop 17 s of an unchanged spinner panel between
  the click and the completion toast.
- `--only` re-records selected scenes without touching clips a player holds.

Built result:

| Scene | VO | stretch | freeze |
|---|---|---|---|
| S1 | 5.1 | 1.80× | 3.16 s |
| S2 | 9.4 | 1.80× | 0.31 s |
| S3 | 11.0 | 1.80× | 0.36 s |
| S4 | 5.9 | 1.80× | 1.99 s |
| S5 | 12.5 | 1.56× | – |
| S6 | 14.4 | 1.52× | – |
| S7 | 8.6 | 1.80× | 2.82 s |
| S8 | 14.8 | 1.80× | 0.55 s |

## Build

Inputs live in `media/demo/`:

| File | Role |
|---|---|
| `scenes.json` | **the script** — id, title, `gif_t0/t1`, optional `trim`, `text` (subtitles) and optional `spoken` (TTS only) |
| `record_voice.py` | scenes.json → `work/voice/S*.mp3` + `.words.json` (`--only` for a subset) |
| `build_video.py` | `sheet` / `preview` / `render` / `subs` / `burn` |
| `audition.py` | five-voice comparison MP4 |

```powershell
# all commands inside ct-viewer
python media\demo\record_voice.py                       # voice clips
python media\demo\build_video.py sheet --source ctbeam_demo.gif --every 2
python media\demo\build_video.py preview                # animatic, no screencast
python media\demo\build_video.py render --source ctbeam_demo.gif
python media\demo\build_video.py subs --source ctbeam_demo.gif   # retitle, no re-encode
python media\demo\build_video.py burn                   # hardsub copy of the mp4
```

Pipeline: PIL upscales/unsharpens each source frame to 1280×688 and pipes raw
RGB to `libx264 -preset slow -crf 20 -pix_fmt yuv420p` at 30 fps; the VO clips
are placed sample-accurately on one numpy track, `loudnorm`-ed, and muxed with
`-c:v copy`, AAC 192k and a `mov_text` subtitle track.

Subtitles take their **text from `scenes.json`** (punctuation intact) and only
the **timing from the TTS word boundaries**, aligned sentence by sentence — the
raw word tokens have no commas, which produced "This is CT Beam Studio Load the
demo phantom" on the first attempt. Cue word counts come from `spoken`, not
`text`, or the "parallel proj" split would shift every boundary after it.

Voice writes are atomic (`.part` then replace): a player holding a clip makes
the run stop with "locked by another program" instead of leaving a truncated
file that plays as silence.

Output: `media/demo/ctbeam_demo_voiceover.mp4` (1280×688, 30 fps, H.264 High,
AAC 48 kHz mono, soft Eng subtitles) + `.srt`.

`burn` writes `ctbeam_demo_voiceover_burned.mp4`: the same cut with the cues
rendered into the picture by libass (Arial 11 against libass's 288 px reference,
white with a dark outline and shadow, bottom-centred). Needed because a
`mov_text` track is off by default in most desktop players and invisible in
browsers, so the soft version looks unsubtitled to a viewer; the burned one
always shows. It costs one extra encode, so it is a little smaller and softer
than the source — invisible on flat UI.

Renders are not atomic at the file level: two concurrent `render` runs race and
the older one can finish last and win. Run one at a time.

## Git

`media/demo/work/` is gitignored (voice clips, frame cache, silent renders).
`media/demo/*.py`, `scenes.json` and this plan are tracked.

The rendered `ctbeam_demo_voiceover.mp4` and its `.srt` are **gitignored**: they
are build outputs, regenerable from `scenes.json` + `ctbeam_demo.gif`, and every
re-render would add another ~5 MB blob to history. The consequence is that
`README.md` cannot link them — clones get the pipeline, not the file. Publish
the MP4 elsewhere (release asset) if it should be visible to users.

`edge-tts` and `imageio-ffmpeg` are installed in `ct-viewer` as tooling only;
they are **not** project dependencies and must not enter `pyproject.toml`.

## Quality notes

- Source is the re-recorded 1280×720 GIF, so the MP4 is near 1:1 and text is
  crisp. The old 480×258 GIF is not used anywhere.
- 1.8× on an ~8 fps source is visible as slightly steppy cursor motion. If that
  matters, re-record at 10 fps and rebuild with the same `scenes.json`; only
  `gif_t0/t1` need re-pinning off a contact sheet.
- The projection wait is real runtime, not padding, but most of it is one
  unchanged panel — hence the trim. S6 now plays at 1.52× over 14.7 s of picture
  instead of 1.0× over 23.1 s.
- `AppTest`-style automation is not involved: the video was checked by extracting
  frames at scene boundaries and reading them, plus `volumedetect` for the audio.

## Open decisions

1. ~~Commit the MP4 and its `.srt`~~ — decided: gitignored (see Git above).
2. README: the GIF embeds stay as they are. A narrated version is only linkable
   if the MP4 is published as a release asset.
3. Music bed: none now; hook exists if a licensed track is supplied.
