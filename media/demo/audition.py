"""Voice audition: same line in each candidate voice, one playable MP4.

Ava reads bright by default, which is the "too happy" complaint. This renders
the S1 line in five calmer candidates back to back, with the name on screen and
in the subtitle track, so the choice is made by ear in one playback.

    python media/demo/audition.py
"""

from __future__ import annotations

import asyncio
import subprocess
import wave
from pathlib import Path

import build_video as bv
import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "work" / "audition"
RATE = "+2%"
PITCH = "+0Hz"  # no shift: a pitch trim is what makes TTS sound processed

LINE = (
    "CT Beam Studio explores CT scanner geometry, and simulates projections "
    "from 3D volume data. Nothing is loaded yet, so start with the built-in "
    "demo phantom."
)

CANDIDATES = [
    ("en-US-MichelleNeural", "calm female, warm, low affect"),
    ("en-GB-SoniaNeural", "calm British female, understated"),
    ("en-US-JennyNeural", "neutral female, measured"),
    ("en-GB-LibbyNeural", "lighter British female, still calm"),
    ("en-US-AriaNeural", "female, professional news read"),
]


async def synth(voice: str, text: str, out: Path) -> float:
    c = edge_tts.Communicate(text, voice, rate=RATE, pitch=PITCH)
    audio = bytearray()
    async for ch in c.stream():
        if ch["type"] == "audio":
            audio += ch["data"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(audio))
    pcm = subprocess.run(
        [
            bv.FFMPEG,
            "-v",
            "error",
            "-i",
            str(out),
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(bv.AUDIO_RATE),
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    return len(pcm) / 2 / bv.AUDIO_RATE


def card(voice: str, tag: str, idx: int, n: int) -> Image.Image:
    font = "C:/Windows/Fonts/segoeui.ttf"
    big = ImageFont.truetype(font, 54)
    mid = ImageFont.truetype(font, 30)
    small = ImageFont.truetype(font, 22)
    img = Image.new("RGB", bv.SIZE, (13, 13, 15))
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 0, bv.SIZE[0], 6], fill=(255, 75, 75))
    dr.text((64, 80), f"voice audition  {idx}/{n}", font=small, fill=(120, 124, 132))
    dr.text((64, 130), voice.replace("Neural", ""), font=big, fill=(238, 238, 240))
    dr.text((64, 205), tag, font=mid, fill=(255, 190, 90))
    dr.text((64, 300), "\u201c" + LINE[:78], font=small, fill=(170, 174, 182))
    dr.text((64, 330), LINE[78:156] + "\u201d", font=small, fill=(170, 174, 182))
    dr.text(
        (64, bv.SIZE[1] - 74),
        f"rate {RATE}   pitch {PITCH}   " "same line as scene 1/8",
        font=small,
        fill=(120, 124, 132),
    )
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    n = len(CANDIDATES)
    gap = 0.5
    total = 0.0
    for i, (voice, tag) in enumerate(CANDIDATES, 1):
        d = asyncio.run(synth(voice, LINE, OUT / f"{voice}.mp3"))
        print(f"{voice:28} {d:5.2f}s  {tag}")
        total += d + gap

    track = np.zeros(int(total * bv.AUDIO_RATE) + bv.AUDIO_RATE, dtype=np.float32)
    at = 0
    marks = []
    for voice, _tag in CANDIDATES:
        pcm = subprocess.run(
            [
                bv.FFMPEG,
                "-v",
                "error",
                "-i",
                str(OUT / f"{voice}.mp3"),
                "-f",
                "s16le",
                "-ac",
                "1",
                "-ar",
                str(bv.AUDIO_RATE),
                "-",
            ],
            capture_output=True,
            check=True,
        ).stdout
        s = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        track[at : at + len(s)] += s
        marks.append((at / bv.AUDIO_RATE, len(s) / bv.AUDIO_RATE))
        at += int(len(s) + gap * bv.AUDIO_RATE)

    wav = OUT / "audition.wav"
    with wave.open(str(wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(bv.AUDIO_RATE)
        wf.writeframes((track * 32767).astype(np.int16).tobytes())

    silent = OUT / "audition_silent.mp4"
    proc, emit = bv._encoder(silent)
    for i, ((voice, tag), (t0, d)) in enumerate(zip(CANDIDATES, marks), 1):
        emit(card(voice, tag, i, n), d + gap)
    proc.stdin.close()
    proc.wait()

    srt = OUT / "audition.srt"

    def ts(t):
        return f"00:00:{t:06.3f}".replace(".", ",")

    with srt.open("w", encoding="utf-8") as f:
        for i, ((voice, tag), (t0, d)) in enumerate(zip(CANDIDATES, marks), 1):
            f.write(f"{i}\n{ts(t0)} --> {ts(t0 + d)}\n{voice} - {tag}\n\n")

    out = OUT / "audition.mp4"
    bv.mux(silent, wav, srt, out)
    print(f"\n{out}  ({out.stat().st_size / 1e6:.1f} MB, {total:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
