import speech_recognition as sr
import threading
import winsound
from typing import Callable, Optional
from core.config import get_config

class VoiceRecognizer:
    """Voice recognition engine for vox"""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_recording = False
        self.on_result: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_recognition_failed: Optional[Callable[[str], None]] = None
        self._calibrating = False
        self._mic_busy = False  # True while _record thread holds the mic

        config = get_config()
        self.energy_threshold = config.get('voice', 'energy_threshold', default=300)
        self.pause_threshold = config.get('voice', 'pause_threshold', default=1.5)
        self.phrase_time_limit = config.get('voice', 'phrase_time_limit', default=60)
        self._calibrate()

    def _calibrate(self):
        """Calibrate microphone for ambient noise"""
        def calibrate():
            self._calibrating = True
            try:
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    self.recognizer.energy_threshold = self.energy_threshold
                    self.recognizer.pause_threshold = self.pause_threshold
                print("Microphone calibrated")
            except Exception as e:
                print(f"Microphone calibration failed: {e}")
            finally:
                self._calibrating = False

        threading.Thread(target=calibrate, daemon=True).start()

    def start_recording(self):
        """Start voice recording"""
        if self.is_recording or self._calibrating or self._mic_busy:
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
        self._mic_busy = True
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=2,
                    phrase_time_limit=self.phrase_time_limit
                )

            self._mic_busy = False
            self._transcribe(audio)

        except sr.WaitTimeoutError:
            self._mic_busy = False
            self._notify_status("No speech detected")
            if self.on_recognition_failed:
                self.on_recognition_failed("No speech detected")
            self.is_recording = False
        except Exception as e:
            self._mic_busy = False
            self._notify_error(f"Recording error: {e}")
            if self.on_recognition_failed:
                self.on_recognition_failed("Recording error")
            self.is_recording = False

    def _transcribe(self, audio):
        """Transcribe audio to text via Google STT"""
        try:
            text = self.recognizer.recognize_google(audio)
            self._notify_status("Recognized")
            if self.on_result:
                self.on_result(text)
        except sr.UnknownValueError:
            self._notify_status("Didn't catch that")
            if self.on_recognition_failed:
                self.on_recognition_failed("Didn't catch that")
        except sr.RequestError as e:
            self._notify_error(f"Google API error: {e}")
            if self.on_recognition_failed:
                self.on_recognition_failed("API error")
        self.is_recording = False

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
