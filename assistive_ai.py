#!/usr/bin/env python3
"""
Accessibility Assistant for Visually Impaired Users
Supports voice input, camera capture, and OCR book reading with Gemini AI integration
"""

import os
import sys
import threading
import queue
import time
from datetime import datetime
import speech_recognition as sr
import pyttsx3
# Using the new google.genai package (replaces deprecated google.generativeai)
from google import genai
from google.genai import types
import cv2
from PIL import Image
import io
IP_WEBCAM_URL = "http://192.168.18.4:8080/video"

# Try to load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env support is optional

class AccessibilityAssistant:
    def __init__(self, api_key):
        """Initialize the accessibility assistant"""
        # Configure Gemini API with new package
        self.client = genai.Client(api_key=api_key)
        # Use gemini-2.5-flash - latest and most capable model
        self.model_name = 'gemini-2.5-flash'
        
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Initialize text-to-speech
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)  # Speed of speech
        self.tts_engine.setProperty('volume', 1.0)  # Volume (0.0 to 1.0)
        
        # Initialize camera with error handling
        self.camera = None
        try:
            self.camera = cv2.VideoCapture(IP_WEBCAM_URL)
            if not self.camera.isOpened():
                print("Warning: Camera not available")
                self.speak("Warning: Camera is not available. Voice mode will still work.")
                self.camera = None
        except Exception as e:
            print(f"Camera initialization error: {e}")
            self.speak("Camera not available. Voice mode will still work.")
        
        # Queue for responses
        self.response_queue = queue.Queue()
        
        # State
        self.is_running = True
        self.listening = False
        
        print("Accessibility Assistant initialized successfully!")
        self.speak("Accessibility Assistant is ready. Press V for voice questions, C for scene description, B for book reading, or Q to quit.")
    
    def speak(self, text):
        """Convert text to speech"""
        print(f"[ASSISTANT]: {text}")
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            print(f"Error in text-to-speech: {e}")
    
    def listen_for_voice(self):
        """Listen for voice input and convert to text"""
        self.speak("Listening... Please speak now.")
        
        with self.microphone as source:
            # Adjust for ambient noise
            print("Adjusting for ambient noise... Please wait.")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            try:
                print("Listening...")
                # Listen for audio input (timeout after 5 seconds of silence)
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=15)
                
                print("Processing speech...")
                self.speak("Processing your speech...")
                
                # Convert speech to text using Google Speech Recognition
                text = self.recognizer.recognize_google(audio)
                print(f"[YOU SAID]: {text}")
                self.speak(f"You said: {text}")
                
                return text
                
            except sr.WaitTimeoutError:
                self.speak("No speech detected. Please try again.")
                return None
            except sr.UnknownValueError:
                self.speak("Sorry, I couldn't understand what you said. Please try again.")
                return None
            except sr.RequestError as e:
                self.speak("Sorry, there was an error with the speech recognition service.")
                print(f"Error: {e}")
                return None
    
    def capture_image(self):
        """Capture image from camera"""
        if self.camera is None:
            self.speak("Camera is not available.")
            return None
            
        self.speak("Capturing image in 3... 2... 1...")
        time.sleep(2)  # Give time for user to position camera
        
        ret, frame = self.camera.read()
        
        if not ret:
            self.speak("Failed to capture image from camera.")
            return None
        
        # Save image temporarily
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"captured_image_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        
        self.speak("Image captured successfully.")
        print(f"Image saved as: {filename}")
        
        # Convert to PIL Image for Gemini
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img_rgb)
        
        return pil_image, filename
    
    def send_text_to_gemini(self, text):
        """Send text to Gemini and get response"""
        try:
            self.speak("Processing your question with Gemini AI...")
            print(f"Sending to Gemini: {text}")
            
            # Create prompt for better context - assist with any question
            prompt = f"You are assisting a visually impaired person. Please provide clear, concise, and helpful responses to their question. User query: {text}"
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            response_text = response.text
            
            print(f"\n[GEMINI RESPONSE]:\n{response_text}\n")
            return response_text
            
        except Exception as e:
            error_msg = f"Error communicating with Gemini: {str(e)}"
            print(error_msg)
            return error_msg
    
    def send_image_to_gemini(self, image, context=None):
        """Send image to Gemini for interpretation"""
        try:
            self.speak("Analyzing the image with Gemini AI...")
            print("Sending image to Gemini...")
            
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Create prompt for image analysis
            if context:
                prompt = (
        "You are assisting a visually impaired person. "
        "List only the main visible objects in the image and give a very brief summary. "
        "Do not add extra details or assumptions. "
        f"Focus only on: {context}. "
        "Respond in one short paragraph."
    )
            else:
                prompt = (
        "You are assisting a visually impaired person. "
        "List only the main visible objects in the image, then give a short summarized description. "
        "Do not describe background details, emotions, or speculative context. "
        "Do not be verbose. "
        "Respond in one short paragraph."
    )

            # Create the content with image
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
            response_text = response.text
            
            print(f"\n[GEMINI IMAGE ANALYSIS]:\n{response_text}\n")
            return response_text
            
        except Exception as e:
            error_msg = f"Error analyzing image with Gemini: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg
    
    def extract_and_process_text_from_image(self, image, mode="read"):
        """Extract text from image using Gemini's OCR and process based on mode"""
        try:
            self.speak("Reading text from the image...")
            print("Extracting text from image...")
            
            # Save a copy for debugging
            debug_filename = "debug_book_image.jpg"
            image.save(debug_filename)
            print(f"Debug: Image saved as {debug_filename} for inspection")
            
            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=95)
            img_byte_arr = img_byte_arr.getvalue()
            
            print(f"Debug: Image size in bytes: {len(img_byte_arr)}")
            
            # Create prompt based on mode - modified to avoid recitation blocks
            if mode == "read":
                prompt = (
                    "This is an accessibility tool for visually impaired users. "
                    "Please transcribe all visible text from this image. "
                    "If the text is from a copyrighted work, provide a detailed description of what the page contains, "
                    "including the layout, number of paragraphs, any headings, and the general topic being discussed. "
                    "Format: First describe the page layout, then provide the transcription or detailed description."
                )
            elif mode == "summarize":
                prompt = (
                    "This is an accessibility tool for visually impaired users. "
                    "Identify and describe the text content in this image. "
                    "Provide a summary of the main topics, key points, and overall content. "
                    "Include information about: the subject matter, main ideas presented, "
                    "any notable quotes or statistics, and the overall purpose of the text. "
                    "Keep it concise but informative (2-3 paragraphs)."
                )
            else:  # Default mode - read all
                prompt = (
                    "This is an accessibility tool for visually impaired users. "
                    "Please transcribe all visible text from this image. "
                    "If the text is from a copyrighted work, provide a detailed description of what the page contains, "
                    "including the layout, number of paragraphs, any headings, and the general topic being discussed. "
                    "Format: First describe the page layout, then provide the transcription or detailed description."
                )
            
            print(f"Debug: Sending image to Gemini with mode: {mode}")
            
            # Send to Gemini for OCR and processing
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
            
            print(f"Debug: Response received from Gemini")
            
            # Check finish reason
            if response.candidates and len(response.candidates) > 0:
                finish_reason = response.candidates[0].finish_reason
                print(f"Debug: Finish reason: {finish_reason}")
                
                if finish_reason.name == 'RECITATION':
                    print("Debug: Recitation block detected - trying alternative approach")
                    # If recitation blocked, try with a different prompt
                    alternative_prompt = (
                        "As an accessibility assistant for visually impaired users, "
                        "describe what you see in this image in detail. "
                        "Focus on: 1) The type of document (book, article, etc.) "
                        "2) The layout and structure (columns, paragraphs, headings) "
                        "3) The main topic or subject matter being discussed "
                        "4) Any visible section titles, chapter names, or headers "
                        "5) The general content and key concepts present. "
                        "Do not reproduce verbatim text, but help the user understand what information is on this page."
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
                    print("Debug: Alternative approach response received")
            
            # Check if response has text
            if hasattr(response, 'text') and response.text:
                response_text = response.text
            elif response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts'):
                    response_text = ' '.join([part.text for part in candidate.content.parts if hasattr(part, 'text')])
                else:
                    response_text = "Unable to extract text. The content may be blocked due to copyright protection."
            else:
                response_text = "No response received from Gemini."
            
            print(f"\n[TEXT EXTRACTED FROM IMAGE]:\n{response_text}\n")
            
            # Check if no text was found
            if not response_text or response_text.strip() == "" or response_text.lower() == "none":
                response_text = "I could not detect any readable text in this image. Please ensure the book page is well-lit, in focus, and clearly visible to the camera."
            
            return response_text
            
        except Exception as e:
            error_msg = f"Error extracting text from image: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg
    
    def process_voice_input(self):
        """Process voice input workflow - answers any question"""
        text = self.listen_for_voice()
        
        if text:
            response = self.send_text_to_gemini(text)
            self.speak(response)
    
    def process_camera_input(self):
        """Process camera input workflow for scene description"""
        if self.camera is None:
            self.speak("Camera is not available. Please check your camera connection.")
            return
            
        # Optional: Ask if user wants to provide context
        self.speak("Do you want to provide context for the image? Say yes or no.")
        
        context_input = self.listen_for_voice()
        context = None
        
        if context_input and "yes" in context_input.lower():
            self.speak("Please describe what you want me to focus on in the image.")
            context = self.listen_for_voice()
        
        # Capture image
        result = self.capture_image()
        
        if result:
            image, filename = result
            response = self.send_image_to_gemini(image, context)
            self.speak(response)
    
    def process_book_reading(self):
        """Process book reading workflow with OCR"""
        if self.camera is None:
            self.speak("Camera is not available. Please check your camera connection.")
            return
        
        # Ask user what they want to do
        self.speak("Do you want me to read the full text, or summarize it? Say read or summarize. If you say nothing, I will read the full text.")
        
        mode_input = self.listen_for_voice()
        mode = "read"  # Default mode
        
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
        
        # Capture image
        result = self.capture_image()
        
        if result:
            image, filename = result
            response = self.extract_and_process_text_from_image(image, mode)
            self.speak(response)
    
    def run(self):
        """Main application loop"""
        print("\n" + "="*60)
        print("ACCESSIBILITY ASSISTANT - CONTROLS")
        print("="*60)
        print("Press 'V' - Voice Questions (Ask anything)")
        print("Press 'C' - Camera Scene Description")
        print("Press 'B' - Book Reading (OCR)")
        print("Press 'Q' - Quit Application")
        print("="*60 + "\n")
        
        try:
            import keyboard
            
            while self.is_running:
                if keyboard.is_pressed('v'):
                    print("\n[VOICE MODE ACTIVATED - Ask Any Question]")
                    self.process_voice_input()
                    time.sleep(1)  # Prevent multiple triggers
                
                elif keyboard.is_pressed('c'):
                    print("\n[CAMERA MODE ACTIVATED - Scene Description]")
                    self.process_camera_input()
                    time.sleep(1)  # Prevent multiple triggers
                
                elif keyboard.is_pressed('b'):
                    print("\n[BOOK READING MODE ACTIVATED - OCR]")
                    self.process_book_reading()
                    time.sleep(1)  # Prevent multiple triggers
                
                elif keyboard.is_pressed('q'):
                    print("\n[SHUTTING DOWN]")
                    self.speak("Goodbye! Shutting down the Accessibility Assistant.")
                    self.is_running = False
                
                time.sleep(0.1)  # Small delay to prevent CPU overuse
        
        except ImportError:
            print("Warning: 'keyboard' module not available. Using alternative input method.")
            self.run_alternative_input()
    
    def run_alternative_input(self):
        """Alternative input method if keyboard module is not available"""
        print("\nUsing text-based input method.")
        
        while self.is_running:
            print("\n" + "="*60)
            print("Enter command:")
            print("  'v' or 'voice' - Voice Questions (Ask anything)")
            print("  'c' or 'camera' - Camera Scene Description")
            print("  'b' or 'book' - Book Reading (OCR)")
            print("  'q' or 'quit' - Exit")
            print("="*60)
            
            command = input("\nYour choice: ").lower().strip()
            
            if command in ['v', 'voice']:
                print("\n[VOICE MODE ACTIVATED - Ask Any Question]")
                self.process_voice_input()
            
            elif command in ['c', 'camera']:
                print("\n[CAMERA MODE ACTIVATED - Scene Description]")
                self.process_camera_input()
            
            elif command in ['b', 'book']:
                print("\n[BOOK READING MODE ACTIVATED - OCR]")
                self.process_book_reading()
            
            elif command in ['q', 'quit']:
                print("\n[SHUTTING DOWN]")
                self.speak("Goodbye! Shutting down the Accessibility Assistant.")
                self.is_running = False
            
            else:
                print("Invalid command. Please try again.")
    
    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up resources...")
        if self.camera is not None and self.camera.isOpened():
            self.camera.release()
        cv2.destroyAllWindows()
        print("Cleanup complete.")


def main():
    """Main function to run the application"""
    print("\n" + "="*60)
    print("ACCESSIBILITY ASSISTANT FOR VISUALLY IMPAIRED")
    print("="*60 + "\n")
    
    # Method 1: Check environment variable
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        print("✓ API key loaded from environment variable")
    
    # Method 2: Check config.txt file in same directory
    if not api_key:
        config_file = os.path.join(os.path.dirname(__file__), 'config.txt')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    api_key = f.read().strip()
                    print("✓ API key loaded from config.txt")
            except Exception as e:
                print(f"Error reading config.txt: {e}")
    
    # Method 3: Ask user to input manually
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
            # Ask if user wants to save it
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
        print("\nPlease provide your API key using one of these methods:")
        print("1. Set environment variable: GEMINI_API_KEY")
        print("2. Create config.txt file with your API key")
        print("3. Enter it when prompted")
        print("\nGet API key from: https://makersuite.google.com/app/apikey")
        print("="*60 + "\n")
        sys.exit(1)
    
    try:
        # Initialize and run the assistant
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