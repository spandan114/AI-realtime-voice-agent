"""
Audio Transcription System
=========================

A flexible audio transcription system that supports multiple providers:
- OpenAI (Whisper)
- Groq
- Deepgram

Flow:
-----
1. Audio Buffer (PCM) → Convert to WAV
2. MP3 → Send to Selected Provider
3. Provider → Return Transcribed Text

Features:
- Automatic format conversion (PCM to WAV)
- Multiple provider support
- Consistent error handling
- Detailed logging
"""

import json
from colorama import Fore
from openai import OpenAI
from groq import Groq
from faster_whisper import WhisperModel
from deepgram import DeepgramClient, PrerecordedOptions
from io import BytesIO
from vosk import Model, KaldiRecognizer, SetLogLevel
import tempfile
import os
import wave
from config.logging import logger

# Create named buffer (required by some providers)
class NamedBytesIO(BytesIO):
    def __init__(self, *args, **kwargs):
        self.name = "audio.mp3"  # Required by OpenAI
        super().__init__(*args, **kwargs)

class AudioTranscriber:
    """
    A class to handle audio transcription using various service providers.
    
    Supports:
    - OpenAI's Whisper model
    - Faster-Whisper
    - Vosk
    - Groq's transcription service
    - Deepgram's Nova-2 model
    
    All providers accept WAV input which is automatically converted to MP3
    for compatibility.
    """
    
    def __init__(self, api_key=None, model='faster-whisper', device='cpu', compute_type='float32'):
        """
        Initialize the transcriber with specified provider.
        
        Args:
            api_key (str): API key for the selected service
            model (str): Provider name - faster-whisper, 'openai', 'groq', or 'deepgram'
        """

        if model.lower() in ['groq', 'openai'] and api_key is None:
            raise ValueError(f"API key is required for model '{model}'")
    
        self.device = device
        self.compute_type = compute_type
        self.api_key = api_key
        self.model = model.lower()
        self._setup_client()

    def _setup_client(self):
        """
        Initialize the appropriate client based on selected provider.
        
        Raises:
            ValueError: If an unsupported model is specified
        """
        providers = {
            'faster-whisper': lambda: WhisperModel(
                model_size_or_path="large-v3",
                device=self.device,
                compute_type=self.compute_type
            ),
            'openai': lambda: OpenAI(api_key=self.api_key),
            'groq': lambda: Groq(api_key=self.api_key),
            'deepgram': lambda: DeepgramClient(self.api_key),
            'vosk': lambda: Model(lang="en-us"),

        }
        
        if self.model not in providers:
            raise ValueError(f"Unsupported model: {self.model}")
            
        self.client:OpenAI | Groq | DeepgramClient = providers[self.model]()

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> BytesIO:
        """
        Converts raw PCM data to WAV format.

        Args:
            pcm_data (bytes): Raw PCM audio data.
            sample_rate (int): The audio sample rate (e.g., 16000 Hz).
            channels (int): Number of audio channels (1 for mono, 2 for stereo).
            sample_width (int): Byte width of each sample (2 for 16-bit audio).

        Returns:
            BytesIO: A BytesIO object containing the WAV file data.
        """
        # Create a BytesIO object to hold the WAV data
        wav_buffer = BytesIO()

        # Initialize a wave file writer
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)  # 2 bytes for 16-bit PCM
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)

        # Reset buffer pointer to the beginning
        wav_buffer.seek(0)
        return wav_buffer

    def transcribe_buffer(self, audio_buffer):
        """
        Main method to transcribe audio using the configured service.
        
        Args:
            audio_buffer : Buffer containing PCM audio data
            
        Returns:
            str: Transcribed text
            
        Raises:
            ValueError: If unsupported transcription model
            Exception: Provider-specific errors
        """
        try:
            # Convert input PCM TO WAV
            wav_buffer = self._pcm_to_wav(audio_buffer)

            # Route to appropriate provider
            transcription_methods = {
                'faster-whisper': self._transcribe_buffer_with_faster_whisper,
                'openai': self._transcribe_buffer_with_openai,
                'groq': self._transcribe_buffer_with_groq,
                'deepgram': self._transcribe_buffer_with_deepgram,
                'vosk': self._transcribe_buffer_with_vosk,
            }
            
            if self.model not in transcription_methods:
                raise ValueError(f"Unsupported transcription model: {self.model}")
                
            return transcription_methods[self.model](wav_buffer)
                
        except Exception as e:
            logger.error(f"{Fore.RED}Failed to transcribe audio buffer: {e}{Fore.RESET}")
            raise type(e)(f"Failed to transcribe audio buffer: {str(e)}") from e

    def _transcribe_buffer_with_vosk(self, wav_buffer):
        """
        Transcribe audio from a WAV buffer using Vosk.

        Args:
            wav_buffer (BytesIO): A BytesIO object containing the WAV audio data.

        Returns:
            str: The transcribed text.
        """
        try:
            # Ensure the wav_buffer is converted to bytes
            wav_data = wav_buffer.read() if hasattr(wav_buffer, 'read') else wav_buffer

            # Save the WAV data to a temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav.write(wav_data)
                temp_wav_path = temp_wav.name

            # Open the WAV file for reading and perform transcription
            with wave.open(temp_wav_path, "rb") as wf:
                recognizer = KaldiRecognizer(self.client, wf.getframerate())
                recognizer.SetWords(True)

                results = []
                while True:
                    # Read audio frames and ensure they're passed as bytes
                    data = wf.readframes(4000)  # Read 4000 frames
                    if len(data) == 0:
                        break
                    if recognizer.AcceptWaveform(data):
                        part_result = json.loads(recognizer.Result())
                        results.append(part_result.get('text', ''))

                # Get the final transcription result
                part_result = json.loads(recognizer.FinalResult())
                results.append(part_result.get('text', ''))

            # Clean up temporary file
            os.unlink(temp_wav_path)

            # Combine and return the transcribed text
            return ' '.join(filter(None, results))

        except Exception as e:
            logger.error(f"{Fore.RED}Vosk transcription error: {str(e)}{Fore.RESET}")
            raise type(e)(f"Vosk transcription error: {str(e)}") from e

    def _transcribe_buffer_with_openai(self, audio_buffer):
        """
        Transcribe audio using OpenAI's Whisper model.
        
        Args:
            audio_buffer (NamedBytesIO): Buffer containing MP3 data
            
        Returns:
            str: Transcribed text
            
        Notes:
            - Uses whisper-1 model
            - Optimized for English language
        """
        try:
            # Ensure the audio buffer is in WAV format
            if not isinstance(audio_buffer, BytesIO):
                raise ValueError("Invalid audio buffer format. Expected BytesIO containing WAV data.")

            audio_buffer.name = "audio.wav"  # Set a name attribute required by OpenAI API

            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_buffer,
                language='en',
                temperature=0.8
            )
            return transcription.text
        except Exception as e:
            logger.error(f"{Fore.RED}OpenAI transcription error: {str(e)}{Fore.RESET}")
            raise type(e)(f"OpenAI transcription error: {str(e)}") from e

    def _transcribe_buffer_with_faster_whisper(self, audio_buffer):
        try:
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_buffer.read())
                temp_path = temp_file.name
            
            segments, _ = self.client.transcribe(
                temp_path,
                language="en",
                beam_size=5,
                word_timestamps=True
            )
            
            os.unlink(temp_path)
            return " ".join([segment.text for segment in segments])
        
        except Exception as e:
            logger.error(f"{Fore.RED}faster-whisper transcription error: {str(e)}{Fore.RESET}")
            raise type(e)(f"faster-whisper transcription error: {str(e)}") from e

    def _transcribe_buffer_with_groq(self, audio_buffer):
        """
        Transcribe audio using Groq's service.
        
        Args:
            audio_buffer (NamedBytesIO): Buffer containing MP3 data
            
        Returns:
            str: Transcribed text
            
        Notes:
            - Uses whisper-large-v3 model
            - Optimized for English language
        """
        try:

            # Ensure the audio buffer is in WAV format
            if not isinstance(audio_buffer, BytesIO):
                raise ValueError("Invalid audio buffer format. Expected BytesIO containing WAV data.")

            audio_buffer.name = "audio.wav"  # Set a name attribute required by OpenAI API

            transcription = self.client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_buffer,
                language='en',
                temperature=0.8
            )
            return transcription.text
        except Exception as e:
            logger.error(f"{Fore.RED}Groq transcription error: {str(e)}{Fore.RESET}")
            raise type(e)(f"Groq transcription error: {str(e)}") from e

    def _transcribe_buffer_with_deepgram(self, audio_buffer):
        """
        Transcribe audio using Deepgram's Nova-2 model.
        Args:
            audio_buffer (NamedBytesIO): Buffer containing MP3 data
        Returns:
            str: Transcribed text
        Notes:
            - Uses nova-2 model for improved accuracy
            - Enables smart formatting for better readability
        """
        try:
            buffer_data = audio_buffer.read()
            
            # Configure Deepgram options
            payload = {"buffer": buffer_data}
            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True  # Adds punctuation and capitalization
            )
            
            # Send for transcription
            response = self.client.listen.prerecorded.v("1").transcribe_file(
                payload,
                options
            )
            
            # Parse response
            data = json.loads(response.to_json())
            return data['results']['channels'][0]['alternatives'][0]['transcript']
            
        except Exception as e:
            logger.error(f"{Fore.RED}Deepgram transcription error: {e}{Fore.RESET}")
            raise type(e)(f"Deepgram Transcription Failed: {str(e)}") from e