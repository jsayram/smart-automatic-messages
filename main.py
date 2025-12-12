import json
import requests
import subprocess
import random
import time

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def generate_message(model, url, prompt):

    data = {
        "model": model,
        "prompt": prompt,
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
        print(f"Sent message: {message}")
    except Exception as e:
        print(f"Error sending message: {e}")

def main():
    config = load_config()
    print("Starting smart automatic messages. Press Ctrl+C to stop.")
    while True:
        message = generate_message(config['ollama_model'], config['ollama_url'], config['prompt'])
        send_message(config['phone_number'], message)
        # Random sleep between 10 seconds and 24 hours
        sleep_time = 10
        print(f"Sleeping for {sleep_time} seconds.")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()