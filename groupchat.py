import json
import requests
import subprocess
import time
import sqlite3
import os

RESPONSE_CACHE_FILE = "response_cache.json"
MAX_CACHE_SIZE = 50  # Keep last 50 responses

def load_response_cache():
    """Load previous responses from cache file."""
    try:
        if os.path.exists(RESPONSE_CACHE_FILE):
            with open(RESPONSE_CACHE_FILE, 'r') as f:
                cache = json.load(f)
                print(f"  📂 Loaded {len(cache)} cached responses")
                return cache
    except Exception as e:
        print(f"  ⚠️  Could not load cache: {e}")
    return []

def save_response_cache(cache):
    """Save responses to cache file."""
    # Keep only last MAX_CACHE_SIZE responses
    cache = cache[-MAX_CACHE_SIZE:]
    try:
        with open(RESPONSE_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
        print(f"  💾 Saved {len(cache)} responses to cache")
    except Exception as e:
        print(f"  ⚠️  Could not save cache: {e}")

def add_to_cache(response):
    """Add a response to the cache."""
    cache = load_response_cache()
    cache.append(response.lower())
    save_response_cache(cache)

def get_recent_phrases():
    """Get recent phrases to avoid repetition."""
    cache = load_response_cache()
    return cache[-10:]  # Return last 10 responses for context

def generate_group_response(model, url, incoming_message, sender_name=None):
    """Generate a response to a group chat message with JARVIS personality."""

    print(f"  🔄 Loading personality...")
    personalities = load_personality()
    personality = personalities.get('girlfriend_personality', 'Be a helpful and friendly AI assistant.')

    # Get recent responses to avoid repetition
    print(f"  📚 Checking response cache...")
    recent = get_recent_phrases()
    avoid_text = ""
    if recent:
        print(f"  ⚠️  Avoiding {len(recent)} recent phrases")
        avoid_text = f"\n\nCRITICAL - DO NOT repeat these phrases or patterns from recent messages: {recent}\nUse DIFFERENT words, reactions, and sentence structures!"

    prompt = f"You are JARVIS, a helpful AI assistant in a group chat. Be friendly, witty, and engaging. {personality}{avoid_text}\n\nGroup message: \"{incoming_message}\"\n\nYour response:"

    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    print(f"  🧠 Sending to LLM (model: {model})...")
    try:
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        print(f"  ✓ LLM responded successfully")
        message = response.json()['response'].strip()
        # Remove surrounding quotes if present
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        print(f"  📝 Generated response: {message}")
        return message
    except requests.exceptions.Timeout:
        error_msg = "LLM request timed out (30s)"
        print(f"  ❌ {error_msg}")
        return "Sorry, I'm a bit slow right now! 🤖"
    except requests.exceptions.ConnectionError:
        error_msg = "Cannot connect to Ollama - is it running?"
        print(f"  ❌ {error_msg}")
        return "Connection issues, please try again later! 🔌"
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        print(f"  ❌ {error_msg}")
        return "Having trouble thinking right now! 🧠"
    except Exception as e:
        print(f"  ❌ Unexpected error: {type(e).__name__}: {e}")
        return "Oops, something went wrong! 🤷‍♂️"

def send_message(phone, message):
    """Send an iMessage to the specified phone number, fallback to SMS if fails."""
    message = message.replace('"', '\\"')

    # Try iMessage first
    imessage_script = f'''
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{phone}" of targetService
    send "{message}" to targetBuddy
end tell
'''
    try:
        result = subprocess.run(['osascript', '-e', imessage_script], check=True, capture_output=True, text=True)
        print(f"  ✓ Sent via iMessage to [{phone}]: {message}")
        return True
    except Exception as e:
        print(f"  ⚠ iMessage failed, trying SMS...")

        # Fallback to SMS
        sms_script = f'''
tell application "Messages"
    set targetService to 1st service whose service type = SMS
    set targetBuddy to buddy "{phone}" of targetService
    send "{message}" to targetBuddy
end tell
'''
        try:
            subprocess.run(['osascript', '-e', sms_script], check=True)
            print(f"  ✓ Sent via SMS to [{phone}]: {message}")
            return True
        except Exception as e2:
            print(f"  ✗ SMS also failed: {e2}")

            # Last resort - try without specifying service type
            generic_script = f'''
tell application "Messages"
    send "{message}" to buddy "{phone}"
end tell
'''
            try:
                subprocess.run(['osascript', '-e', generic_script], check=True)
                print(f"  ✓ Sent (generic) to [{phone}]: {message}")
                return True
            except Exception as e3:
                print(f"  ✗ All send methods failed: {e3}")
                return False

def get_last_message_from_any():
    """Get the last message from any phone number that contains @JARVIS."""
    db_path = os.path.expanduser("~/Library/Messages/chat.db")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get the most recent message from any sender
        query = """
        SELECT m.rowid, m.text, m.is_from_me, m.date, h.id as phone
        FROM message m
        JOIN handle h ON m.handle_id = h.rowid
        WHERE m.is_from_me = 0  -- Only incoming messages
        ORDER BY m.date DESC
        LIMIT 1
        """

        cursor.execute(query)
        row = cursor.fetchone()
        conn.close()

        if row:
            rowid, text, is_from_me, date, phone = row
            return (text, rowid, phone)
        return (None, None, None)
    except Exception as e:
        print(f"Error reading Messages database: {e}")
        return (None, None, None)

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def load_personality():
    """Load personality prompts from personality.json"""
    with open('personality.json', 'r') as f:
        return json.load(f)

def check_ollama(model, url):
    """Verify Ollama is running and model exists."""
    try:
        response = requests.post(url, json={"model": model, "prompt": "hi", "stream": False}, timeout=15)
        response.raise_for_status()
        return True, None
    except requests.exceptions.HTTPError:
        return False, f"Model '{model}' not found"
    except requests.exceptions.ConnectionError:
        return False, "Ollama not running"
    except Exception as e:
        return False, str(e)

def main():
    config = load_config()

    # Get JARVIS dedicated number (optional)
    jarvis_number = config.get('jarvis_number')

    print("=" * 55)
    print("🤖 JARVIS GROUP CHAT BOT")
    print("=" * 55)
    if jarvis_number:
        print(f"JARVIS Number: {jarvis_number}")
    print("\n🔍 Checking Ollama...")
    ok, err = check_ollama(config['ollama_model'], config['ollama_url'])
    if ok:
        print(f"  ✓ Model ready: {config['ollama_model']}")
    else:
        print(f"  ✗ {err}")
        return

    print("\n🧪 Testing JARVIS response generation...")
    try:
        test_response = generate_group_response(
            config['ollama_model'],
            config['ollama_url'],
            "Hello JARVIS, this is a test message"
        )
        print(f"  ✓ JARVIS test successful: {test_response}")
    except Exception as e:
        print(f"  ✗ JARVIS test failed: {e}")
        print("  ⚠️  Bot may not work properly. Check your setup.")
        return

    print("\n📱 Listening for @JARVIS mentions from any number")
    print("\n" + "-" * 55)
    print("Waiting for messages... (Ctrl+C to stop)\n")

    # Get initial state
    _, last_rowid, _ = get_last_message_from_any()

    poll_count = 0
    while True:
        poll_count += 1
        if poll_count % 20 == 0:  # Every 60 seconds (20 * 3s)
            print(f"  🔍 Still listening... (checked {poll_count} times)")

        # Check for new messages from any sender
        body, rowid, sender_phone = get_last_message_from_any()

        # New incoming message
        if body and rowid != last_rowid:
            # Check if message contains @JARVIS
            if '@JARVIS' in body.upper():
                print(f"\n🤖 JARVIS mentioned by [{sender_phone}]")
                print(f"💬 Message: {body}")
                print(f"  📊 Message ID: {rowid}")

                # Remove @JARVIS from the message for processing
                clean_message = body.replace('@JARVIS', '').replace('@jarvis', '').strip()

                if clean_message:  # Only respond if there's content after @JARVIS
                    response = generate_group_response(
                        config['ollama_model'],
                        config['ollama_url'],
                        clean_message
                    )

                    print(f"🤖 JARVIS responding: {response}")
                    add_to_cache(response)
                    print(f"  ⏳ Waiting 2s before sending...")
                    time.sleep(2)
                    
                    # Use JARVIS number if configured, otherwise respond to sender
                    response_number = jarvis_number if jarvis_number else sender_phone
                    send_message(response_number, response)
                    
                    if jarvis_number and jarvis_number != sender_phone:
                        print(f"  📤 Sent from JARVIS number: {jarvis_number}")
                else:
                    print("  ℹ️  @JARVIS mentioned but no message content")

                print("-" * 55)

            last_rowid = rowid

        time.sleep(3)  # Check every 3 seconds

if __name__ == "__main__":
    main()