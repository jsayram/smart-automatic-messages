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
                return json.load(f)
    except:
        pass
    return []

def save_response_cache(cache):
    """Save responses to cache file."""
    # Keep only last MAX_CACHE_SIZE responses
    cache = cache[-MAX_CACHE_SIZE:]
    with open(RESPONSE_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def add_to_cache(response):
    """Add a response to the cache."""
    cache = load_response_cache()
    cache.append(response.lower())
    save_response_cache(cache)

def get_recent_phrases():
    """Get recent phrases to avoid repetition."""
    cache = load_response_cache()
    return cache[-10:]  # Return last 10 responses for context

def generate_admin_response(model, url, command):
    """Generate a response for admin commands with @LLM prefix."""
    
    personalities = load_personality()
    admin_prompt = personalities.get('admin_personality', 'You are a helpful AI assistant.')

    prompt = f"{admin_prompt}\n\nAdmin command: \"{command}\"\n\nYour response:"

    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        message = response.json()['response'].strip()
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        return message
    except Exception as e:
        return f"Error: {e}"

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def load_personality():
    """Load personality prompts from personality.json"""
    with open('personality.json', 'r') as f:
        return json.load(f)

def generate_response(model, url, incoming_message, sender_name=None):
    """Generate a response to an incoming message with a fun personality."""
    
    personalities = load_personality()
    personality = personalities.get('girlfriend_personality', 'Be a helpful and friendly boyfriend.')

    # Get recent responses to avoid repetition
    recent = get_recent_phrases()
    avoid_text = ""
    if recent:
        avoid_text = f"\n\nCRITICAL - DO NOT repeat these phrases or patterns from recent messages: {recent}\nUse DIFFERENT words, reactions, and sentence structures!"
    
    prompt = f"DONT SAY MAN OR GIRL TERMS. YOU ARE TALKING TO MY GIRLFIEND. NEVER ASK QUESTIONS - ONLY STATEMENTS! {personality}{avoid_text}\n\nThey sent: \"{incoming_message}\"\n\nYour response (STATEMENT ONLY, NO QUESTIONS):"

    data = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        message = response.json()['response'].strip()
        # Remove surrounding quotes if present
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        return message
    except Exception as e:
        print(f"Error generating response: {e}")
        return "holdd one one sec, busy!! 💕"

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

def get_last_message(phone, include_from_me=False):
    """Get the last message from a specific phone number.
    
    Args:
        phone: Phone number to check
        include_from_me: If True, returns the last message regardless of sender.
                        If False, only returns messages FROM them (is_from_me=0).
    """
    db_path = os.path.expanduser("~/Library/Messages/chat.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        phone_digits = ''.join(filter(str.isdigit, phone))
        
        query = """
        SELECT m.rowid, m.text, m.is_from_me, m.date
        FROM message m
        JOIN handle h ON m.handle_id = h.rowid
        WHERE h.id LIKE ?
        ORDER BY m.date DESC
        LIMIT 1
        """
        
        cursor.execute(query, (f"%{phone_digits[-10:]}%",))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            rowid, text, is_from_me, date = row
            # For admin: return any message (we'll check @LLM prefix)
            # For girlfriend: only return if it's FROM her (is_from_me=0)
            if include_from_me:
                return (is_from_me == 0, text, rowid, is_from_me)
            else:
                return (is_from_me == 0, text, rowid)
        
        if include_from_me:
            return (False, None, None, None)
        return (False, None, None)
    except Exception as e:
        print(f"Error reading Messages database: {e}")
        if include_from_me:
            return (False, None, None, None)
        return (False, None, None)

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
    
    # The number to listen for messages FROM (your girlfriend)
    listen_from = config['listen_from']
    
    # Admin number for @LLM commands (optional)
    admin_number = config.get('admin_number', None)
    
    print("=" * 55)
    print("🤖 AUTO-RESPONDER - Responds as YOU!")
    print("=" * 55)
    
    # Startup checks
    print("\n🔍 Checking Ollama...")
    ok, err = check_ollama(config['ollama_model'], config['ollama_url'])
    if ok:
        print(f"  ✓ Model ready: {config['ollama_model']}")
    else:
        print(f"  ✗ {err}")
        return
    
    print(f"\n📱 Listening for messages from: {listen_from}")
    print(f"📤 Will respond back to: {listen_from}")
    if admin_number:
        print(f"🔧 Admin commands from: {admin_number} (use @LLM prefix)")
    print("\n" + "-" * 55)
    print("Waiting for messages... (Ctrl+C to stop)\n")
    
    # Get initial state
    _, _, last_rowid = get_last_message(listen_from)
    last_admin_rowid = None
    if admin_number:
        _, _, last_admin_rowid, _ = get_last_message(admin_number, include_from_me=True)
    
    while True:
        # Check girlfriend's messages
        is_incoming, body, rowid = get_last_message(listen_from)
        
        # New incoming message from girlfriend
        if is_incoming and body and rowid != last_rowid:
            print(f"\n💬 [{listen_from}] says: {body}")
            
            response = generate_response(
                config['ollama_model'], 
                config['ollama_url'], 
                body
            )
            
            print(f"🤖 Responding: {response}")
            add_to_cache(response)
            time.sleep(2)
            send_message(listen_from, response)
            
            last_rowid = rowid
            print("-" * 55)
        
        # Check admin messages (if configured)
        if admin_number:
            _, admin_body, admin_rowid, admin_is_from_me = get_last_message(admin_number, include_from_me=True)
            
            # Only process messages that YOU sent (is_from_me=1) with @LLM prefix
            if admin_body and admin_rowid != last_admin_rowid and admin_is_from_me == 1:
                # Check for @LLM prefix
                if admin_body.strip().upper().startswith('@LLM'):
                    command = admin_body.strip()[4:].strip()  # Remove @LLM prefix
                    print(f"\n🔧 [ADMIN] {admin_number}: {admin_body}")
                    
                    response = generate_admin_response(
                        config['ollama_model'],
                        config['ollama_url'],
                        command
                    )
                    
                    print(f"🤖 Admin response: {response}")
                    time.sleep(1)
                    send_message(admin_number, response)
                    print("-" * 55)
                
                last_admin_rowid = admin_rowid
        
        time.sleep(3)  # Check every 3 seconds

if __name__ == "__main__":
    main()
