# video_translator

英語の動画ファイルを音声認識（Whisper）・翻訳（Google翻訳）し、日本語字幕を焼き込んだ動画を生成するツールです。

## 必要環境

- **NVIDIA GPU（CUDA対応）が必須です。** 音声認識にWhisperの`medium`モデルをGPU（`device="cuda"`）で実行するため、CUDA対応GPUがない環境では動作しません（CPUフォールバックはありません）。GPUが検出できない場合は起動時にエラーで停止します。
- Windows（`run_translator.bat` / `setup_ffmpeg.py` はWindows向け）
- Python
- FFmpeg（`setup_ffmpeg.py` で自動セットアップ可能）

## セットアップ

```
pip install -r requirements.txt
```

## 実行

```
python video_translator.py
```

動画ファイルのパスを聞かれるので入力すると、`<動画のあるフォルダ>/translated/` 以下に日本語字幕ファイル（`.srt`）と、字幕を焼き込んだ動画が生成されます。

字幕の焼き込みに失敗した場合は、自動的に複数の方式（`subtitles`フィルタ → ASS変換 → MKVへのソフト字幕埋め込み）を順に試みます。
