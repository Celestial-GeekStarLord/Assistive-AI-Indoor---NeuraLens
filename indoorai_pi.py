#!/usr/bin/env python3
import os, sys, time, io, cv2, signal, subprocess
import speech_recognition as sr
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
    start = time.time()
    while GPIO.input(pin) == GPIO.HIGH:
        time.sleep(0.01)
    return "hold" if time.time() - start > HOLD_TIME else "tap"

# ================= SPEECH =================
speech_process = None
interrupt_flag = False

def speak(text):
    """Speak using espeak with interruption support"""
    global speech_process, interrupt_flag
    
    print(text)
    interrupt_flag = False
    
    # Stop any ongoing speech
    stop_speech()
    
    try:
        # Split into sentences for better interruption
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        for sentence in sentences:
            if interrupt_flag or GPIO.input(BTN_BACK) == GPIO.HIGH:
                interrupt_flag = True
                break
            
            speech_process = subprocess.Popen(
                ['espeak', '-a', '200', '-s', '165', sentence, '--stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            aplay_process = subprocess.Popen(
                ['aplay'],
                stdin=speech_process.stdout,
                stderr=subprocess.DEVNULL
            )
            
            speech_process.stdout.close()
            
            # Wait with interruption check
            while aplay_process.poll() is None:
                if GPIO.input(BTN_BACK) == GPIO.HIGH:
                    interrupt_flag = True
                    aplay_process.kill()
                    speech_process.kill()
                    time.sleep(0.3)
                    return False
                time.sleep(0.05)
            
            if len(sentences) > 1:
                time.sleep(0.15)
        
        speech_process = None
        return not interrupt_flag
        
    except Exception as e:
        print(f"Speech error: {e}")
        speech_process = None
        return False

def stop_speech():
    """Stop ongoing speech"""
    global speech_process
    if speech_process is not None:
        try:
            speech_process.kill()
            speech_process.wait()
        except:
            pass
        speech_process = None


class AccessibilityAssistant:
    def __init__(self, api_key):

        # ===== Gemini =====
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

        # ===== Mic =====
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()

        # ===== Camera =====
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            self.camera = None
            speak("Camera not available")
        else:
            speak("Camera ready")

        # modes
        self.modes = ["voice", "capture", "book"]
        self.mode_index = 0

        speak("Assistant ready")
        self.announce_mode()

    # ---------- SPEECH ----------
    def announce_mode(self):
        speak(self.modes[self.mode_index] + " mode")

    # ---------- GEMINI ----------
    def ask_text(self, q):
        prompt = "Assist a visually impaired person briefly.\n" + q
        return self.client.models.generate_content(
            model=self.model_name, contents=prompt).text

    def ask_image(self, img, mode):
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        prompts = {
            "capture": "List objects briefly.",
            "book": "Read all visible text."
        }
        r = self.client.models.generate_content(
            model=self.model_name,
            contents=[types.Content(parts=[
                types.Part(text=prompts[mode]),
                types.Part(inline_data=types.Blob(
                    mime_type="image/jpeg", data=buf.getvalue()))
            ])])
        return r.text

    # ---------- LISTEN ----------
    def listen(self):
        global interrupt_flag
        interrupt_flag = False
        
        try:
            with self.mic as src:
                speak("Listening")
                if interrupt_flag:
                    return None
                audio = self.recognizer.listen(src, timeout=15, phrase_time_limit=15)
            
            if interrupt_flag:
                return None
                
            return self.recognizer.recognize_google(audio).lower()
        except:
            if not interrupt_flag:
                speak("Sorry I did not understand")
            return None

    # ---------- CAMERA ----------
    def capture(self):
        if not self.camera: 
            return None
        for _ in range(5): 
            self.camera.read()
        ok, frame = self.camera.read()
        if not ok: 
            return None
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    # ---------- RUN LOOP ----------
    def run(self):
        global interrupt_flag

        while True:

            # BACK button quits program
            if GPIO.input(BTN_BACK) == GPIO.HIGH:
                wait_press(BTN_BACK)
                speak("Exiting assistant")
                break

            # MAIN button
            if GPIO.input(BTN_MAIN) == GPIO.HIGH:
                action = wait_press(BTN_MAIN)
                interrupt_flag = False

                # TAP → change mode
                if action == "tap":
                    self.mode_index = (self.mode_index + 1) % 3
                    self.announce_mode()

                # HOLD → run selected mode
                else:
                    mode = self.modes[self.mode_index]

                    if mode == "voice":
                        text = self.listen()
                        if text and not interrupt_flag:
                            ans = self.ask_text(text)
                            speak(ans)

                    elif mode == "capture":
                        img = self.capture()
                        if img and not interrupt_flag:
                            ans = self.ask_image(img, "capture")
                            speak(ans)

                    elif mode == "book":
                        img = self.capture()
                        if img and not interrupt_flag:
                            ans = self.ask_image(img, "book")
                            speak(ans)

            time.sleep(0.05)

    def cleanup(self):
        stop_speech()
        if self.camera: 
            self.camera.release()
        GPIO.cleanup()


# ===== MAIN =====
def main():
    api = os.getenv("GEMINI_API_KEY")
    if not api and os.path.exists("config.txt"):
        api = open("config.txt").read().strip()
    if not api:
        print("API key missing")
        sys.exit(1)

    a = AccessibilityAssistant(api)
    try:
        a.run()
    finally:
        a.cleanup()

if __name__ == "__main__":
    main()
