"""
EdgeTTSService: Native, high-quality, free AI Voiceover generation service.
Supports Vietnamese (Hoai My, Nam Minh) and international voices via Microsoft Edge TTS.
Does not require API keys or external Node.js dependencies.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable


AVAILABLE_VOICES = [
    {"id": "vi-VN-HoaiMyNeural", "name": "Tiếng Việt - Hoài My (Nữ, truyền cảm)", "gender": "Female", "locale": "vi-VN"},
    {"id": "vi-VN-NamMinhNeural", "name": "Tiếng Việt - Nam Minh (Nam, trầm ấm)", "gender": "Male", "locale": "vi-VN"},
    {"id": "en-US-JennyNeural", "name": "English - Jenny (Female, Natural)", "gender": "Female", "locale": "en-US"},
    {"id": "en-US-GuyNeural", "name": "English - Guy (Male, Natural)", "gender": "Male", "locale": "en-US"},
    {"id": "en-US-AriaNeural", "name": "English - Aria (Female, Expressive)", "gender": "Female", "locale": "en-US"},
]


class EdgeTTSService:
    """Service providing asynchronous and synchronous speech synthesis with edge-tts."""

    def __init__(self, default_voice: str = "vi-VN-HoaiMyNeural"):
        self.default_voice = default_voice

    @staticmethod
    def get_available_voices() -> List[Dict[str, str]]:
        return AVAILABLE_VOICES

    async def _synthesize_async(
        self,
        text: str,
        output_file: Path,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        output_srt: Optional[Path] = None,
    ) -> Tuple[bool, str]:
        """Asynchronously synthesizes speech using edge_tts and optionally exports SRT subtitles."""
        try:
            import edge_tts
        except ImportError:
            return False, "Thư viện edge-tts chưa được cài đặt. Chạy 'pip install edge-tts'."

        voice_id = voice or self.default_voice
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                rate=rate,
                pitch=pitch
            )

            if output_srt:
                output_srt = Path(output_srt)
                output_srt.parent.mkdir(parents=True, exist_ok=True)
                sub_maker = edge_tts.SubMaker()
                with open(output_file, "wb") as file:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            file.write(chunk["data"])
                        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                            sub_maker.feed(chunk)
                # Write SRT subtitle file
                output_srt.write_text(sub_maker.get_srt(), encoding="utf-8")
            else:
                await communicate.save(str(output_file))

            if output_file.exists() and output_file.stat().st_size > 100:
                return True, f"Tạo giọng thành công: {output_file.name}"
            return False, "File xuất rỗng hoặc không tồn tại."
        except Exception as e:
            return False, f"Lỗi sinh giọng đọc Edge TTS: {str(e)}"

    def synthesize(
        self,
        text: str,
        output_file: Path,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
        output_srt: Optional[Path] = None,
    ) -> Tuple[bool, str]:
        """Synchronous wrapper for synthesize_async."""
        text = text.strip()
        if not text:
            return False, "Nội dung văn bản rỗng."

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ok, msg = loop.run_until_complete(
                    self._synthesize_async(text, output_file, voice, rate, pitch, output_srt)
                )
                return ok, msg
            finally:
                loop.close()
        except Exception as e:
            return False, str(e)

    def batch_synthesize_txt_files(
        self,
        txt_files: List[Path],
        output_dir: Path,
        voice: Optional[str] = None,
        rate: str = "+0%",
        generate_subtitles: bool = True,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
        log_cb: Optional[Callable[[str], None]] = None,
        stop_cb: Optional[Callable[[], bool]] = None,
    ) -> Tuple[int, int, List[Path]]:
        """
        Synthesizes a list of TXT files sequentially into corresponding MP3 and SRT files.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Path] = []
        total = len(txt_files)
        success = 0

        for idx, txt_path in enumerate(txt_files, 1):
            if stop_cb and stop_cb():
                if log_cb:
                    log_cb("[DỪNG] Đã hủy tiến trình tạo giọng đọc theo yêu cầu.")
                break
            if not txt_path.exists():
                continue
            text = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue

            mp3_out = output_dir / f"{txt_path.stem}.mp3"
            srt_out = output_dir / f"{txt_path.stem}.srt" if generate_subtitles else None

            if log_cb:
                log_cb(f"[{idx}/{total}] Đang tạo giọng đọc cho: {txt_path.name}...")

            ok, msg = self.synthesize(text, mp3_out, voice=voice, rate=rate, output_srt=srt_out)
            if ok:
                success += 1
                results.append(mp3_out)
                if log_cb:
                    log_cb(f"  -> Hoàn thành: {mp3_out.name} ({mp3_out.stat().st_size // 1024} KB)")
            else:
                if log_cb:
                    log_cb(f"  -> Lỗi: {msg}")

            if progress_cb:
                progress_cb(idx, total, f"Đã tạo {idx}/{total} files")

        return success, total, results


# Alias for naming consistency
EdgeTtsService = EdgeTTSService
