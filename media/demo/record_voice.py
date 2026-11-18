"""Render the voiceover clips for the narrated demo.

Reads scenes.json, writes one MP3 per scene plus word-boundary timing, then
prints the measured durations. Audio is the pacing clock for the video build,
so this runs before any frame is touched.

Run inside the ct-viewer env:
    python media/demo/record_voice.py
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work" / "voice"
FFPROBE = Path(imageio_ffmpeg.get_ffmpeg_exe()).with_name("ffprobe-win-x86_64.exe")


async def synth(scene: dict, cfg: dict, out: Path) -> list[dict]:
    free = edge_tts.Communicate(
        scene.get("spoken", scene["text"]),
        cfg["voice"],
        rate=cfg.get("rate", "-5%"),
        pitch=cfg.get("pitch", "-2Hz"),
        # 7.3.1 defaults to SentenceBoundary; the cue builder needs words
        boundary="WordBoundary",
    )
    words: list[dict] = []
    audio = bytearray()
    async for chunk in free.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            words.append(
                {
                    "t": chunk["offset"] / 1e7,  # 100 ns ticks -> seconds
                    "d": chunk["duration"] / 1e7,
                    "w": chunk["text"],
                }
            )
    if not words:
        print(f"  warn: {scene['id']} produced no word boundaries", file=sys.stderr)
    # atomic publish: a player holding the old file must never see a half write
    tmp = out.with_suffix(out.suffix + ".part")
    tmp.write_bytes(bytes(audio))
    try:
        tmp.replace(out)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise SystemExit(
            f"{out.name} is locked by another program (a media player?). "
            "Close it and rerun."
        ) from None
    (out.with_suffix(".words.json")).write_text(json.dumps(words, indent=1))
    return words


def duration(path: Path) -> float:
    """Duration in seconds via ffprobe."""
    if FFPROBE.exists():
        out = subprocess.run(
            [
                str(FFPROBE),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return float(out.strip())
    # mp3 fallback: CBR 24 kHz mono 48 kbit/s, headerless estimate is close
    return path.stat().st_size / 6000.0


async def main() -> int:
    # --only lets me re-render a few scenes without touching clips a player holds
    only = None
    if "--only" in sys.argv:
        raw = sys.argv[sys.argv.index("--only") + 1]
        only = {s.strip().upper() for s in raw.split(",") if s.strip()}

    cfg = json.loads((ROOT / "scenes.json").read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    dur_file = ROOT / "work" / "durations.json"
    prev = json.loads(dur_file.read_text()) if dur_file.exists() else {}

    rows = []
    for scene in cfg["scenes"]:
        sid = scene["id"]
        out = WORK / f"{sid}.mp3"
        if only and sid not in only and sid in prev and out.exists():
            # keep the audio, but always measure the file that is actually there
            d = duration(out)
            print(f"{sid}  {d:6.2f}s   (kept)")
        else:
            try:
                await synth(scene, cfg, out)
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001 - one retry, then report
                print(f"{sid}: {exc} - retrying once", file=sys.stderr)
                await asyncio.sleep(3)
                await synth(scene, cfg, out)
            d = duration(out)
            print(f"{sid}  {d:6.2f}s   (recorded)")
        gif = scene["gif_t1"] - scene["gif_t0"]
        rows.append((sid, d, gif))

    total = sum(r[1] for r in rows)
    print(f"\ntotal VO {total:6.2f}s")
    print(
        f"video   {total + len(rows) * (cfg['lead_in_s'] + cfg['tail_s']):6.2f}s"
        f"  (+{len(rows)} x lead/tail padding)"
    )
    dur_file.write_text(json.dumps({r[0]: round(r[1], 3) for r in rows}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
