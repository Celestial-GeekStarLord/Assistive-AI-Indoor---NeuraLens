#!/usr/bin/env python3
"""Check available Gemini models"""

import os
from google import genai

# Load API key
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    config_file = 'config.txt'
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            api_key = f.read().strip()

if not api_key:
    print("ERROR: No API key found")
    exit(1)

print("Checking available models...\n")

try:
    client = genai.Client(api_key=api_key)
    
    # List all available models
    models = client.models.list()
    
    print("Available models:")
    print("="*60)
    for model in models:
        print(f"Model: {model.name}")
        if hasattr(model, 'supported_generation_methods'):
            print(f"  Supported methods: {model.supported_generation_methods}")
        print()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()