# setup_ffmpeg.py - FFmpegを自動でダウンロード・設定
import os
import zipfile
import urllib.request
from pathlib import Path

def download_ffmpeg():
    """Windows用FFmpegを自動ダウンロード・設定"""
    
    ffmpeg_dir = Path("ffmpeg")
    ffmpeg_dir.mkdir(exist_ok=True)
    
    if not (ffmpeg_dir / "ffmpeg.exe").exists():
        print("FFmpegをダウンロード中...")
        
        # FFmpeg Windows版のURL（gyan.devから）
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        
        zip_path = "ffmpeg.zip"
        urllib.request.urlretrieve(url, zip_path)
        
        print("展開中...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("temp_ffmpeg")
        
        # ファイルを適切な場所に移動
        temp_dir = Path("temp_ffmpeg")
        for item in temp_dir.rglob("*"):
            if item.name == "ffmpeg.exe":
                item.rename(ffmpeg_dir / "ffmpeg.exe")
                break
        
        # 一時ファイル削除
        import shutil
        shutil.rmtree("temp_ffmpeg")
        os.remove(zip_path)
        
        print("FFmpegの設定完了")
    else:
        print("FFmpegは既にインストール済み")
    
    # 環境変数に追加
    ffmpeg_path = str(ffmpeg_dir.absolute())
    current_path = os.environ.get('PATH', '')
    if ffmpeg_path not in current_path:
        os.environ['PATH'] = f"{ffmpeg_path};{current_path}"
    
    return ffmpeg_dir / "ffmpeg.exe"

if __name__ == "__main__":
    download_ffmpeg()