#!/usr/bin/env python3
import os, sys, time, io, cv2, signal
import speech_recognition as sr
import pyttsx3
import RPi.GPIO as GPIO
from PIL import Image
from google import genai
from google.genai import types

# ================= GPIO =================
BTN_MAIN = 17
BTN_BACK = 27
HOLD_TIME = 1.2

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(BTN_MAIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BTN_BACK, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def wait_press(pin):
    while GPIO.input(pin) == GPIO.LOW:
        time.sleep(0.01)
    start=time.time()
    while GPIO.input(pin)==GPIO.HIGH:
        time.sleep(0.01)
    return "hold" if time.time()-start>HOLD_TIME else "tap"


class AccessibilityAssistant:
    def __init__(self, api_key):

        # ===== Gemini =====
        self.client = genai.Client(api_key=api_key)
        self.model_name="gemini-2.5-flash"

        self.tts=pyttsx3.init(driverName="espeak")
        self.tts.setProperty("rate",165)

        # ===== Mic =====
        self.recognizer=sr.Recognizer()
        self.mic=sr.Microphone()

        # ===== Camera =====
        self.camera=cv2.VideoCapture(0)
        if not self.camera.isOpened():
            self.camera=None
            self.speak("Camera not available")
        else:
            self.speak("Camera ready")

        # modes
        self.modes=["voice","capture","book"]
        self.mode_index=0

        self.speak("Assistant ready")
        self.announce_mode()

    # ---------- SPEECH ----------
    def speak(self,text):
        print(text)
        self.tts.say(text)
        self.tts.runAndWait()

    def announce_mode(self):
        self.speak(self.modes[self.mode_index]+" mode")

    # ---------- GEMINI ----------
    def ask_text(self,q):
        prompt="Assist a visually impaired person briefly.\n"+q
        return self.client.models.generate_content(
            model=self.model_name,contents=prompt).text

    def ask_image(self,img,mode):
        buf=io.BytesIO()
        img.save(buf,format="JPEG")
        prompts={
            "capture":"List objects briefly.",
            "book":"Read all visible text."
        }
        r=self.client.models.generate_content(
            model=self.model_name,
            contents=[types.Content(parts=[
                types.Part(text=prompts[mode]),
                types.Part(inline_data=types.Blob(
                    mime_type="image/jpeg",data=buf.getvalue()))
            ])])
        return r.text

    # ---------- LISTEN ----------
    def listen(self):
        try:
            with self.mic as src:
                self.speak("Listening")
                audio=self.recognizer.listen(src,timeout=15,phrase_time_limit=15)
            return self.recognizer.recognize_google(audio).lower()
        except:
            self.speak("Sorry I did not understand")
            return None

    # ---------- CAMERA ----------
    def capture(self):
        if not self.camera: return None
        for _ in range(5): self.camera.read()
        ok,frame=self.camera.read()
        if not ok: return None
        return Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))

    # ---------- RUN LOOP ----------
    def run(self):

        while True:

            # BACK button quits program
            if GPIO.input(BTN_BACK)==GPIO.HIGH:
                wait_press(BTN_BACK)
                self.speak("Exiting assistant")
                break

            # MAIN button
            if GPIO.input(BTN_MAIN)==GPIO.HIGH:
                action=wait_press(BTN_MAIN)

                # TAP → change mode
                if action=="tap":
                    self.mode_index=(self.mode_index+1)%3
                    self.announce_mode()

                # HOLD → run selected mode
                else:
                    mode=self.modes[self.mode_index]

                    if mode=="voice":
                        text=self.listen()
                        if text:
                            ans=self.ask_text(text)
                            self.speak(ans)

                    elif mode=="capture":
                        img=self.capture()
                        if img:
                            ans=self.ask_image(img,"capture")
                            self.speak(ans)

                    elif mode=="book":
                        img=self.capture()
                        if img:
                            ans=self.ask_image(img,"book")
                            self.speak(ans)

            time.sleep(0.05)

    def cleanup(self):
        if self.camera: self.camera.release()
        GPIO.cleanup()


# ===== MAIN =====
def main():
    api=os.getenv("GEMINI_API_KEY")
    if not api and os.path.exists("config.txt"):
        api=open("config.txt").read().strip()
    if not api:
        print("API key missing");sys.exit(1)

    a=AccessibilityAssistant(api)
    try:
        a.run()
    finally:
        a.cleanup()

if __name__=="__main__":
    main()