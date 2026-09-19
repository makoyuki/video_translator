@echo off
REM run_translator.bat
REM 初回実行時はvenv環境の作成・依存パッケージのインストール・FFmpegのセットアップまで自動で行う

setlocal

REM venv環境がなければ作成
if not exist video_translation_env\Scripts\activate.bat (
    echo venv環境が見つからないため作成します...
    python -m venv video_translation_env
    if errorlevel 1 (
        echo venv環境の作成に失敗しました。Pythonがインストールされ、PATHに通っているか確認してください。
        pause
        exit /b 1
    )

    call video_translation_env\Scripts\activate.bat

    echo 依存パッケージをインストール中（初回のみ。数分かかることがあります）...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo 依存パッケージのインストールに失敗しました。requirements.txt の内容やネットワーク接続を確認してください。
        pause
        exit /b 1
    )
) else (
    call video_translation_env\Scripts\activate.bat
)

REM FFmpegセットアップ（初回のみ）
if not exist ffmpeg\ffmpeg.exe (
    echo FFmpegをセットアップ中...
    python setup_ffmpeg.py
)

REM メインスクリプト実行
python video_translator.py

REM 環境を非アクティベート
deactivate
