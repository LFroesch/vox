"""Wake word detection using vosk — listens for 'hey vox' to trigger recording."""

import json
import threading
import time
from typing import Callable, Optional
from pathlib import Path


class WakeWordListener:
    """Background listener that detects 'hey vox' via vosk keyword spotting."""

    SAMPLE_RATE = 16000
    CHUNK_SIZE = 4000  # 250ms at 16kHz

    STARTUP_GRACE = 7  # seconds to ignore wake words after start

    def __init__(self, on_wake: Optional[Callable] = None):
        self.on_wake = on_wake
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._stream = None
        self._pa = None
        self._start_time: float = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._paused = False
        self._start_time = time.monotonic()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._paused = False

    def pause(self):
        self._paused = True
        self._close_stream()

    def resume(self):
        self._paused = False

    @property
    def is_active(self) -> bool:
        return self._running and not self._paused

    def _listen_loop(self):
        try:
            import vosk
            import pyaudio
        except ImportError as e:
            print(f"Wake word dependencies not available: {e}")
            self._running = False
            return

        # Find model
        model_path = self._find_model()
        if not model_path:
            print("Vosk model not found. Download vosk-model-small-en-us-0.15 to data/models/vosk/")
            self._running = False
            return

        vosk.SetLogLevel(-1)  # Suppress vosk logs
        model = vosk.Model(str(model_path))
        # Grammar restricts recognition to just our wake phrase + filler
        rec = vosk.KaldiRecognizer(model, self.SAMPLE_RATE,
                                    json.dumps(["hey vox", "[unk]"]))

        self._pa = pyaudio.PyAudio()

        while self._running:
            if self._paused:
                self._close_stream()
                time.sleep(0.1)
                continue

            if self._stream is None:
                try:
                    self._stream = self._pa.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=self.SAMPLE_RATE,
                        input=True,
                        frames_per_buffer=self.CHUNK_SIZE,
                    )
                except Exception as e:
                    print(f"Wake word mic error: {e}")
                    time.sleep(1)
                    continue

            try:
                data = self._stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")
                    if "hey vox" in text:
                        in_grace = (time.monotonic() - self._start_time) < self.STARTUP_GRACE
                        if self.on_wake and not self._paused and not in_grace:
                            self.on_wake()
            except Exception as e:
                print(f"Wake word audio error: {e}")
                self._close_stream()
                time.sleep(0.5)

        self._close_stream()
        if self._pa:
            self._pa.terminate()
            self._pa = None

    def _close_stream(self):
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _find_model(self) -> Optional[Path]:
        """Look for a vosk model directory."""
        import sys

        candidates = [
            Path(__file__).parent.parent.parent / "data" / "models" / "vosk",
            Path.home() / ".vox" / "models" / "vosk",
        ]
        if getattr(sys, 'frozen', False):
            candidates.insert(0, Path(sys._MEIPASS) / "data" / "models" / "vosk")

        for p in candidates:
            if p.exists() and (p / "conf" / "model.conf").exists():
                return p
        return None
