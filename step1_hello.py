# Step 1: Your first AI call
# We send ONE message to Gemini and print its reply.

import logging
import time
from dotenv import load_dotenv   # reads the .env file
from google import genai         # Google's official Gemini library

# Hide a harmless technical warning the library prints.
logging.getLogger("google_genai").setLevel(logging.ERROR)

# 1. Load GEMINI_API_KEY from .env into the program's environment.
#    (The key stays in .env - it is never written in the code.)
load_dotenv()

# 2. Create a "client" - the object that talks to Google's servers.
#    It automatically finds GEMINI_API_KEY that we just loaded.
client = genai.Client()

# Models to try, in order. If the first is busy, we try the next one.
MODELS = ["gemini-3.5-flash", "gemini-flash-lite-latest"]

# 3. Ask the user for a message.
message = input("You: ")

# 4. Send the message to the model and wait for the reply.
start = time.time()
for model in MODELS:
    try:
        response = client.models.generate_content(
            model=model,         # which Gemini "brain" to use
            contents=message,    # what we're asking
        )
        break                    # it worked - stop trying other models
    except genai.errors.APIError as error:
        print(f"({model} failed: {error.code} - trying the next one...)")
else:
    # This runs only if EVERY model failed.
    print("All models are busy right now. Try again in a minute!")
    raise SystemExit

# 5. Print the reply, which model answered, and how long it took.
seconds = time.time() - start
print(f"\nGemini ({model}, {seconds:.1f}s):", response.text)
