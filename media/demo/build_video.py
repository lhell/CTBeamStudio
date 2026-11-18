"""Build the narrated demo MP4 from a silent screencast and the VO clips.

The voice is the clock: every scene's picture is stretched (or frozen) to cover
its narration, never the other way round. See
docs/superpowers/plans/2026-11-17-demo-voiceover-video.md for the model.

Usage (inside the ct-viewer env):

    # 1. contact sheet to pin scene boundaries (timestamps burned in)
    python media/demo/build_video.py sheet --source <frames dir> --fps 2

    # 2. render
    python media/demo/build_video.py render --source <frames dir>

<source> is either a directory of frames with an ffconcat list.txt next to it,
or a .gif file. Scene ranges are read from scenes.json (rec_t0/rec_t1 when the
recording is newer than the GIF, else gif_t0/gif_t1).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FPS = 30
SIZE = (1280, 688)  # source aspect is 1.86:1; 688 keeps it 16:9-ish and even
AUDIO_RATE = 48000


# ---------------------------------------------------------------- source frames


def load_source(src: Path) -> tuple[list[Path], list[float]]:
    """Return (frame paths, natural display seconds per frame)."""
    if src.is_dir():
        lst = src / "list.txt"
        if not lst.exists():
            raise SystemExit(f"{lst} missing - the recorder did not finish")
        text = lst.read_text(errors="replace")
        files = re.findall(r"file '?([^'\n]+)'?", text)
        durs = [
            float(d.replace(",", "."))
            for d in re.findall(r"duration\s+([\d.,]+)", text)
        ]
        paths = [src / Path(f).name for f in files]
        if len(durs) != len(paths):
            raise SystemExit(f"list.txt: {len(paths)} files vs {len(durs)} durations")
        return paths, durs

    im = Image.open(src)
    frames, durs = [], []
    for i in range(im.n_frames):
        im.seek(i)
        p = WORK / "gif_frames" / f"g{ i:04d}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            im.convert("RGB").save(p)
        frames.append(p)
        durs.append((im.info.get("duration") or 100) / 1000.0)
    return frames, durs


def scene_ranges(cfg: dict, src: Path) -> list[dict]:
    key = "gif" if src.suffix.lower() == ".gif" else "rec"
    scenes = []
    for s in cfg["scenes"]:
        t0, t1 = s.get(f"{key}_t0"), s.get(f"{key}_t1")
        if t0 is None or t1 is None:
            raise SystemExit(f"scene {s['id']}: no {key}_t0/{key}_t1 in scenes.json")
        scenes.append({**s, "t0": float(t0), "t1": float(t1)})
    return scenes


def schedule(cfg: dict, scenes: list[dict]) -> list[dict]:
    """Attach audio duration, stretch and freeze per scene, and start offsets."""
    durs = json.loads((WORK / "durations.json").read_text())
    t = 0.0
    for i, s in enumerate(scenes):
        audio = durs[s["id"]]
        total = cfg["lead_in_s"] + audio + cfg["tail_s"] + s.get("extra_hold", 0.0)
        nat = sum(s["_durs"])
        stretch = min(cfg["max_stretch"], max(1.0, total / nat)) if nat else 1.0
        motion = nat * stretch
        # a scene can never be shorter than its own picture: that would make the
        # frames run ahead of the voice and shift every later scene
        total = max(total, motion)
        freeze = max(0.0, total - motion)
        s.update(
            audio=audio,
            total=total,
            nat=nat,
            stretch=stretch,
            motion=motion,
            freeze=freeze,
            pre=freeze * 0.3,
            post=freeze * 0.7,
            start=t,
            audio_at=t + cfg["lead_in_s"],
        )
        t += total
        if stretch <= 1.0 and total < nat:
            print(
                f"  warn {i + 1}: scene over-narrated ({total:.1f}s < "
                f"{nat:.1f}s of action) - lengthen the line",
                file=sys.stderr,
            )
    return scenes


def scene_frames(scenes: list[dict], paths: list[Path], durs: list[float]):
    """Slice the source timeline into scenes by cumulative time.

    A scene may carry `trim`: a list of [start, end] ranges that are kept, so a
    long static wait can be cut down without touching the rest of the video.
    """
    cum, t = [], 0.0
    for d in durs:
        cum.append(t)
        t += d
    for s in scenes:
        ranges = s.get("trim") or [[s["t0"], s["t1"]]]
        idx = [i for i, c in enumerate(cum) if any(a <= c < b for a, b in ranges)]
        if not idx:
            raise SystemExit(f"scene {s['id']}: no frames in {ranges}")
        s["_paths"] = [paths[i] for i in idx]
        s["_durs"] = [durs[i] for i in idx]


# ------------------------------------------------------------------ pipelines


def contact_sheet(
    src: Path, every: float, t0: float = 0.0, t1: float | None = None
) -> Path:
    paths, durs = load_source(src)
    cum, t = [], 0.0
    for d in durs:
        cum.append(t)
        t += d
    picks, nxt = [], t0
    for i, c in enumerate(cum):
        if c < t0 or (t1 is not None and c >= t1):
            continue
        if c >= nxt:
            picks.append(i)
            nxt = c + every
    cols, w, h = 5, 384, 216
    rows = (len(picks) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 18)), (18, 18, 20))
    dr = ImageDraw.Draw(sheet)
    for k, i in enumerate(picks):
        x, y = (k % cols) * w, (k // cols) * (h + 18)
        sheet.paste(Image.open(paths[i]).convert("RGB").resize((w, h)), (x, y))
        dr.text((x + 4, y + h + 3), f"{i:04d}  t={cum[i]:6.2f}s", fill=(255, 220, 120))
    out = WORK / f"contact_sheet_{t0:05.1f}{'' if t1 is None else f'_{t1:05.1f}'}.png"
    sheet.save(out)
    print(f"sheet: {len(picks)} thumbs, {t:.1f}s total -> {out}")
    return out


def _encoder(out: Path) -> tuple[subprocess.Popen, callable]:
    """Start an H.264 encoder fed raw RGB, return (process, emit(img, seconds))."""
    proc = subprocess.Popen(
        [
            FFMPEG,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{SIZE[0]}x{SIZE[1]}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-g",
            str(FPS * 2),
            str(out),
        ],
        stdin=subprocess.PIPE,
    )

    def emit(img: Image.Image, seconds: float) -> None:
        n = max(1, int(round(seconds * FPS)))
        buf = img.tobytes()
        for _ in range(n):
            proc.stdin.write(buf)

    return proc, emit


def render_frames(scenes: list[dict], out: Path) -> None:
    """Stream frames to ffmpeg, holding each source frame for its slot."""
    total = sum(s["total"] for s in scenes)
    n_out = int(round(total * FPS))
    proc, emit = _encoder(out)
    sharp = ImageFilter.UnsharpMask(radius=1.2, percent=55, threshold=2)
    written = 0

    for s in scenes:
        slots = [d * s["stretch"] for d in s["_durs"]]
        # keep the total exact: push rounding residue onto the last slot
        residue = s["motion"] - sum(slots)
        if slots:
            slots[-1] += residue
        cache: Image.Image | None = None
        for k, (p, sec) in enumerate(zip(s["_paths"], slots)):
            img = Image.open(p).convert("RGB").resize(SIZE, Image.LANCZOS)
            img = img.filter(sharp)
            if k == 0 and s["pre"] > 0:
                emit(img, s["pre"])
                written += int(round(s["pre"] * FPS))
            emit(img, sec)
            written += int(round(sec * FPS))
            cache = img
        if s["post"] > 0 and cache is not None:
            emit(cache, s["post"])
            written += int(round(s["post"] * FPS))
        print(
            f"  {s['id']}: {s['total']:5.2f}s  stretch {s['stretch']:.2f}x  "
            f"freeze {s['freeze']:4.2f}s"
        )
    while written < n_out:  # pad so the picture never ends before the audio
        emit(cache, 1 / FPS)
        written += 1
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        raise SystemExit("ffmpeg frame encode failed")


def render_cards(scenes: list[dict], out: Path, cfg: dict) -> None:
    """Animatic: one caption card per scene, timed to its VO clip."""
    import textwrap

    from PIL import ImageFont

    font_path = "C:/Windows/Fonts/segoeui.ttf"
    body = ImageFont.truetype(font_path, 34)
    meta = ImageFont.truetype(font_path, 22)
    proc, emit = _encoder(out)
    n = len(scenes)
    for i, s in enumerate(scenes, 1):
        card = Image.new("RGB", SIZE, (13, 13, 15))
        dr = ImageDraw.Draw(card)
        dr.rectangle([0, 0, SIZE[0], 6], fill=(255, 75, 75))
        dr.text((64, 70), f"{i}/{n}   {s['title']}", font=meta, fill=(255, 190, 90))
        y = 150
        for line in textwrap.wrap(s["text"], width=64):
            dr.text((64, y), line, font=body, fill=(238, 238, 240))
            y += 48
        dr.text(
            (64, SIZE[1] - 74),
            f"{cfg['voice']}   rate {cfg['rate']}   "
            f"scene {s['audio']:.1f}s   stretch {s['stretch']:.2f}x",
            font=meta,
            fill=(120, 124, 132),
        )
        emit(card, s["total"])
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        raise SystemExit("ffmpeg card encode failed")


def render_audio(scenes: list[dict], out: Path) -> None:
    """Place each VO clip at its scene offset in a single mono track."""
    total = sum(s["total"] for s in scenes)
    track = np.zeros(int(total * AUDIO_RATE) + AUDIO_RATE, dtype=np.float32)
    for s in scenes:
        mp3 = WORK / "voice" / f"{s['id']}.mp3"
        raw = subprocess.run(
            [
                FFMPEG,
                "-v",
                "error",
                "-i",
                str(mp3),
                "-f",
                "s16le",
                "-ac",
                "1",
                "-ar",
                str(AUDIO_RATE),
                "-",
            ],
            capture_output=True,
            check=True,
        ).stdout
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        at = int(s["audio_at"] * AUDIO_RATE)
        track[at : at + len(pcm)] += pcm
    peak = float(np.max(np.abs(track))) or 1.0
    if peak > 0.99:
        track *= 0.99 / peak
    import wave

    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(AUDIO_RATE)
        wf.writeframes((track * 32767).astype(np.int16).tobytes())


def _sentences(text: str) -> list[str]:
    return [p for p in re.split(r"(?<=[.!?:])\s+", text.strip()) if p]


def _wrap(text: str, a: float, b: float) -> list[tuple[str, float, float]]:
    """Split a long line into <=44 char cues, sharing the time by characters."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > 44:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    if len(lines) == 1:
        return [(text, a, b)]
    span = b - a
    total = sum(len(x) for x in lines) or 1
    out, t = [], a
    for line in lines:
        d = span * len(line) / total
        out.append((line, t, t + d))
        t += d
    return out


