@echo off
REM run_translator.bat

REM venv環境をアクティベートして実行
call video_translation_env\Scripts\activate.bat

REM FFmpegセットアップ（初回のみ）
if not exist ffmpeg\ffmpeg.exe (
    echo FFmpegをセットアップ中...
    python setup_ffmpeg.py
)

REM メインスクリプト実行
python video_translator.py

REM 環境を非アクティベート
deactivate