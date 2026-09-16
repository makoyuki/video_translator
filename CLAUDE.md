# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows-oriented CLI tool that takes an English video file and produces a copy with burned-in Japanese subtitles. It transcribes speech with Whisper, translates each segment with Google Translate, writes an SRT, then uses FFmpeg to burn the subtitles into the video.

## Setup and running

There is no build step, package manifest, or test suite — this is a flat collection of scripts run directly with Python.

```bash
pip install -r requirements.txt
python video_translator.py          # interactive: prompts for a video file path
python setup_ffmpeg.py              # one-time: downloads a Windows FFmpeg build into ./ffmpeg/
python subtitle_adder.py video.mp4 subtitles.srt output.mp4   # burn an existing SRT into a video standalone
```

`run_translator.bat` is the intended Windows entry point: it activates `video_translation_env\Scripts\activate.bat`, runs `setup_ffmpeg.py` if `ffmpeg\ffmpeg.exe` is missing, then runs `video_translator.py`.

`requirements.txt` pins `torch`/`torchaudio`/`torchvision` to `+cu118` CUDA wheels and `video_translator.py` hardcodes `whisper.load_model("medium", device="cuda")` — this project assumes an NVIDIA GPU is present. There's no CPU fallback path.

## Architecture

- **`video_translator.py`** — the main entry point and `VideoTranslator` class, orchestrating the full pipeline: Whisper transcription (English, forced via `language="en"`) → per-segment Google Translate call (`en`→`ja`) → SRT construction via `pysrt` → FFmpeg subtitle burn-in via the `subtitles` filter with hardcoded `force_style`. It also does its own minimal FFmpeg discovery (checks `ffmpeg/ffmpeg.exe` relative to cwd, falls back to PATH).
- **`subtitle_adder.py`** — a standalone, more defensive version of the "burn subtitles into video" step. Given an existing video + SRT, it tries three FFmpeg strategies in order until one succeeds: (1) basic `subtitles` filter, (2) convert SRT→ASS itself and use the `ass` filter, (3) mux the SRT in as a soft subtitle stream into an MKV container. This logic is **not** currently called by `video_translator.py`, which has its own single-strategy `add_subtitles_to_video` — treat the two as separate implementations of the same concept rather than assuming one calls the other.
- **`setup_ffmpeg.py`** — downloads a prebuilt Windows FFmpeg zip (BtbN builds) and extracts `ffmpeg.exe` into `./ffmpeg/`, adding it to `PATH` for the current process. Windows-only (looks for `ffmpeg.exe` specifically).

All user-facing strings, comments, and console output across the codebase are in Japanese.

Translation is per-subtitle-segment (one `Translator().translate()` call per Whisper segment, not a single batched call), and each segment translation is individually try/excepted — a failed translation falls back to leaving that segment's text in English rather than aborting the run.
