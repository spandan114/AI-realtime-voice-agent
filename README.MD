# Real-Time Voice Assistant

A voice assistant system that enables real-time speech interaction using OpenAI's GPT and TTS services. Built with Python, this system provides seamless voice-to-voice conversations with robust state management and performance monitoring.

## 🌟 Features

- **Real-time Voice Interaction**
  - Continuous speech recognition
  - Natural language processing
  - High-quality text-to-speech output
  - Interrupt capability during speech

- **Multiple Speech-to-Text Options**
  - OpenAI Whisper
  - Vosk (offline capability)
  - Groq
  - Deepgram

- **Text-to-Speech Providers**
  - OpenAI TTS
  - Deepgram TTS
  - Multiple voice options and customization

- **Performance Monitoring**
  - Real-time process timing
  - Detailed metrics for each component
  - Performance logging and analysis

- **Robust Error Handling**
  - Graceful recovery from errors
  - Comprehensive error logging
  - State preservation during failures

## 🏗️ Architecture

```
Voice Assistant System
│
├── Core Components
│   ├── Speech Recognition (speech_recognition)
│   ├── Audio Transcription (transcription.py)
│   ├── Language Model Processing (llm.py)
│   └── Text-to-Speech (tts.py)
│
├── State Management
│   ├── IDLE
│   ├── LISTENING
│   ├── PROCESSING
│   ├── SPEAKING
│   └── STOPPED
│
├── Threading System
│   ├── Audio Worker Thread
│   ├── Event Processing Thread
│   └── TTS Monitor Thread
│
└── Performance Monitoring
    ├── Process Timer
    ├── Metrics Collection
    └── Performance Logging
```

### Process Flow
   ```
   Text Stream -> Complete Sentence -> Audio Generation -> Audio Queue -> Playback
   (continues in parallel while streaming)
   ```
1. **Audio Input**
   - Microphone calibration
   - Continuous audio monitoring
   - Speech detection and recording

2. **Speech Processing**
   - Audio to text transcription
   - Command detection
   - Stop command handling

3. **Response Generation**
   - LLM processing
   - Context management
   - Response streaming

4. **Audio Output**
   - Text to speech conversion
   - Real-time audio playback
   - Queue management

## 🛠️ Technical Components

### Core Classes

- **VoiceAssistant**: Main system coordinator
- **AudioTranscriber**: Handles speech-to-text
- **ResponseGenerator**: Manages LLM interactions
- **TextToSpeechHandler**: Handles text-to-speech
- **ProcessTimer**: Performance monitoring

### Key Features

- **Multi-threading**: Concurrent processing of audio, events, and TTS
- **State Management**: Thread-safe state transitions
- **Queue System**: Efficient handling of audio and event queues
- **Performance Metrics**: Detailed timing and performance tracking

## 📊 Performance Monitoring

The system tracks various performance metrics:

- Speech to Text latency
- LLM Processing time
- Text Splitting duration
- Audio Generation speed
- Audio Playback timing
- Total interaction time

## 🚀 Getting Started

### Prerequisites

```bash
python >= 3.8
```

### Required Environment Variables

```env
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key  
DEEPGRAM_API_KEY=your_deepgram_api_key
```

### Installation

1. Clone the repository
```bash
git clone https://github.com/spandan114/AI-voice-chat-engine.git
git checkout voice-chat-enginee
cd voice-chat-enginee
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Run the assistant
```bash
python main.py
```

## 🎮 Usage

1. Start the assistant:
```python
from assistant import VoiceAssistant

assistant = VoiceAssistant()
assistant.start()
```

2. Available voice commands:
- Speak normally for queries/conversation
- Say "stop" to interrupt current speech
- Use "quiet" or "be quiet" to stop output
- Ctrl+C to exit the program


## 📈 Performance Optimization

The system includes built-in performance monitoring:

```python
# View real-time metrics
assistant.timer.print_metrics()

# Save metrics to file
assistant.timer.save_metrics("performance_log.json")
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🙏 Acknowledgments

- OpenAI for GPT and Whisper
- Vosk for offline speech recognition
- Deepgram for alternative speech services

## 📞 Support

For support, please open an issue in the GitHub repository.