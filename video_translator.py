import whisper
import os
import pysrt
import torch
import time
from deep_translator import GoogleTranslator
import subprocess
from pathlib import Path
from subtitle_adder import SubtitleAdder

# 焼き込み字幕のスタイル（force_style）。ffmpegの subtitles フィルタにそのまま渡す
SUBTITLE_FORCE_STYLE = "Fontsize=24,PrimaryColour=&Hffffff&,BackColour=&H80000000&,Bold=1"

class VideoTranslator:
    def __init__(self):
        print("初期化中...")

        # FFmpegの確認
        self.setup_ffmpeg()

        # GPU(CUDA)の確認。本ツールはGPU前提で動作するため、無い場合はここで明示的に停止する
        self.check_gpu()

        # Whisperモデル読み込み
        print("Whisperモデルを読み込み中...")
        self.model = whisper.load_model("medium", device="cuda")  # GPU使用を明示

        # 翻訳器初期化
        self.translator = GoogleTranslator(source='en', target='ja')

        # 字幕焼き込み（複数の方式を順に試すフォールバック処理はSubtitleAdderに委譲）
        self.subtitle_adder = SubtitleAdder()

        print("準備完了！")

    def check_gpu(self):
        """CUDA対応GPUが利用可能か確認する。本ツールはGPU必須（CPUフォールバックなし）"""
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA対応のNVIDIA GPUが検出されませんでした。本ツールはGPU必須です（CPUでは動作しません）。\n"
                "NVIDIAドライバと、CUDA対応版のPyTorchがインストールされているか確認してください。"
            )
        print(f"GPU検出: {torch.cuda.get_device_name(0)}")

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
            
            # Step 3: 動画に字幕追加（焼き込み。失敗時は複数の方式に自動フォールバック）
            print("\n?? 字幕を動画に追加中...")
            result_path = self.subtitle_adder.add_subtitles_to_video(
                video_path, srt_path, output_video, force_style=SUBTITLE_FORCE_STYLE
            )

            if result_path:
                print(f"\n? 完成: {result_path}")
                return str(result_path)
            else:
                print(f"\n??  字幕ファイルのみ作成: {srt_path}")
                return str(srt_path)
                
        except Exception as e:
            print(f"? エラー: {e}")
            raise
    
    def translate_text(self, text, retries=3, retry_delay=2.0):
        """英語テキストを日本語に翻訳する。レート制限等で断続的に失敗することがあるため、
        待機時間を伸ばしながら数回リトライする。全て失敗した場合はNoneを返す（呼び出し側で原文へのフォールバックを行う）"""
        for attempt in range(1, retries + 1):
            try:
                result = self.translator.translate(text)
                # deep-translatorはGoogle側がブロック等で翻訳できなかった場合、例外を出さず
                # 原文をそのまま返すことがある。原文と一致する場合は翻訳失敗とみなしリトライする
                if not result or result.strip() == text.strip():
                    raise ValueError("翻訳結果が原文と同一（翻訳できていない可能性）")
                return result
            except Exception as e:
                if attempt < retries:
                    time.sleep(retry_delay * attempt)
                else:
                    print(f"   翻訳エラー（{retries}回リトライ後も失敗）: {e}")
            finally:
                # 連続リクエストによるブロックを避けるための待機
                time.sleep(0.3)
        return None

    def create_japanese_subtitles(self, transcription_result, srt_path):
        """字幕作成"""
        subs = pysrt.SubRipFile()
        total_segments = len(transcription_result["segments"])

        for i, segment in enumerate(transcription_result["segments"], 1):
            japanese_text = self.translate_text(segment["text"])

            # 字幕エントリ作成（翻訳に失敗した場合は原文のまま）
            sub = pysrt.SubRipItem()
            sub.index = i
            sub.start = pysrt.SubRipTime(seconds=segment["start"])
            sub.end = pysrt.SubRipTime(seconds=segment["end"])
            sub.text = japanese_text if japanese_text is not None else segment["text"]

            subs.append(sub)

            # 進捗表示
            if i % 5 == 0 or i == total_segments:
                print(f"   進捗: {i}/{total_segments} ({i/total_segments*100:.1f}%)")

        # 字幕ファイル保存
        subs.save(str(srt_path), encoding='utf-8')
        print(f"? 字幕ファイル保存完了: {srt_path}")

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