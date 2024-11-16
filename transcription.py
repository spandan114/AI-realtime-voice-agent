"""
Audio Transcription System
=========================

A flexible audio transcription system that supports multiple providers:
- OpenAI (Whisper)
- Groq
- Deepgram

Flow:
-----
1. Audio Buffer (WAV) → Convert to MP3
2. MP3 → Send to Selected Provider
3. Provider → Return Transcribed Text

Features:
- Automatic format conversion (WAV to MP3)
- Multiple provider support
- Consistent error handling
- Detailed logging
"""

import json
import logging
from colorama import Fore
from openai import OpenAI
from groq import Groq
from faster_whisper import WhisperModel
from deepgram import DeepgramClient, PrerecordedOptions
from io import BytesIO
from timing_utils import time_process
from pydub import AudioSegment
from vosk import Model, KaldiRecognizer, SetLogLevel
import tempfile
import os
import wave

class AudioTranscriber:
    """
    A class to handle audio transcription using various service providers.
    
    Supports:
    - OpenAI's Whisper model
    - Groq's transcription service
    - Deepgram's Nova-2 model
    
    All providers accept WAV input which is automatically converted to MP3
    for compatibility.
    """
    
    def __init__(self, api_key, model='faster-whisper', device='cpu', compute_type='float32', timer=None):
        """
        Initialize the transcriber with specified provider.
        
        Args:
            api_key (str): API key for the selected service
            model (str): Provider name - faster-whisper, 'openai', 'groq', or 'deepgram'
        """
        self.device = device
        self.compute_type = compute_type
        self.api_key = api_key
        self.model = model.lower()
        self.timer = timer
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
            
        self.client = providers[self.model]()

    def _convert_wav_to_mp3(self, wav_data):
        """
        Convert WAV audio data to MP3 format for provider compatibility.
        
        Args:
            wav_data (bytes): Raw WAV audio data
            
        Returns:
            NamedBytesIO: Buffer containing MP3 data with .name attribute
                         (required by some providers)
        
        Process:
        1. Create in-memory WAV file
        2. Convert to AudioSegment
        3. Export as MP3 with specific parameters
        4. Create named buffer for provider compatibility
        """
        # Create WAV file in memory
        wav_buffer = BytesIO(wav_data)
        
        # Convert to AudioSegment for processing
        audio_segment = AudioSegment.from_wav(wav_buffer)
        
        # Export as MP3 with specific parameters
        # -ac 1: mono audio
        # -ar 44100: 44.1kHz sample rate
        mp3_buffer = BytesIO()
        audio_segment.export(
            mp3_buffer,
            format='mp3',
            parameters=["-ac", "1", "-ar", "44100"]
        )
        mp3_buffer.seek(0)
        
        # Create named buffer (required by some providers)
        class NamedBytesIO(BytesIO):
            def __init__(self, *args, **kwargs):
                self.name = "audio.mp3"  # Required by OpenAI
                super().__init__(*args, **kwargs)
        
        return NamedBytesIO(mp3_buffer.read())

    @time_process("transcription_generation")
    def transcribe_buffer(self, audio_buffer):
        """
        Main method to transcribe audio using the configured service.
        
        Args:
            audio_buffer (BytesIO): Buffer containing WAV audio data
            
        Returns:
            str: Transcribed text
            
        Raises:
            ValueError: If unsupported transcription model
            Exception: Provider-specific errors
        """
        try:
            # Convert input WAV to MP3
            mp3_buffer = self._convert_wav_to_mp3(audio_buffer.getvalue())
            
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
                
            return transcription_methods[self.model](mp3_buffer)
                
        except Exception as e:
            logging.error(f"{Fore.RED}Failed to transcribe audio buffer: {e}{Fore.RESET}")
            raise

    def _transcribe_buffer_with_vosk(self, audio_buffer):
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                wav_buffer = BytesIO()
                audio_segment = AudioSegment.from_mp3(BytesIO(audio_buffer.read()))
                audio_segment.export(wav_buffer, format='wav')
                wav_buffer.seek(0)
                temp_wav.write(wav_buffer.read())
                temp_wav_path = temp_wav.name

            with wave.open(temp_wav_path, "rb") as wf:
                recognizer = KaldiRecognizer(self.client, wf.getframerate())
                recognizer.SetWords(True)

                results = []
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    if recognizer.AcceptWaveform(data):
                        part_result = json.loads(recognizer.Result())
                        results.append(part_result.get('text', ''))

                part_result = json.loads(recognizer.FinalResult())
                results.append(part_result.get('text', ''))

            os.unlink(temp_wav_path)
            return ' '.join(filter(None, results))

        except Exception as e:
            logging.error(f"{Fore.RED}Vosk transcription error: {str(e)}{Fore.RESET}")
            raise


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
            transcription = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_buffer,
                language='en'
            )
            return transcription.text
        except Exception as e:
            logging.error(f"{Fore.RED}OpenAI transcription error: {str(e)}{Fore.RESET}")
            raise

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
            logging.error(f"{Fore.RED}faster-whisper transcription error: {str(e)}{Fore.RESET}")
            raise

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
            transcription = self.client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_buffer,
                language='en'
            )
            return transcription.text
        except Exception as e:
            logging.error(f"{Fore.RED}Groq transcription error: {str(e)}{Fore.RESET}")
            raise

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
            logging.error(f"{Fore.RED}Deepgram transcription error: {e}{Fore.RESET}")
            raise
