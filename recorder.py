import speech_recognition as sr
from colorama import Fore, init
from io import BytesIO
from queue import Queue
from threading import Thread, Event
import webrtcvad
import numpy as np

init()

class AudioProcessor:
    def __init__(self, transcriber):
        print(f"{Fore.GREEN}Initializing Audio Processor...{Fore.RESET}")
        self.transcriber = transcriber
        self.recognizer = sr.Recognizer()
        self.vad = webrtcvad.Vad(3)  # Aggressiveness level 3
        self.is_recording = False
        self.full_transcription = []
        self.transcription_queue = Queue()
        self.stop_event = Event()
        

    def record_and_process(self):
        with sr.Microphone() as source:
            while not self.stop_event.is_set():
                try:
                    print(f"\n{Fore.CYAN}Listening...{Fore.RESET}")
                    audio_data = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
                    
                    wav_buffer = BytesIO(audio_data.get_wav_data())
                    transcription = self.transcriber.transcribe_buffer(wav_buffer)
                    
                    if transcription and transcription.strip():
                        self.full_transcription.append(transcription.strip())
                        print(f"{Fore.GREEN}Current: {transcription}{Fore.RESET}")
                        self.transcription_queue.put(transcription.strip())
                    
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"{Fore.RED}Error: {e}{Fore.RESET}")
                    continue

    def start(self):
        print(f"\n{Fore.GREEN}Starting audio recording...{Fore.RESET}")
        self.stop_event.clear()
        self.recording_thread = Thread(target=self.record_and_process)
        self.recording_thread.start()
        return self.transcription_queue

    def stop(self):
        self.stop_event.set()
        if hasattr(self, 'recording_thread'):
            self.recording_thread.join()
        print(f"\n{Fore.GREEN}=== Complete Transcription ==={Fore.RESET}")
        print(f"{Fore.YELLOW}{' '.join(self.full_transcription)}{Fore.RESET}")