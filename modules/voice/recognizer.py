import speech_recognition as sr
import threading
import winsound
import json
import os
import wave
import io
from typing import Callable, Optional
from core.config import get_config

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

class VoiceRecognizer:
    """Voice recognition engine for vox"""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_recording = False
        self.on_result: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None

        config = get_config()
        self.energy_threshold = config.get('voice', 'energy_threshold', default=300)
        self.pause_threshold = config.get('voice', 'pause_threshold', default=1.5)
        self.phrase_time_limit = config.get('voice', 'phrase_time_limit', default=60)
        self.vosk_confidence_threshold = config.get('voice', 'vosk_confidence_threshold', default=0.7)

        self.vosk_model = None
        self._init_vosk()
        self._calibrate()

    def _calibrate(self):
        """Calibrate microphone for ambient noise"""
        def calibrate():
            try:
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    self.recognizer.energy_threshold = self.energy_threshold
                    self.recognizer.pause_threshold = self.pause_threshold
                print("Microphone calibrated")
            except Exception as e:
                print(f"Microphone calibration failed: {e}")

        threading.Thread(target=calibrate, daemon=True).start()

    def _init_vosk(self):
        """Initialize Vosk model for fallback recognition"""
        if not VOSK_AVAILABLE:
            print("Vosk not installed, fallback disabled")
            return

        model_path = os.path.expanduser("~/.vox/models/vosk-model-small-en-us-0.15")
        if os.path.exists(model_path):
            try:
                self.vosk_model = Model(model_path)
                print("Vosk model loaded")
            except Exception as e:
                print(f"Vosk init failed: {e}")
        else:
            print(f"Vosk model not found at {model_path}")
            print("Download from: https://alphacephei.com/vosk/models")

    def start_recording(self):
        """Start voice recording"""
        if self.is_recording:
            return

        self.is_recording = True
        self._play_beep("start")
        self._notify_status("Listening...")

        thread = threading.Thread(target=self._record, daemon=True)
        thread.start()

    def stop_recording(self):
        """Stop voice recording"""
        self.is_recording = False
        self._play_beep("stop")

    def toggle_recording(self):
        """Toggle recording state"""
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _record(self):
        """Record and transcribe audio"""
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=2,
                    phrase_time_limit=self.phrase_time_limit
                )

            self._transcribe(audio)

        except sr.WaitTimeoutError:
            self._notify_status("No speech detected")
            self.is_recording = False
        except Exception as e:
            self._notify_error(f"Recording error: {e}")
            self.is_recording = False

    def _transcribe(self, audio):
        """Transcribe audio to text with Vosk fallback"""
        # Try Google first
        try:
            text = self.recognizer.recognize_google(audio)
            self._notify_status("Recognized")
            if self.on_result:
                self.on_result(text)
            self.is_recording = False
            return
        except sr.UnknownValueError:
            pass  # Fall through to Vosk
        except sr.RequestError as e:
            self._notify_error(f"Google API error: {e}")

        # Fallback to Vosk with word confidence
        if self.vosk_model:
            text = self._transcribe_vosk(audio)
            if text and text.strip():
                self._notify_status("Recognized (partial)")
                if self.on_result:
                    self.on_result(text)
                self.is_recording = False
                return

        self._notify_status("Could not understand audio")
        self.is_recording = False

    def _transcribe_vosk(self, audio):
        """Transcribe using Vosk with word-level confidence"""
        try:
            # Convert audio to WAV format for Vosk
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)

            rec = KaldiRecognizer(self.vosk_model, 16000)
            rec.SetWords(True)  # Enable word-level results

            # Process audio
            rec.AcceptWaveform(wav_data)
            result = json.loads(rec.FinalResult())

            if 'result' not in result:
                return result.get('text', '')

            # Build text with blanks for low-confidence words
            words = []
            for word_info in result['result']:
                conf = word_info.get('conf', 0)
                word = word_info.get('word', '')
                if conf >= self.vosk_confidence_threshold:
                    words.append(word)
                else:
                    words.append('___')

            return ' '.join(words)
        except Exception as e:
            print(f"Vosk transcription error: {e}")
            return None

    def _play_beep(self, beep_type: str):
        """Play audio feedback"""
        try:
            if beep_type == "start":
                winsound.Beep(600, 150)
            elif beep_type == "stop":
                winsound.Beep(400, 200)
        except:
            pass

    def _notify_status(self, message: str):
        if self.on_status:
            self.on_status(message)

    def _notify_error(self, message: str):
        if self.on_error:
            self.on_error(message)
        print(message)
