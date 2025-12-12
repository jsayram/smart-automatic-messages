# Smart Automatic Messages

A simple Python console application that automatically sends cute messages to your girlfriend using a local LLM and iMessages.

## Requirements

- macOS with Messages app logged into iCloud
- Python 3
- Ollama installed and running locally (free)

## Setup

1. Install Ollama: https://ollama.ai/
2. Pull a model: `ollama pull llama2`
3. Install dependencies: `pip install -r requirements.txt`
4. Edit `config.json` with your girlfriend's phone number and model name.
5. Run: `python main.py`

The app will run indefinitely, sending messages at random intervals (1-24 hours).

## How it works

- Uses Ollama for local LLM to generate messages
- Sends via AppleScript to Messages app
- Random timing to avoid predictability

All free and local.