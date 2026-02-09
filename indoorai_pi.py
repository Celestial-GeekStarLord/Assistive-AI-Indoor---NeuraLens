#!/usr/bin/env python3
"""
Accessibility Assistant (USB Camera + Gemini + Voice)
Raspberry Pi 4 – Earphone Mic & Speaker Supported
Mute voice: press M (menu) or say "mute voice"
"""

import os
import sys
import time
import io
import cv2
import select
import speech_recognition as sr
import pyttsx3
from PIL import Image
from google import genai
from google.genai import types


# LOAD ENV

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass


class AccessibilityAssistant:
    def __init__(self, api_key):

        
        # GEMINI
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

        self.is_running = True
        self.voice_muted = False

        
        # TTS
        
        self.tts = pyttsx3.init(driverName="espeak")

        for v in self.tts.getProperty("voices"):
            if "en-us" in v.id.lower():
                self.tts.setProperty("voice", v.id)
                break

        self.tts.setProperty("rate", 165)

        
        # SPEECH RECOGNITION
        
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()

        
        # USB CAMERA
        
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not self.camera.isOpened():
            self.camera = None
            self.output("⚠ USB camera not available.")
        else:
            self.output("✅ USB camera connected.")

        self.output("Accessibility Assistant Ready.")
        self.output("V = voice | C = scene | B = read | M = mute | Q = quit")
        self.speak("Accessibility assistant is ready.")

    
    # CLEAN RESPONSE (REMOVE *)
    def clean_response(self, text):
        return text.replace("*", "")

   
    # VOICE OUTPUT
 
    def speak(self, text):
        if self.voice_muted:
            return
        text = self.clean_response(text)
        self.tts.say(text)
        self.tts.runAndWait()

    def toggle_mute(self):
        self.voice_muted = not self.voice_muted
        state = "muted" if self.voice_muted else "unmuted"
        self.output(f"🔇 Voice {state}")
        if not self.voice_muted:
            self.speak("Voice unmuted")

   
    # OUTPUT
   
    def output(self, text):
        text = self.clean_response(text)
        print("\n" + "=" * 60)
        print(text)
        print("=" * 60 + "\n")

  
    # CAPTURE IMAGE
  
    def capture_image(self):
        if self.camera is None:
            self.output("Camera not available.")
            return None

        time.sleep(0.5)
        for _ in range(8):
            self.camera.read()

        ret, frame = self.camera.read()
        if not ret:
            self.output("Failed to capture image.")
            return None

        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

   
    # VOICE INPUT
   
    def listen(self):
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            self.output("🎙 Listening...")
            audio = self.recognizer.listen(source)

        try:
            text = self.recognizer.recognize_google(audio).lower()
            self.output(f"🗣 You said: {text}")

            if "mute" in text:
                self.voice_muted = True
                self.output("🔇 Voice muted")
                return None

            if "unmute" in text:
                self.voice_muted = False
                self.speak("Voice unmuted")
                return None

            return text

        except:
            self.output("❌ Could not understand.")
            self.speak("Sorry, I did not understand.")
            return None

   
    # GEMINI
   
    def ask_gemini_text(self, text):
        prompt = (
            "You are assisting a visually impaired person. "
            "Answer clearly, briefly, and practically.\n"
            f"Question: {text}"
        )
        return self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        ).text

    def ask_gemini_image(self, image, mode):
        buf = io.BytesIO()
        image.save(buf, format="JPEG")

        prompts = {
            "scene": "List main visible objects and summarize briefly.",
            "read": "Read all visible text clearly.",
            "summarize": "Summarize text into short bullet points."
        }

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(
                    parts=[
                        types.Part(text=prompts[mode]),
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/jpeg",
                                data=buf.getvalue()
                            )
                        )
                    ]
                )
            ],
        )
        return response.text


    # MODES
    
    def run(self):
        while self.is_running:
            cmd = input("v / c / b / m / q: ").strip().lower()

            if cmd == "v":
                text = self.listen()
                if text:
                    ans = self.ask_gemini_text(text)
                    self.output(ans)
                    self.speak(ans)

            elif cmd == "c":
                img = self.capture_image()
                if img:
                    ans = self.ask_gemini_image(img, "scene")
                    self.output(ans)
                    self.speak(ans)

            elif cmd == "b":
                img = self.capture_image()
                if img:
                    ans = self.ask_gemini_image(img, "read")
                    self.output(ans)
                    self.speak(ans)

            elif cmd == "m":
                self.toggle_mute()

            elif cmd == "q":
                self.speak("Goodbye.")
                self.is_running = False

    def cleanup(self):
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()



# MAIN

def main():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key and os.path.exists("config.txt"):
        with open("config.txt") as f:
            api_key = f.read().strip()

    if not api_key:
        print("❌ GEMINI_API_KEY required.")
        sys.exit(1)

    assistant = AccessibilityAssistant(api_key)

    try:
        assistant.run()
    finally:
        assistant.cleanup()


if __name__ == "__main__":
    main()