def subtitles(scenes: list[dict], out: Path) -> None:
    """Cue text comes from scenes.json (punctuation intact); only the timing
    comes from the TTS word boundaries, aligned sentence by sentence."""

    def ts(t: float) -> str:
        h, rem = divmod(max(t, 0.0), 3600)
        m, sec = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}".replace(".", ",")

    cues = []
    for s in scenes:
        text = s.get("text", "")
        spoken = s.get("spoken", text)
        words = json.loads((WORK / "voice" / f"{s['id']}.words.json").read_text())
        sents = _sentences(text)
        # counts must come from what was actually spoken ("parallel proj" is two
        # tokens, "parallelproj" is one), or the cue boundaries drift
        sp_sents = _sentences(spoken)
        counts = [
            len(x.split()) for x in (sp_sents if len(sp_sents) == len(sents) else sents)
        ]
        total_words = sum(counts) or 1

        spans: list[tuple[float, float]] = []
        if words and abs(len(words) - total_words) <= max(2, 0.25 * total_words):
            idx = 0
            for c in counts:
                if idx >= len(words):
                    break
                end = min(idx + c, len(words)) - 1
                spans.append((words[idx]["t"], words[end]["t"] + words[end]["d"]))
                idx += c
        else:  # token counts drift from the script: spread over the clip
            t = 0.0
            for c in counts:
                d = s["audio"] * c / total_words
                spans.append((t, t + d))
                t += d

        for sent, (a, b) in zip(sents, spans):
            for piece, pa, pb in _wrap(sent, a, b):
                cues.append((pa + s["audio_at"], pb + s["audio_at"], piece))

    with out.open("w", encoding="utf-8") as f:
        for i, (a, b, text) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(max(b, a + 0.7))}\n{text}\n\n")


