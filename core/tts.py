import os
import requests
# Load environment variables if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Map our personas to ElevenLabs voice IDs (using some of the standard high-quality voices)
VOICE_MAP = {
    "Brutal friend": "JBFqnCBsd6RMkjVDRZzb",  # George
    "Gentle mentor": "21m00Tcm4TlvDq8ikWAM",  # Rachel
    "FAANG recruiter": "2EiwWnXFnvU5JabPnv8n", # Clyde
    "Startup founder": "29vD33N1CtxCmqQRPOHJ", # Drew
    "Indian Market Expert": "pFZP5JQG7iQjIQuC4Bku", # Lily (fallback)
    "HR Professional": "EXAVITQu4vr4xnSDxMaL", # Bella
}

def get_elevenlabs_key() -> str | None:
    # Read directly from file to support hot-swapping keys without restarting the app
    try:
        from dotenv import dotenv_values
        config = dotenv_values(".env")
        if "ELEVENLABS_API_KEY" in config:
            return config["ELEVENLABS_API_KEY"]
    except ImportError:
        pass
    
    # Fallback to standard environment variable
    return os.environ.get("ELEVENLABS_API_KEY")

def generate_voice_roast(text: str, persona: str) -> bytes | None:
    api_key = get_elevenlabs_key()
    if not api_key:
        return None
        
    voice_id = VOICE_MAP.get(persona, "JBFqnCBsd6RMkjVDRZzb")
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    # We strip out markdown chars (**, #, etc) so it sounds natural
    clean_text = text.replace("**", "").replace("#", "").replace("*", "")
    
    # ElevenLabs limits single requests to ~5000 characters. 
    # We will pass the entire review up to a safe 4900 chars limit.
    intro_text = clean_text[:4900]
    data = {
        "text": intro_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=120)
    except requests.RequestException as exc:
        # Network failures are not RuntimeError, so surface them as one error type
        # for the caller instead of letting a stack trace escape.
        raise RuntimeError(f"Could not reach ElevenLabs: {exc}") from exc

    if response.status_code == 200:
        return response.content
    raise RuntimeError(
        f"ElevenLabs API error {response.status_code}: {response.text[:300]}"
    )
