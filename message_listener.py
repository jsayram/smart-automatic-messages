import json
import requests
import subprocess
import random
import time
import sqlite3
import os
from datetime import datetime

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def generate_message(model, url, prompt, incoming_message=None):
    if incoming_message:
        full_prompt = f"Respond to this message from my girlfriend: '{incoming_message}'. " + prompt
    else:
        full_prompt = prompt

    data = {
        "model": model,
        "prompt": full_prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        message = response.json()['response'].strip()
        # Remove surrounding quotes if present
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]
        return message
    except Exception as e:
        print(f"Error generating message: {e}")
        return "I love you! 💕"

def check_ollama_model(model, url):
    """Test if the Ollama model is available and working."""
    test_data = {
        "model": model,
        "prompt": "Say hi",
        "stream": False
    }
    try:
        response = requests.post(url, json=test_data, timeout=15)
        response.raise_for_status()
        return True, None
    except requests.exceptions.HTTPError as e:
        return False, f"Model '{model}' not found. Check 'ollama list' for available models."
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Ollama. Is it running? Try 'ollama serve'"
    except Exception as e:
        return False, str(e)

def send_message(phone, message):
    # Escape quotes in message
    message = message.replace('"', '\\"')
    script = f'''
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "{phone}" of targetService
    send "{message}" to targetBuddy
end tell
'''
    try:
        subprocess.run(['osascript', '-e', script], check=True)
        print(f"✓ Sent to [{phone}]: {message}")
    except Exception as e:
        print(f"✗ Error sending to [{phone}]: {e}")

def get_last_message(phone):
    """
    Query the Messages SQLite database directly to get the last incoming message.
    Returns (is_from_them, message_body, message_rowid) or (False, None, None)
    """
    db_path = os.path.expanduser("~/Library/Messages/chat.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Normalize phone number (remove non-digits for matching)
        phone_digits = ''.join(filter(str.isdigit, phone))
        
        # Query for the last message from this phone number
        # is_from_me = 0 means it's an incoming message
        query = """
        SELECT m.rowid, m.text, m.is_from_me, m.date
        FROM message m
        JOIN handle h ON m.handle_id = h.rowid
        WHERE h.id LIKE ?
        ORDER BY m.date DESC
        LIMIT 1
        """
        
        # Try with different phone formats
        cursor.execute(query, (f"%{phone_digits[-10:]}%",))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            rowid, text, is_from_me, date = row
            # is_from_me = 0 means incoming (from her), 1 means outgoing (from you)
            return (is_from_me == 0, text, rowid)
        
        return (False, None, None)
    except Exception as e:
        print(f"Error reading Messages database: {e}")
        return (False, None, None)

def main():
    config = load_config()
    listen_number = config['listen_from']
    send_number = config['sending_from']
    
    print("=" * 50)
    print("Starting message listener. Press Ctrl+C to stop.")
    print("=" * 50)
    
    # Startup checks
    print("\n🔍 Running startup checks...")
    
    # Check Ollama model
    print(f"  Checking Ollama model: {config['ollama_model']}")
    model_ok, error = check_ollama_model(config['ollama_model'], config['ollama_url'])
    if model_ok:
        print(f"  ✓ Ollama model is ready!")
    else:
        print(f"  ✗ Ollama error: {error}")
        print("  Exiting. Please fix the model configuration.")
        return
    
    print(f"\n📱 Listening for messages from: {listen_number}")
    print(f"📤 Sending responses to: {send_number}")
    
    # Test database connection first
    is_from_her, body, rowid = get_last_message(listen_number)
    if body:
        print(f"✓ Database connected! Last message found (rowid={rowid}): {body[:50]}...")
    else:
        print("✗ No messages found from this number yet (or database issue)")
    
    last_rowid = rowid  # Start tracking from current message
    
    while True:
        is_from_her, body, rowid = get_last_message(listen_number)
        
        # Debug output
        if body:
            print(f"[{listen_number}] Last msg (rowid={rowid}, from_her={is_from_her}): {body[:50]}...")
        
        # Only respond if it's a new incoming message from her
        if is_from_her and body and rowid != last_rowid:
            print(f"\n>>> [{listen_number}] New message: {body}")
            response = generate_message(config['ollama_model'], config['ollama_url'], config['prompt'], body)
            print(f"<<< Sending to [{send_number}]: {response}")
            send_message(send_number, response)
            last_rowid = rowid
        
        time.sleep(5)  # Check every 5 seconds

if __name__ == "__main__":
    main()