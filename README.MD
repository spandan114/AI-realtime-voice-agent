# Voice Agent API

Real-time voice-to-voice communication API using FastAPI and Socket.IO. This project enables bidirectional audio streaming between clients and an AI assistant, featuring real-time transcription, natural language processing, and text-to-speech capabilities.

## 🏗️ Project Structure

```
voice-agent/
├── README.md
├── requirements.txt
├── .env
├── main.py                    # Application entry point
├── config/                    # Configuration management
├── core/                     # Core business logic
├── api/                      # API implementations
├── services/                 # External service integrations
├── utils/                    # Helper utilities
└── tests/                    # Test suite
```

### Directory Details

- **config/**: Configuration and environment settings
  - `settings.py`: Application configuration
  - `logging_config.py`: Logging setup

- **core/**: Core business logic
  - `assistant.py`: Main assistant manager
  - `audio_processor.py`: Audio processing
  - `transcriber.py`: Speech-to-text services
  - `llm.py`: Language model integration
  - `tts.py`: Text-to-speech processing

- **api/**: API layer
  - `socket/`: Socket.IO implementation
  - `rest/`: REST endpoints

- **services/**: External service integrations
  - `openai_service.py`: OpenAI integration
  - `groq_service.py`: Groq integration
  - `deepgram_service.py`: Deepgram integration

- **utils/**: Helper utilities
  - `audio.py`: Audio processing utilities
  - `timer.py`: Performance timing
  - `validators.py`: Input validation

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- FFmpeg (for audio processing)
- API keys for:
  - OpenAI
  - Groq (optional)
  - Deepgram (optional)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/voice-agent.git
cd voice-agent
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```env
OPENAI_API_KEY=your_openai_key
GROQ_API_KEY=your_groq_key
DEEPGRAM_API_KEY=your_deepgram_key
```

### Running the Application

1. Start the server:
```bash
python main.py
```

2. The API will be available at:
- Socket.IO: `ws://localhost:8000/socket.io/`
- REST API: `http://localhost:8000/`
- Documentation: `http://localhost:8000/docs`

## 📡 WebSocket Events

### Client to Server

- `audio_stream`: Send audio chunks
  ```javascript
  socket.emit('audio_stream', {
    audio: base64EncodedAudio
  });
  ```

- `end_stream`: Signal end of audio stream
  ```javascript
  socket.emit('end_stream');
  ```

### Server to Client

- `audio_response`: Receive audio responses
  ```javascript
  socket.on('audio_response', (data) => {
    const { audio, text } = data;
    // Process audio response
  });
  ```

- `error`: Error notifications
  ```javascript
  socket.on('error', (data) => {
    console.error(data.message);
  });
  ```

## 🔧 Configuration

Configure service providers in `config/settings.py`:

```python
TRANSCRIPTION_PROVIDER = "openai"  # openai, groq, or deepgram
TTS_PROVIDER = "openai"           # openai or deepgram
LLM_MODEL = "gpt-4-turbo-preview" # or other models
```

## 🧪 Testing

Run the test suite:

```bash
pytest tests/
```

Run specific tests:

```bash
pytest tests/test_audio.py
pytest tests/test_transcription.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🛠️ Built With

- [FastAPI](https://fastapi.tiangolo.com/)
- [Socket.IO](https://socket.io/)
- [OpenAI](https://openai.com/)
- [Groq](https://groq.com/)
- [Deepgram](https://deepgram.com/)

## ✨ Features

- Real-time audio streaming
- Automatic speech recognition
- Natural language processing
- Text-to-speech synthesis
- Multiple provider support
- Session management
- Error handling and logging
- Performance monitoring

## 📚 Documentation

For detailed API documentation, visit:
- API Docs: `http://localhost:8000/docs`
- Socket.IO Events: See WebSocket Events section above

## ⚠️ Known Issues

- List any known issues or limitations
- Provide workarounds if available

## 🙏 Acknowledgments

- Credit to libraries and services used
- Community contributions

## 📞 Contact

Your Name - [@yourusername](https://twitter.com/yourusername)
Project Link: [https://github.com/yourusername/voice-agent](https://github.com/yourusername/voice-agent)