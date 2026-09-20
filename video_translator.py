import whisper
import os
import re
import pysrt
import torch
import time
import requests
import subprocess
from pathlib import Path
from subtitle_adder import SubtitleAdder

# 焼き込み字幕のスタイル（force_style）。ffmpegの subtitles フィルタにそのまま渡す
SUBTITLE_FORCE_STYLE = "Fontsize=24,PrimaryColour=&Hffffff&,BackColour=&H80000000&,Bold=1"

# 翻訳に使うOllamaの設定。既定値はここを書き換えるだけで変更できるほか、
# 環境変数 OLLAMA_HOST / OLLAMA_MODEL でコードを変更せず上書きすることもできる
# （例: Ollamaが別マシンで動いている場合に set OLLAMA_HOST=http://192.168.1.10:11434）
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")

# 1回のOllamaリクエストでまとめて翻訳するセグメント数
TRANSLATE_BATCH_SIZE = 20

class VideoTranslator:
    def __init__(self):
        print("初期化中...")

        # FFmpegの確認
        self.setup_ffmpeg()

        # GPU(CUDA)の確認。本ツールはGPU前提で動作するため、無い場合はここで明示的に停止する
        self.check_gpu()

        # 翻訳に使うOllamaモデルを選択（Whisperモデルの読み込み前に確認することで、
        # Ollamaが起動していない場合に無駄な読み込み時間をかけずに済む）
        self.ollama_model = self.select_ollama_model()

        # Whisperモデル読み込み
        print("Whisperモデルを読み込み中...")
        self.model = whisper.load_model("medium", device="cuda")  # GPU使用を明示

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

    def select_ollama_model(self):
        """Ollamaで利用可能なモデル一覧を取得し、翻訳に使うモデルを選択する"""
        try:
            resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            raise RuntimeError(
                f"Ollamaに接続できませんでした（{OLLAMA_HOST}）。Ollamaが起動しているか確認してください。\n詳細: {e}"
            )

        if not models:
            raise RuntimeError(
                "Ollamaで利用可能なモデルが見つかりません。`ollama pull <モデル名>` でモデルを取得してください。"
            )

        default_index = models.index(OLLAMA_MODEL) + 1 if OLLAMA_MODEL in models else 1

        print("\n利用可能なOllamaモデル:")
        for i, name in enumerate(models, 1):
            marker = " (デフォルト)" if i == default_index else ""
            print(f"  {i}. {name}{marker}")

        choice = input(
            f"\n翻訳に使うモデルの番号を入力してください（Enterで {models[default_index - 1]} を使用）: "
        ).strip()

        if not choice:
            return models[default_index - 1]

        if choice.isdigit() and 1 <= int(choice) <= len(models):
            return models[int(choice) - 1]

        print("入力が不正なため、デフォルトのモデルを使用します。")
        return models[default_index - 1]

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

            # Whisperモデルは音声認識完了後は不要なため、GPUメモリを解放する
            # （Ollamaの翻訳モデルとGPUメモリを取り合わないようにするため）
            del self.model
            torch.cuda.empty_cache()

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
    
    def _ollama_generate(self, prompt, timeout=180):
        """Ollamaにプロンプトを送り、生成されたテキストを返す"""
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            # think=False: Qwen3系などの拡張思考(thinking)対応モデルは、これを付けないと
            # 翻訳のような単純なタスクでも長大な内部思考を生成し大幅に遅くなる（実測で約60倍）。
            # 思考非対応のモデルに渡しても無視されるだけで無害なので常に付けている。
            json={"model": self.ollama_model, "prompt": prompt, "stream": False, "think": False},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["response"]

    @staticmethod
    def _clean_llm_output(text):
        """LLMが付けがちなコードフェンスや前後の引用符を取り除く"""
        text = text.strip()
        text = re.sub(r'^```[a-zA-Z]*\s*|\s*```$', '', text).strip()
        if len(text) >= 2 and text[0] == text[-1] == '"':
            text = text[1:-1].strip()
        return text

    def _parse_numbered_response(self, response_text, expected_count):
        """"番号: 訳文" 形式の応答を番号順のリストに変換する。行数が合わなければNoneを返す"""
        pattern = re.compile(r'^\s*(\d+)\s*[:：]\s*(.*)$')
        results = {}
        for line in response_text.splitlines():
            m = pattern.match(line)
            if m:
                results[int(m.group(1))] = self._clean_llm_output(m.group(2))

        if len(results) != expected_count:
            return None
        try:
            return [results[i] for i in range(1, expected_count + 1)]
        except KeyError:
            return None

    def translate_single(self, text, retries=2):
        """1件だけ翻訳する（バッチ翻訳が失敗したセグメントのフォールバック用）。
        全て失敗した場合はNoneを返す（呼び出し側で原文へのフォールバックを行う）"""
        prompt = (
            "以下の英語の字幕を、自然で簡潔な日本語字幕に翻訳してください。\n"
            "翻訳結果の日本語のみを出力し、説明・前置き・元の英語文は含めないでください。\n\n"
            f"{text}"
        )
        for attempt in range(1, retries + 1):
            try:
                result = self._clean_llm_output(self._ollama_generate(prompt))
                if result:
                    return result
            except Exception as e:
                print(f"   翻訳エラー（{attempt}/{retries}回目）: {e}")
            if attempt < retries:
                time.sleep(1.0)
        return None

    def translate_batch(self, texts, retries=2):
        """複数の英語テキストをまとめて翻訳し、日本語訳のリストを返す（要素数はtextsと同じ）。
        バッチでの翻訳に失敗した場合は1件ずつ翻訳する（それも失敗した要素はNone）"""
        numbered_input = "\n".join(f"{i + 1}: {t}" for i, t in enumerate(texts))
        prompt = (
            "以下は英語の映画・動画の字幕です。各行を自然で簡潔な日本語字幕に翻訳してください。\n"
            "出力は入力と同じ行数・同じ番号で、必ず \"番号: 訳文\" の形式にしてください。\n"
            "説明・前置き・元の英語文は一切含めず、翻訳結果のみを出力してください。\n\n"
            f"{numbered_input}"
        )

        for attempt in range(1, retries + 1):
            try:
                response_text = self._ollama_generate(prompt)
                parsed = self._parse_numbered_response(response_text, len(texts))
                if parsed is not None:
                    return parsed
                print(f"   バッチ翻訳の応答形式が不正でした（{attempt}/{retries}回目）")
            except Exception as e:
                print(f"   バッチ翻訳エラー（{attempt}/{retries}回目）: {e}")
            if attempt < retries:
                time.sleep(1.0)

        print("   バッチ翻訳に失敗したため、このバッチは1件ずつ翻訳します")
        return [self.translate_single(t) for t in texts]

    def create_japanese_subtitles(self, transcription_result, srt_path):
        """字幕作成"""
        subs = pysrt.SubRipFile()
        segments = transcription_result["segments"]
        total_segments = len(segments)

        for batch_start in range(0, total_segments, TRANSLATE_BATCH_SIZE):
            batch = segments[batch_start:batch_start + TRANSLATE_BATCH_SIZE]
            texts = [segment["text"].strip() for segment in batch]
            translations = self.translate_batch(texts)

            for offset, (segment, translated) in enumerate(zip(batch, translations)):
                sub = pysrt.SubRipItem()
                sub.index = batch_start + offset + 1
                sub.start = pysrt.SubRipTime(seconds=segment["start"])
                sub.end = pysrt.SubRipTime(seconds=segment["end"])
                sub.text = translated if translated else segment["text"]
                subs.append(sub)

            done = batch_start + len(batch)
            print(f"   進捗: {done}/{total_segments} ({done/total_segments*100:.1f}%)")

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