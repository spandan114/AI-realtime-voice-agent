import json
import logging
from colorama import Fore
from openai import OpenAI
from groq import Groq
from deepgram import DeepgramClient, PrerecordedOptions
from io import BytesIO
import wave
from pydub import AudioSegment

class AudioTranscriber:
    def __init__(self, api_key, model='openai'):
        self.api_key = api_key
        self.model = model
        self._setup_client()

    def _setup_client(self):
        if self.model == 'openai':
            self.client = OpenAI(api_key=self.api_key)
        elif self.model == 'groq':
            self.client = Groq(api_key=self.api_key)
        elif self.model == 'deepgram':
            self.client = DeepgramClient(self.api_key)

    def _convert_wav_to_mp3(self, wav_data):
        """Convert WAV data to MP3 format."""
        # Create a WAV file in memory
        wav_buffer = BytesIO(wav_data)
        
        # Convert to AudioSegment
        audio_segment = AudioSegment.from_wav(wav_buffer)
        
        # Export as MP3 to a new buffer
        mp3_buffer = BytesIO()
        audio_segment.export(mp3_buffer, format='mp3', parameters=["-ac", "1", "-ar", "44100"])
        mp3_buffer.seek(0)
        
        # Create a named buffer (OpenAI requires a filename)
        class NamedBytesIO(BytesIO):
            def __init__(self, *args, **kwargs):
                self.name = "audio.mp3"
                super().__init__(*args, **kwargs)
        
        named_buffer = NamedBytesIO(mp3_buffer.read())
        return named_buffer

    def transcribe_buffer(self, audio_buffer):
        """
        Transcribe audio from a buffer using the configured service.
        Args:
            audio_buffer: BytesIO object containing WAV data
        Returns:
            str: Transcribed text
        """
        try:
            # Convert WAV to MP3
            mp3_buffer = self._convert_wav_to_mp3(audio_buffer.getvalue())
            
            # Transcribe based on selected service
            if self.model == 'openai':
                return self._transcribe_buffer_with_openai(mp3_buffer)
            elif self.model == 'groq':
                return self._transcribe_buffer_with_groq(mp3_buffer)
            elif self.model == 'deepgram':
                return self._transcribe_buffer_with_deepgram(mp3_buffer)
            else:
                raise ValueError("Unsupported transcription model")
                
        except Exception as e:
            logging.error(f"{Fore.RED}Failed to transcribe audio buffer: {e}{Fore.RESET}")
            raise

    def _transcribe_buffer_with_openai(self, audio_buffer):
        """
        Transcribe audio buffer using OpenAI's Whisper model.
        Args:
            audio_buffer: BytesIO object containing MP3 data
        Returns:
            str: Transcribed text
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

    def _transcribe_buffer_with_groq(self, audio_buffer):
        transcription = self.client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_buffer,
            language='en'
        )
        return transcription.text

    def _transcribe_buffer_with_deepgram(self, audio_buffer):
        try:
            buffer_data = audio_buffer.read()
            
            payload = {"buffer": buffer_data}
            options = PrerecordedOptions(model="nova-2", smart_format=True)
            response = self.client.listen.prerecorded.v("1").transcribe_file(payload, options)
            data = json.loads(response.to_json())

            return data['results']['channels'][0]['alternatives'][0]['transcript']
        except Exception as e:
            logging.error(f"{Fore.RED}Deepgram transcription error: {e}{Fore.RESET}")
            raise