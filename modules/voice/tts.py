import pyttsx3

class TextToSpeech:
    """Text-to-speech - creates fresh engine each call to avoid threading issues"""

    def speak(self, text: str):
        if not text:
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 175)
            engine.setProperty('volume', 0.9)
            engine.say(str(text))
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"TTS error: {e}")

    def stop(self):
        pass
