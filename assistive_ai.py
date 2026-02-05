#!/usr/bin/env python3
"""
Accessibility Assistant for Visually Impaired Users
- Voice input (general AI assistant)
- Camera input (scene understanding + OCR)
- Follow-up questions about visible text or image
"""

import os
import sys
import time
from datetime import datetime
import speech_recognition as sr
import pyttsx3
from google import genai
from google.genai import types
import cv2
from PIL import Image
import io

IP_WEBCAM_URL = "http://192.168.18.4:8080/video"


class AccessibilityAssistant:
    def __init__(self, api_key):
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

        # Speech
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        # TTS
        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", 150)

        # Camera
        self.camera = cv2.VideoCapture(IP_WEBCAM_URL)
        if not self.camera.isOpened():
            self.camera = None

        # Memory from last image
        self.last_image_text = None
        self.last_image_summary = None
        self.last_image_objects = None

        self.is_running = True

        self.speak("Accessibility assistant ready. Press V for voice or C for camera.")

    # --------------------------------------------------
    def speak(self, text):
        print(f"[ASSISTANT]: {text}")
        self.tts.say(text)
        self.tts.runAndWait()

    # --------------------------------------------------
    def listen(self):
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=15)
        return self.recognizer.recognize_google(audio)

    # --------------------------------------------------
    def capture_image(self):
        if not self.camera:
            self.speak("Camera not available.")
            return None

        self.speak("Capturing image.")
        time.sleep(2)

        ret, frame = self.camera.read()
        if not ret:
            return None

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    # --------------------------------------------------
    def analyze_image(self, image):
        buf = io.BytesIO()
        image.save(buf, format="JPEG")

        prompt = (
            "You are assisting a visually impaired person.\n"
            "Do ALL of the following:\n"
            "1. List main visible objects\n"
            "2. Give a short scene summary\n"
            "3. Extract ALL readable text exactly as written\n\n"
            "FORMAT STRICTLY AS:\n"
            "OBJECTS:\n- ...\n\n"
            "SUMMARY:\n...\n\n"
            "TEXT:\n..."
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Content(parts=[
                    types.Part(text=prompt),
                    types.Part(inline_data=types.Blob(
                        mime_type="image/jpeg",
                        data=buf.getvalue()
                    ))
                ])
            ]
        )

        return response.text

    # --------------------------------------------------
    def process_camera_input(self):
        image = self.capture_image()
        if not image:
            self.speak("Failed to capture image.")
            return

        self.speak("Analyzing image.")
        analysis = self.analyze_image(image)

        objects = summary = text = ""

        if "TEXT:" in analysis:
            before, text = analysis.split("TEXT:", 1)
            if "SUMMARY:" in before:
                obj_part, summary = before.split("SUMMARY:", 1)
                objects = obj_part.replace("OBJECTS:", "").strip()
                summary = summary.strip()
            text = text.strip()

        self.last_image_objects = objects
        self.last_image_summary = summary
        self.last_image_text = text

        self.speak("Here is what I see.")
        if objects:
            self.speak(objects)
        if summary:
            self.speak(summary)

    # --------------------------------------------------
    def ask_from_image_text(self, question):
        prompt = (
            "Answer using ONLY the text below:\n\n"
            f"{self.last_image_text}\n\n"
            f"Question: {question}"
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        return response.text

    # --------------------------------------------------
    def ask_gemini(self, question):
        prompt = (
            "You are assisting a visually impaired person. "
            "Answer clearly and naturally.\n\n"
            f"Question: {question}"
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        return response.text

    # --------------------------------------------------
    def process_voice_input(self):
        try:
            self.speak("Listening.")
            text = self.listen()
            lower = text.lower()

            # OCR related
            if self.last_image_text and any(
                k in lower for k in ["read", "written", "text", "paragraph", "page", "line"]
            ):
                answer = self.ask_from_image_text(text)

            # Image related
            elif self.last_image_summary and any(
                k in lower for k in ["image", "picture", "see", "object"]
            ):
                answer = self.last_image_summary

            # General AI
            else:
                answer = self.ask_gemini(text)

            self.speak(answer)

        except Exception:
            self.speak("Sorry, I could not understand.")

    # --------------------------------------------------
    def run(self):
        import keyboard

        while self.is_running:
            if keyboard.is_pressed("v"):
                self.process_voice_input()
                time.sleep(1)

            elif keyboard.is_pressed("c"):
                self.process_camera_input()
                time.sleep(1)

            elif keyboard.is_pressed("q"):
                self.speak("Goodbye.")
                self.is_running = False

            time.sleep(0.1)


# ==================================================
def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = input("Enter Gemini API key: ").strip()

    assistant = AccessibilityAssistant(api_key)
    assistant.run()


if __name__ == "__main__":
    main()
