import threading
import pyttsx3

class TextToSpeech:
    """Text-to-speech - runs in background thread to avoid blocking/crashing UI"""

    def __init__(self):
        self.enabled = True

    def speak(self, text: str):
        if not text or not self.enabled:
            return
        threading.Thread(target=self._do_speak, args=(str(text),), daemon=True).start()

    def _do_speak(self, text: str):
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 175)
            engine.setProperty('volume', 0.9)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass

    def stop(self):
        pass
