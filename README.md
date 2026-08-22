# Suno AI - NVDA Voice Assistant

Suno AI is an intelligent voice assistant for NVDA screen reader, designed to provide a "Siri-like" hands-free experience. It allows visually impaired users to seamlessly interact with their Windows computer using voice commands, entirely for free and with zero external API key requirements.

## Features

- **Zero-Delay Wake Word Detection:** Features an asynchronous background wake-word engine. Just say "Hey Suno" or "Hello Suno" to instantly wake the assistant. No need to press any keys!
- **Intelligent Intent Parsing:** Designed to understand natural language. You don't need rigid commands; speak naturally (e.g., "what is 250 plus 15", "please open Chrome").
- **App Launcher:** Instantly launch Windows applications like Word, Excel, Chrome, YouTube, Calculator, WhatsApp, and more just by using your voice.
- **General Knowledge & Web Search:** Uses a dual-engine lookup system (DuckDuckGo Instant Answers + Wikipedia API) to rapidly fetch accurate answers and summarize them, skipping complex technical jargon and pronunciation guides.
- **Smart Math Calculator:** Extracts math logic from spoken queries and answers instantly.
- **Time, Date & Weather:** Instantly get current local details without opening a browser.
- **Privacy-Friendly & Lightweight:** No bloated dependencies. Direct integration with Google Cloud Chromium Speech-to-Text via pure Python standard libraries to ensure 100% compatibility across NVDA versions without crashing.

## Usage

### Waking the Assistant
You can wake the assistant using your voice:
- Simply say **"Hey Suno"** or **"Hello Suno"** into your microphone.
- Wait for the **"Beep"** sound, then immediately speak your command.

### Example Commands
- **App launching:** "Open Google Chrome", "Start Calculator", "Launch WhatsApp", "Word kholo"
- **Math:** "What is 500 divided by 2?", "Calculate 25 plus 30"
- **Knowledge:** "Pakistan ki currency kya hai?", "Tell me about Mount Everest", "Who is Albert Einstein?"
- **Utilities:** "What is the time?", "What is the weather?"

## Installation
Download the `.nvda-addon` file from the [Releases](https://github.com/) page and double-click it while NVDA is running to install. Restart NVDA when prompted.

## Development

Suno AI is built using pure Python targeting NVDA's Python environment. The wake-word listener uses a highly optimized PowerShell bridge to the native Windows `System.Speech.Recognition` engine to run silently in the background without locking NVDA's main thread.

### Source Code Structure
- `globalPlugins/suno_ai.py` - Core logic, APIs, Audio processing, and Intent Parsing.
- `manifest.ini` - Add-on metadata and NVDA version compatibility constraints.

## Developer
Developed by **Raza** (Suno Tech Solutions).

## License
Open Source. Free to use, modify, and distribute.