def _mux_copy(silent: Path, norm_wav: Path, srt: Path, out: Path) -> None:
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-v",
            "error",
            "-i",
            str(silent),
            "-i",
            str(norm_wav),
            "-i",
            str(srt),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
    )


def mux(silent: Path, wav: Path, srt: Path, out: Path) -> None:
    norm = WORK / "audio_norm.wav"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-v",
            "error",
            "-i",
            str(wav),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar",
            str(AUDIO_RATE),
            str(norm),
        ],
        check=True,
    )
    _mux_copy(silent, norm, srt, out)


# ---------------------------------------------------------------------- entry


def _need(p: Path | None) -> Path:
    if p is None:
        raise SystemExit("--source is required for sheet/render")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sheet", "render", "preview", "subs"])
    ap.add_argument("--source", type=Path, help="frames dir or .gif (sheet/render)")
    ap.add_argument(
        "--every",
        type=float,
        default=2.0,
        help="seconds between contact-sheet thumbnails",
    )
    ap.add_argument("--t0", type=float, default=0.0, help="sheet range start")
    ap.add_argument("--t1", type=float, default=None, help="sheet range end")
    ap.add_argument("--out", type=Path, default=ROOT / "ctbeam_demo_voiceover.mp4")
    a = ap.parse_args()

    if a.cmd == "sheet":
        contact_sheet(_need(a.source), a.every, a.t0, a.t1)
        return 0

    WORK.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "scenes.json").read_text())

    if a.cmd == "preview":
        # animatic: cards only, no screencast - lets the narration be reviewed
        scenes = [
            {**s, "t0": 0.0, "t1": 1.0, "_paths": [None], "_durs": [0.0]}
            for s in cfg["scenes"]
        ]
        out = WORK / "preview.mp4"
        silent, wav = WORK / "preview_silent.mp4", WORK / "preview_audio.wav"
        schedule(cfg, scenes)
        print("video:")
        render_cards(scenes, silent, cfg)
        render_audio(scenes, wav)
        subtitles(scenes, out.with_suffix(".srt"))
        mux(silent, wav, out.with_suffix(".srt"), out)
        print(f"\n{out}  ({out.stat().st_size / 1e6:.1f} MB)")
        return 0

    scenes = scene_ranges(cfg, _need(a.source))
    paths, durs = load_source(a.source)
    scene_frames(scenes, paths, durs)
    schedule(cfg, scenes)

    if a.cmd == "subs":
        # rebuild subtitles + remux from the silent render already on disk
        srt = a.out.with_suffix(".srt")
        subtitles(scenes, srt)
        _mux_copy(WORK / "silent.mp4", WORK / "audio_norm.wav", srt, a.out)
        print(f"{srt}\n{a.out}  ({a.out.stat().st_size / 1e6:.1f} MB)")
        return 0

    silent = WORK / "silent.mp4"
    wav = WORK / "audio.wav"
    srt = a.out.with_suffix(".srt")
    print("video:")
    render_frames(scenes, silent)
    print("audio:")
    render_audio(scenes, wav)
    subtitles(scenes, srt)
    mux(silent, wav, srt, a.out)
    (WORK / "timeline.json").write_text(
        json.dumps(
            [
                {
                    k: s[k]
                    for k in (
                        "id",
                        "title",
                        "text",
                        "audio",
                        "audio_at",
                        "total",
                        "start",
                    )
                    if k in s
                }
                for s in scenes
            ],
            indent=1,
        )
    )
    print(f"\n{a.out}  ({a.out.stat().st_size / 1e6:.1f} MB)")
    print(f"{srt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
