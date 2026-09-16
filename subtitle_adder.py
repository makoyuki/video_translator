# subtitle_adder.py
import subprocess
import sys
from pathlib import Path
import pysrt

class SubtitleAdder:
    def __init__(self):
        pass

    @staticmethod
    def escape_ffmpeg_filter_path(path):
        """Windowsパス（ドライブレターの':'やバックスラッシュ）をffmpegのフィルタ引数として安全な形式に変換"""
        return str(path).replace('\\', '/').replace(':', '\\:')

    def add_subtitles_to_video(self, video_path, srt_path, output_path, force_style=None):
        """動画に字幕を追加（複数の方法を順に試行し、実際に書き出されたファイルのPathを返す。全て失敗した場合はNone）"""

        video_path = Path(video_path)
        srt_path = Path(srt_path)
        output_path = Path(output_path)

        if not video_path.exists():
            raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")
        if not srt_path.exists():
            raise FileNotFoundError(f"字幕ファイルが見つかりません: {srt_path}")

        print(f"動画: {video_path}")
        print(f"字幕: {srt_path}")
        print(f"出力: {output_path}")

        # 方法1: 基本的なsubtitlesフィルター（焼き込み）
        if self.try_basic_subtitles(video_path, srt_path, output_path, force_style):
            return output_path

        # 方法2: ASSファイル使用（焼き込み）
        if self.try_ass_subtitles(video_path, srt_path, output_path):
            return output_path

        # 方法3: 外部字幕として埋め込み（焼き込みではなくソフトサブとしてMKVに格納）
        if self.try_external_subtitles(video_path, srt_path, output_path):
            return output_path.with_suffix('.mkv')

        return None

    def try_basic_subtitles(self, video_path, srt_path, output_path, force_style=None):
        """基本的なsubtitlesフィルター"""
        print("\n方法1: 基本的なsubtitlesフィルター")

        vf = f'subtitles={self.escape_ffmpeg_filter_path(srt_path)}'
        if force_style:
            vf += f":force_style='{force_style}'"

        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', vf,
            '-c:a', 'copy',
            '-c:v', 'libx264',
            '-y',
            str(output_path)
        ]

        return self.run_ffmpeg_command(cmd)
    
    def try_ass_subtitles(self, video_path, srt_path, output_path):
        """ASSファイルを使用"""
        print("\n方法2: ASSファイル使用")
        
        # SRTをASSに変換
        ass_path = srt_path.with_suffix('.ass')
        self.convert_srt_to_ass(srt_path, ass_path)
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vf', f'ass={self.escape_ffmpeg_filter_path(ass_path)}',
            '-c:a', 'copy',
            '-y',
            str(output_path)
        ]

        result = self.run_ffmpeg_command(cmd)

        # 一時ASSファイル削除
        if ass_path.exists():
            ass_path.unlink()

        return result
    
    def try_external_subtitles(self, video_path, srt_path, output_path):
        """外部字幕として埋め込み"""
        print("\n方法3: 外部字幕として埋め込み")
        
        # 出力をMKVに変更
        mkv_output = output_path.with_suffix('.mkv')
        
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-i', str(srt_path),
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-c:s', 'srt',
            '-metadata:s:s:0', 'language=jpn',
            '-y',
            str(mkv_output)
        ]
        
        return self.run_ffmpeg_command(cmd)
    
    def convert_srt_to_ass(self, srt_path, ass_path):
        """SRTをASSに変換"""
        subs = pysrt.open(str(srt_path), encoding='utf-8')
        
        ass_content = """[Script Info]
Title: Converted from SRT
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,24,&H00ffffff,&H000000ff,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        for sub in subs:
            start = f"{sub.start.hours}:{sub.start.minutes:02d}:{sub.start.seconds:02d}.{sub.start.milliseconds//10:02d}"
            end = f"{sub.end.hours}:{sub.end.minutes:02d}:{sub.end.seconds:02d}.{sub.end.milliseconds//10:02d}"
            text = sub.text.replace('\n', '\\N')
            
            ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
        
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)
    
    def run_ffmpeg_command(self, cmd):
        """FFmpegコマンドを実行"""
        try:
            print(f"実行中: {' '.join(cmd[:6])}...")
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            print("✅ 成功")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ 失敗: {e.returncode}")
            if e.stderr:
                print(f"エラー: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ エラー: {e}")
            return False

def main():
    if len(sys.argv) != 4:
        print("使用法: python subtitle_adder.py video.mp4 subtitles.srt output.mp4")
        sys.exit(1)
    
    video_file = sys.argv[1]
    srt_file = sys.argv[2]
    output_file = sys.argv[3]
    
    adder = SubtitleAdder()
    result_path = adder.add_subtitles_to_video(video_file, srt_file, output_file)

    if result_path:
        print(f"\n🎉 完了: {result_path}")
    else:
        print("\n❌ 全ての方法が失敗しました")

if __name__ == "__main__":
    main()