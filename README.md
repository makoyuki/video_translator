# video_translator

英語の動画ファイルを音声認識（Whisper）・翻訳（ローカルLLM／Ollama）し、日本語字幕を焼き込んだ動画を生成するツールです。

## 必要環境

- **NVIDIA GPU（CUDA対応）が必須です。** 音声認識にWhisperの`medium`モデルをGPU（`device="cuda"`）で実行するため、CUDA対応GPUがない環境では動作しません（CPUフォールバックはありません）。GPUが検出できない場合は起動時にエラーで停止します。
- **[Ollama](https://ollama.com/) が起動していて、翻訳用のモデルが最低1つ`pull`済みであること。** 翻訳はGoogle翻訳ではなくローカルのOllamaに投げる方式になっています（ネットワーク不要・レート制限なし）。`video_translator.py`冒頭の`OLLAMA_MODEL`でデフォルトのモデル名を指定でき、実行時に利用可能なモデル一覧から選び直すこともできます。
  - 16GB VRAM環境での目安: `qwen3.5:9b`（デフォルト）が品質・速度のバランスが良く推奨。より高品質にしたい場合は`qwen2.5:14b-instruct`、翻訳特化モデルを試したい場合は`7shi/gemma-2-jpn-translate`なども選択肢です。
  - Whisperモデルは音声認識完了後にGPUメモリから解放してから翻訳を開始するため、Whisper（`medium`、約5GB）と翻訳モデルを同時にVRAMへ載せる必要はありません。
- Windows（`run_translator.bat` / `setup_ffmpeg.py` はWindows向け）
- **Python 3.10〜3.11。** `requirements.txt` は `torch==2.5.1+cu118` などCUDA(11.8)版PyTorchを固定しています。Python 3.12以降では他の固定パッケージ（`numba`など）が対応していない場合があるため、3.10または3.11を推奨します。
- FFmpeg（`setup_ffmpeg.py` で自動セットアップ可能）

## セットアップ・実行（Windows / 推奨）

`run_translator.bat` をダブルクリック（またはコマンドプロンプトから実行）してください。初回実行時に以下を自動で行います。

1. `video_translation_env` という名前でvenv環境を作成
2. venv環境を有効化し、`pip install -r requirements.txt` で依存パッケージをインストール
3. `ffmpeg\ffmpeg.exe` が無ければ `setup_ffmpeg.py` でFFmpegを自動セットアップ
4. `video_translator.py` を実行

2回目以降は既存の `video_translation_env` をそのまま使うため、venv作成とパッケージインストールはスキップされます。`requirements.txt` を更新した後など依存パッケージを入れ直したい場合は、`video_translation_env` フォルダを削除してから再度 `run_translator.bat` を実行してください。

## 手動セットアップ（Windows以外 / venvを使わない場合）

```
pip install -r requirements.txt
python video_translator.py
```

`torch==2.5.1+cu118` のようなCUDA版PyTorchはPyPI本体には無く、PyTorch専用のパッケージインデックスからのみ取得できます。そのため `requirements.txt` の先頭に `--extra-index-url https://download.pytorch.org/whl/cu118` を入れてあります（このURLを指定せずに `pip install torch==2.5.1+cu118` 単体を実行すると `Could not find a version that satisfies the requirement torch==2.5.1+cu118` のようなエラーになります）。

動画ファイルのパスを聞かれるので入力すると、`<動画のあるフォルダ>/translated/` 以下に日本語字幕ファイル（`.srt`）と、字幕を焼き込んだ動画が生成されます。

字幕の焼き込みに失敗した場合は、自動的に複数の方式（`subtitles`フィルタ → ASS変換 → MKVへのソフト字幕埋め込み）を順に試みます。
