from google import genai
from dotenv import load_dotenv
import os
import json
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = "gemini-2.5-flash-preview-native-audio-dialog"

with open('questions.json') as f:
    questions = json.load(f)

with open('prompt.txt', 'r') as f: 
    p = f.read()
    prompt = p.format(questions=questions)