"""Generate a voiceover with a running VoiceStudio backend.

Usage:
    python3 scripts/generate.py script.txt out/voiceover.wav

Reads the narration text, splits it into ~900-char chunks at sentence
boundaries, synthesizes each chunk through the OpenAI-compatible endpoint
POST /v1/audio/speech, then joins the WAVs with ffmpeg.

Env:
    PROFILE_ID  voice-profile id from POST /profiles (required)
    MODEL       engine id, default "omnivoice"
                (OpenAI aliases tts-1 / tts-1-hd also work)
    BASE_URL    backend base, default http://127.0.0.1:3900
"""

import json
import os
import re
import subprocess
import sys
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:3900")
PROFILE_ID = os.environ["PROFILE_ID"]
MODEL = os.environ.get("MODEL", "omnivoice")
MAX_CHARS = 900


def split_chunks(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) + 1 > MAX_CHARS:
            chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    return chunks


def synth(text, idx, outdir):
    payload = json.dumps(
        {
            "model": MODEL,
            "voice": PROFILE_ID,
            "input": text,
            "response_format": "wav",
        }
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/v1/audio/speech",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as resp:
        audio = resp.read()
    path = os.path.join(outdir, f"chunk_{idx:03d}.wav")
    with open(path, "wb") as f:
        f.write(audio)
    print(f"chunk {idx}: {len(text)} chars -> {len(audio)} bytes")
    return path


def main():
    script_path, out_path = sys.argv[1], sys.argv[2]
    text = open(script_path).read().strip()
    if not text:
        raise SystemExit("script file is empty")

    chunk_dir = "out/chunks"
    os.makedirs(chunk_dir, exist_ok=True)

    files = [
        synth(chunk, i, chunk_dir)
        for i, chunk in enumerate(split_chunks(text))
    ]
    print(f"synthesized {len(files)} chunks")

    with open("out/concat.txt", "w") as f:
        for p in files:
            f.write(f"file '{os.path.abspath(p)}'\n")

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", "out/concat.txt", "-c", "copy", out_path,
        ],
        check=True,
    )
    print("wrote", out_path)


main()
