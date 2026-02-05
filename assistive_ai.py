#!/usr/bin/env python3
"""
Accessibility Assistant for Visually Impaired Users
Production-ready version with voice control, camera capture, and OCR book reading
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

# IP Webcam Configuration
IP_WEBCAM_URL = "http://192.168.18.4:8080/video"

# Try to load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class AccessibilityAssistant:
    def __init__(self, api_key):
        """Initialize the accessibility assistant"""
        # Configure Gemini API
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.5-flash'
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize text-to-speech
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)
        self.tts_engine.setProperty('volume', 1.0)
        
        # Voice control state
        self.voice_enabled = True
        
        # Initialize camera
        self.camera = None
        try:
            self.camera = cv2.VideoCapture(IP_WEBCAM_URL)
            if not self.camera.isOpened():
                self.speak("Warning: Camera is not available. Voice mode will still work.")
                self.camera = None
        except Exception as e:
            self.speak("Camera not available. Voice mode will still work.")
        
        # Application state
        self.is_running = True
        
        self.speak("Accessibility Assistant is ready.")
        self.speak("Press V for voice questions, C for scene description, B for book reading, or Q to quit.")
        self.speak("Press Control plus M anytime to mute or unmute voice output.")
    
    def speak(self, text):
        """Convert text to speech"""
        print(f"{text}")
        if self.voice_enabled:
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                print(f"[Error in speech synthesis: {e}]")
    
    def toggle_voice(self):
        """Toggle voice output on/off"""
        self.voice_enabled = not self.voice_enabled
        status = "enabled" if self.voice_enabled else "disabled"
        print(f"[Voice output {status}]")
        if self.voice_enabled:
            self.speak(f"Voice output {status}")
    
    def listen_for_voice(self):
        """Listen for voice input and convert to text"""
        self.speak("Listening... Please speak now.")
        
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            try:
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=15)
                self.speak("Processing your speech...")
                
                text = self.recognizer.recognize_google(audio)
                self.speak(f"You said: {text}")
                
                return text
                
            except sr.WaitTimeoutError:
                self.speak("No speech detected. Please try again.")
                return None
            except sr.UnknownValueError:
                self.speak("Sorry, I couldn't understand what you said. Please try again.")
                return None
            except sr.RequestError:
                self.speak("Speech recognition service error. Please try again.")
                return None
    
    def capture_image(self):
        """Capture image from camera"""
        if self.camera is None:
            self.speak("Camera is not available.")
            return None
            
        self.speak("Capturing image in 3, 2, 1...")
        time.sleep(2)
        
        ret, frame = self.camera.read()
        
        if not ret:
            self.speak("Failed to capture image from camera.")
            return None
        
        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"captured_image_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        
        self.speak("Image captured successfully.")
        
        # Convert to PIL Image
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img_rgb)
        
        return pil_image, filename
    
    def send_text_to_gemini(self, text):
        """Send text query to Gemini and get response"""
        try:
            self.speak("Processing your question...")
            
            prompt = f"You are assisting a visually impaired person. Please provide clear, concise, and helpful responses to their question. User query: {text}"
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            return response.text
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def send_image_to_gemini(self, image, context=None):
        """Send image to Gemini for scene description"""
        try:
            self.speak("Analyzing the scene...")
            
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=95)
            img_byte_arr = img_byte_arr.getvalue()
            
            # Create prompt
            if context:
                prompt = (
                    "You are assisting a visually impaired person. "
                    "List the main visible objects and give a brief summary. "
                    f"Focus on: {context}. "
                    "Respond in one short paragraph."
                )
            else:
                prompt = (
                    "You are assisting a visually impaired person. "
                    "List the main visible objects and give a short description of the scene. "
                    "Be concise and clear. Respond in one short paragraph."
                )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(text=prompt),
                            types.Part(inline_data=types.Blob(
                                mime_type='image/jpeg',
                                data=img_byte_arr
                            ))
                        ]
                    )
                ]
            )
            
            return response.text
            
        except Exception as e:
            return f"Error analyzing image: {str(e)}"
    
    def extract_and_process_text_from_image(self, image, mode="read"):
        """Extract text from image using Gemini's OCR"""
        try:
            self.speak("Reading text from the image...")
            
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=95)
            img_byte_arr = img_byte_arr.getvalue()
            
            # Create prompt based on mode
            if mode == "read":
                prompt = (
                    "This is an accessibility tool for visually impaired users. "
                    "Read all the text visible in this image and convey the complete information to the user. "
                    "IMPORTANT: Do NOT copy text verbatim. Instead, rephrase and restructure every sentence in your own words. "
                    "Preserve ALL details including: names, numbers, dates, places, specific facts, concepts, and context. "
                    "Do NOT skip any information. "
                    "Do NOT describe the layout, format, page numbers, or document structure. "
                    "Simply communicate what the text says by rephrasing it completely. "
                    "Make sure every piece of information from the page is conveyed, just expressed differently."
                )
            elif mode == "summarize":
                prompt = (
                    "This is an accessibility tool for visually impaired users. "
                    "Read the text in this image and provide a concise summary. "
                    "Format your response as bullet points covering: "
                    "• Main topic or subject "
                    "• Key points and important details "
                    "• Any significant names, dates, or numbers mentioned "
                    "• Main conclusions or takeaways "
                    "Keep it brief but informative. Do NOT describe layout or format."
                )
            else:
                prompt = (
                    "This is an accessibility tool for visually impaired users. "
                    "Read all the text visible in this image and convey the complete information to the user. "
                    "IMPORTANT: Do NOT copy text verbatim. Instead, rephrase and restructure every sentence in your own words. "
                    "Preserve ALL details including: names, numbers, dates, places, specific facts, concepts, and context. "
                    "Do NOT skip any information. "
                    "Do NOT describe the layout, format, page numbers, or document structure. "
                    "Simply communicate what the text says by rephrasing it completely. "
                    "Make sure every piece of information from the page is conveyed, just expressed differently."
                )
            
            # Send to Gemini
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Content(
                        parts=[
                            types.Part(text=prompt),
                            types.Part(inline_data=types.Blob(
                                mime_type='image/jpeg',
                                data=img_byte_arr
                            ))
                        ]
                    )
                ]
            )
            
            # Check for recitation block
            if response.candidates and len(response.candidates) > 0:
                finish_reason = response.candidates[0].finish_reason
                
                if finish_reason.name == 'RECITATION':
                    # Retry with alternative prompt focusing on paraphrasing
                    alternative_prompt = (
                        "As an accessibility assistant for visually impaired users, "
                        "read this page and explain what it communicates using completely different words. "
                        "Paraphrase every sentence. Keep all important details like names, numbers, and facts. "
                        "Do NOT copy any phrases. Restructure the information entirely. "
                        "What is this page telling the reader? Explain it in your own way."
                    )
                    
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[
                            types.Content(
                                parts=[
                                    types.Part(text=alternative_prompt),
                                    types.Part(inline_data=types.Blob(
                                        mime_type='image/jpeg',
                                        data=img_byte_arr
                                    ))
                                ]
                            )
                        ]
                    )
            
            # Extract response text
            if hasattr(response, 'text') and response.text:
                response_text = response.text
            elif response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts'):
                    response_text = ' '.join([part.text for part in candidate.content.parts if hasattr(part, 'text')])
                else:
                    response_text = "Unable to extract text. The content may be blocked due to copyright protection."
            else:
                response_text = "No response received."
            
            if not response_text or response_text.strip() == "":
                response_text = "I could not detect any readable text in this image. Please ensure the page is well-lit, in focus, and clearly visible."
            
            return response_text
            
        except Exception as e:
            return f"Error extracting text: {str(e)}"
    
    def process_voice_input(self):
        """Process voice questions - answers any question"""
        text = self.listen_for_voice()
        
        if text:
            response = self.send_text_to_gemini(text)
            print(f"\n{response}\n")
            # Speak the response out loud
            self.speak(response)
    
    def process_camera_input(self):
        """Process camera input for scene description"""
        if self.camera is None:
            self.speak("Camera is not available. Please check your camera connection.")
            return
        
        self.speak("Do you want to provide context for the image? Say yes or no.")
        
        context_input = self.listen_for_voice()
        context = None
        
        if context_input and "yes" in context_input.lower():
            self.speak("Please describe what you want me to focus on in the image.")
            context = self.listen_for_voice()
        
        result = self.capture_image()
        
        if result:
            image, filename = result
            response = self.send_image_to_gemini(image, context)
            print(f"\n{response}\n")
            # Speak the response out loud
            self.speak(response)
    
    def process_book_reading(self):
        """Process book reading with OCR"""
        if self.camera is None:
            self.speak("Camera is not available. Please check your camera connection.")
            return
        
        self.speak("Do you want me to read the full text, or summarize it? Say read or summarize. If you say nothing, I will read the full text.")
        
        mode_input = self.listen_for_voice()
        mode = "read"
        
        if mode_input:
            if "summarize" in mode_input.lower() or "summary" in mode_input.lower() or "brief" in mode_input.lower():
                mode = "summarize"
                self.speak("I will summarize the text for you.")
            elif "read" in mode_input.lower():
                mode = "read"
                self.speak("I will read the full text for you.")
            else:
                self.speak("I didn't understand. I will read the full text by default.")
        else:
            self.speak("No input detected. I will read the full text by default.")
        
        result = self.capture_image()
        
        if result:
            image, filename = result
            response = self.extract_and_process_text_from_image(image, mode)
            print(f"\n{response}\n")
            # Speak the response out loud
            self.speak(response)
    
    def run(self):
        """Main application loop"""
        print("\n" + "="*60)
        print("ACCESSIBILITY ASSISTANT - CONTROLS")
        print("="*60)
        print("V - Voice Questions (Ask anything)")
        print("C - Camera Scene Description")
        print("B - Book Reading (OCR)")
        print("Ctrl+M - Mute/Unmute Voice")
        print("Q - Quit Application")
        print("="*60 + "\n")
        
        try:
            import keyboard
            
            # Register Ctrl+M hotkey for voice toggle
            keyboard.add_hotkey('ctrl+m', self.toggle_voice)
            
            while self.is_running:
                if keyboard.is_pressed('v') and not keyboard.is_pressed('ctrl'):
                    print("\n[VOICE MODE - Ask Any Question]")
                    self.process_voice_input()
                    time.sleep(1)
                
                elif keyboard.is_pressed('c'):
                    print("\n[CAMERA MODE - Scene Description]")
                    self.process_camera_input()
                    time.sleep(1)
                
                elif keyboard.is_pressed('b'):
                    print("\n[BOOK READING MODE - OCR]")
                    self.process_book_reading()
                    time.sleep(1)
                
                elif keyboard.is_pressed('q'):
                    print("\n[SHUTTING DOWN]")
                    self.speak("Goodbye! Shutting down the Accessibility Assistant.")
                    self.is_running = False
                
                time.sleep(0.1)
        
        except ImportError:
            print("Warning: 'keyboard' module not available. Using alternative input method.")
            self.run_alternative_input()
    
    def run_alternative_input(self):
        """Alternative input method if keyboard module is not available"""
        print("\nUsing text-based input method.")
        
        while self.is_running:
            print("\n" + "="*60)
            print("Enter command:")
            print("  v - Voice Questions (Ask anything)")
            print("  c - Camera Scene Description")
            print("  b - Book Reading (OCR)")
            print("  m - Mute/Unmute Voice")
            print("  q - Quit")
            print("="*60)
            
            command = input("\nYour choice: ").lower().strip()
            
            if command == 'v':
                print("\n[VOICE MODE - Ask Any Question]")
                self.process_voice_input()
            
            elif command == 'c':
                print("\n[CAMERA MODE - Scene Description]")
                self.process_camera_input()
            
            elif command == 'b':
                print("\n[BOOK READING MODE - OCR]")
                self.process_book_reading()
            
            elif command == 'm':
                self.toggle_voice()
            
            elif command == 'q':
                print("\n[SHUTTING DOWN]")
                self.speak("Goodbye! Shutting down the Accessibility Assistant.")
                self.is_running = False
            
            else:
                print("Invalid command. Please try again.")
    
    def cleanup(self):
        """Clean up resources"""
        if self.camera is not None and self.camera.isOpened():
            self.camera.release()
        cv2.destroyAllWindows()


