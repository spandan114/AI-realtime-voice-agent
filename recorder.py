import speech_recognition as sr
import logging
from colorama import Fore, init
from datetime import datetime
from io import BytesIO
from queue import Queue
from threading import Thread, Event

# Initialize colorama
init()

class AudioProcessor:
    def __init__(self, transcriber):
        print(f"{Fore.GREEN}Initializing Audio Processor...{Fore.RESET}")
        
        self.transcriber = transcriber
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 2000
        self.recognizer.pause_threshold = 1
        self.recognizer.phrase_threshold = 0.1
        self.recognizer.dynamic_energy_threshold = True
        
        self.is_recording = False
        self.full_transcription = []
        self.transcription_queue = Queue()
        self.stop_event = Event()

    def record_and_process(self):
        """Record and process audio continuously using buffer."""
        try:
            with sr.Microphone() as source:
                print(f"{Fore.YELLOW}Calibrating for ambient noise...{Fore.RESET}")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print(f"{Fore.GREEN}Ready to record. Press Ctrl+C to stop.{Fore.RESET}")

                while not self.stop_event.is_set():
                    try:
                        print(f"{Fore.CYAN}Listening...{Fore.RESET}")
                        # Listen for audio
                        audio_data = self.recognizer.listen(source, timeout=10, phrase_time_limit=None)
                        
                        # Get WAV data as bytes
                        wav_buffer = BytesIO(audio_data.get_wav_data())
                        
                        # Transcribe directly from buffer
                        try:
                            # Pass the buffer directly to transcriber
                            transcription = self.transcriber.transcribe_buffer(wav_buffer)
                            if transcription and transcription.strip():
                                self.full_transcription.append(transcription.strip())
                                print(f"{Fore.GREEN}Current: {transcription}{Fore.RESET}")
                                # Add transcription to queue for processing
                                self.transcription_queue.put(transcription.strip())
                                
                        except Exception as e:
                            print(f"{Fore.RED}Transcription error: {e}{Fore.RESET}")
                        
                    except sr.WaitTimeoutError:
                        print(f"{Fore.YELLOW}No speech detected, continuing...{Fore.RESET}")
                        continue
                    except Exception as e:
                        print(f"{Fore.RED}Error during recording: {e}{Fore.RESET}")
                        continue
                        
        except Exception as e:
            print(f"{Fore.RED}Error setting up microphone: {e}{Fore.RESET}")
            raise

    def start(self):
        """Start recording and processing audio."""
        print(f"\n{Fore.GREEN}Starting audio recording...{Fore.RESET}")
        self.stop_event.clear()
        # Start recording in a separate thread
        self.recording_thread = Thread(target=self.record_and_process)
        self.recording_thread.start()
        return self.transcription_queue

    def stop(self):
        """Stop recording and display final transcription."""
        self.stop_event.set()
        if hasattr(self, 'recording_thread'):
            self.recording_thread.join()
        
        # Display complete transcription
        print(f"\n{Fore.GREEN}=== Complete Transcription ==={Fore.RESET}")
        print(f"{Fore.YELLOW}{' '.join(self.full_transcription)}{Fore.RESET}")