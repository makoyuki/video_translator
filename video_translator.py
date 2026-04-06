import whisper
import os
import pysrt
from googletrans import Translator
import subprocess
from pathlib import Path
import sys

class VideoTranslator:
    def __init__(self):
        print("初期化中...")
        
        # FFmpegの確認
        self.setup_ffmpeg()
        
        # Whisperモデル読み込み
        print("Whisperモデルを読み込み中...")
        self.model = whisper.load_model("medium", device="cuda")  # GPU使用を明示
        
        # 翻訳器初期化
        self.translator = Translator()
        
        print("準備完了！")
    
    def setup_ffmpeg(self):
        """FFmpeg設定"""
        # ローカルFFmpegを優先使用
        local_ffmpeg = Path("ffmpeg/ffmpeg.exe")
        if local_ffmpeg.exists():
            ffmpeg_path = str(local_ffmpeg.parent.absolute())
            os.environ['PATH'] = f"{ffmpeg_path};{os.environ.get('PATH', '')}"
        
        # FFmpegが使用可能か確認
        try:
            subprocess.run(['ffmpeg', '-version'], 
                          capture_output=True, check=True)
            print("FFmpeg: 利用可能")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("警告: FFmpegが見つかりません。字幕ファイルのみ作成されます。")
    
    def translate_video(self, video_path):
        """動画を翻訳して字幕付き動画を生成"""
        
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")
        
        # 出力ディレクトリ作成
        output_dir = video_path.parent / "translated"
        output_dir.mkdir(exist_ok=True)
        
        srt_path = output_dir / f"{video_path.stem}_japanese.srt"
        output_video = output_dir / f"{video_path.stem}_with_subtitles.mp4"
        
        print(f"\n処理開始: {video_path.name}")
        print("=" * 50)
        
        try:
            # Step 1: 音声認識
            print("?? 音声認識中...")
            result = self.model.transcribe(
                str(video_path), 
                language="en",
                verbose=True
            )
            
            print(f"? {len(result['segments'])} セグメントを検出")
            
            # Step 2: 翻訳と字幕作成
            print("\n?? 翻訳・字幕作成中...")
            self.create_japanese_subtitles(result, srt_path)
            
            # Step 3: 動画に字幕追加
            print("\n?? 字幕を動画に追加中...")
            success = self.add_subtitles_to_video(video_path, srt_path, output_video)
            
            if success:
                print(f"\n? 完成: {output_video}")
                return str(output_video)
            else:
                print(f"\n??  字幕ファイルのみ作成: {srt_path}")
                return str(srt_path)
                
        except Exception as e:
            print(f"? エラー: {e}")
            raise
    
    def create_japanese_subtitles(self, transcription_result, srt_path):
        """字幕作成"""
        subs = pysrt.SubRipFile()
        total_segments = len(transcription_result["segments"])
        
        for i, segment in enumerate(transcription_result["segments"], 1):
            try:
                # 翻訳実行
                translated = self.translator.translate(
                    segment["text"],
                    src='en',
                    dest='ja'
                )
                japanese_text = translated.text
                
                # 字幕エントリ作成
                sub = pysrt.SubRipItem()
                sub.index = i
                sub.start = pysrt.SubRipTime(seconds=segment["start"])
                sub.end = pysrt.SubRipTime(seconds=segment["end"])
                sub.text = japanese_text
                
                subs.append(sub)
                
                # 進捗表示
                if i % 5 == 0 or i == total_segments:
                    print(f"   進捗: {i}/{total_segments} ({i/total_segments*100:.1f}%)")
                    
            except Exception as e:
                print(f"   翻訳エラー (セグメント {i}): {e}")
                # エラー時は英語のまま
                sub = pysrt.SubRipItem()
                sub.index = i
                sub.start = pysrt.SubRipTime(seconds=segment["start"])
                sub.end = pysrt.SubRipTime(seconds=segment["end"])
                sub.text = segment["text"]
                subs.append(sub)
        
        # 字幕ファイル保存
        subs.save(str(srt_path), encoding='utf-8')
        print(f"? 字幕ファイル保存完了: {srt_path}")
    
    def add_subtitles_to_video(self, video_path, srt_path, output_path):
        """字幕を動画に焼き込み"""
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', f"subtitles='{str(srt_path)}':force_style='Fontsize=24,PrimaryColour=&Hffffff&,BackColour=&H80000000&,Bold=1'",
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-y',
            str(output_path)
        ]
        
        try:
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"   FFmpegエラー: {e}")
            return False
        except FileNotFoundError:
            print("   FFmpegが見つかりません")
            return False

def main():
    print("動画翻訳ツール")
    print("=" * 30)
    
    # 動画ファイル選択
    while True:
        video_file = input("\n動画ファイルのパスを入力してください: ").strip().strip('"')
        
        if not video_file:
            print("終了します")
            return
        
        if os.path.exists(video_file):
            break
        else:
            print("? ファイルが見つかりません。もう一度入力してください。")
    
    try:
        # 翻訳実行
        translator = VideoTranslator()
        result = translator.translate_video(video_file)
        
        print(f"\n?? 処理完了！")
        print(f"結果: {result}")
        
    except Exception as e:
        print(f"\n? エラーが発生しました: {e}")
    
    input("\nEnterキーで終了...")

if __name__ == "__main__":
    main()