def main():
    """Main function to run the application"""
    print("\n" + "="*60)
    print("ACCESSIBILITY ASSISTANT FOR VISUALLY IMPAIRED")
    print("="*60 + "\n")
    
    # Load API key from config.txt
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        config_file = os.path.join(os.path.dirname(__file__), 'config.txt')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    api_key = f.read().strip()
                    print("✓ API key loaded from config.txt")
            except Exception as e:
                print(f"Error reading config.txt: {e}")
    
    if not api_key:
        print("\n" + "="*60)
        print("GEMINI API KEY SETUP")
        print("="*60)
        print("\nAPI key not found. Please provide your Gemini API key.")
        print("\nTo get an API key:")
        print("1. Visit: https://makersuite.google.com/app/apikey")
        print("2. Sign in with Google account")
        print("3. Click 'Create API Key'")
        print("4. Copy the key\n")
        
        api_key = input("Enter your Gemini API key: ").strip()
        
        if api_key:
            save_choice = input("\nDo you want to save this key to config.txt for future use? (yes/no): ").lower().strip()
            if save_choice in ['yes', 'y']:
                try:
                    config_file = os.path.join(os.path.dirname(__file__), 'config.txt')
                    with open(config_file, 'w') as f:
                        f.write(api_key)
                    print(f"✓ API key saved to {config_file}")
                except Exception as e:
                    print(f"Could not save API key: {e}")
    
    if not api_key:
        print("\n" + "="*60)
        print("ERROR: API key is required to run this application.")
        print("="*60)
        sys.exit(1)
    
    try:
        assistant = AccessibilityAssistant(api_key)
        assistant.run()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'assistant' in locals():
            assistant.cleanup()
        print("\nApplication terminated.")


if __name__ == "__main__":
    main()