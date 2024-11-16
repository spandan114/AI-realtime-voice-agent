"""
Voice Assistant System
=====================

A real-time voice assistant that:
1. Listens to user speech
2. Transcribes audio to text
3. Generates responses using LLM
4. Converts responses to speech
5. Plays audio responses

The system uses multiple threads to handle concurrent operations:
- Audio recording/transcription
- Event processing
- TTS monitoring

State Management:
- IDLE: Initial state
- LISTENING: Waiting for user input
- PROCESSING: Generating response
- SPEAKING: Playing audio response
- STOPPED: System shutdown
"""

import os
from dotenv import load_dotenv
from transcription import AudioTranscriber
from llm import ResponseGenerator
from tts import TextToSpeechHandler
from timing_utils import ProcessTimer
from colorama import Fore
from threading import Thread, Event, Lock
from queue import Queue, Empty
import time
import speech_recognition as sr
from io import BytesIO
from states import AssistantState
from events import AssistantEvent
import time

class VoiceAssistant:
    def __init__(self):
        load_dotenv()
        
        self.recognizer = sr.Recognizer()

        # Initialize components
        self.timer = ProcessTimer()

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.transcriber = AudioTranscriber(self.api_key, model='vosk', timer=self.timer)
        self.tts_handler = TextToSpeechHandler(provider_name="openai", timer=self.timer)
        self.llm = ResponseGenerator(provider='openai', timer=self.timer)

        # Event handling
        self.event_queue = Queue()
        self.state = AssistantState.IDLE
        self.state_lock = Lock()
        
        # Control flags
        self.running = True
        self.stop_event = Event()
        self.is_speaking = Event()

    def start(self):
        """
        Start the voice assistant system.
        Initializes and starts all worker threads:
        - Audio worker: Handles speech recognition
        - Event worker: Processes system events
        - TTS monitor: Monitors speech completion
        """
        try:
            print(f"{Fore.GREEN}Starting Voice Assistant...{Fore.RESET}")
            
            # Start worker threads
            self.audio_thread = Thread(target=self._audio_worker)
            self.event_thread = Thread(target=self._event_worker)
            self.tts_monitor_thread = Thread(target=self._monitor_tts_queue)
            
            self.audio_thread.start()
            self.event_thread.start()
            self.tts_monitor_thread.start()
            
            # Set initial state
            self.state = AssistantState.LISTENING
            
            # Wait for keyboard interrupt
            try:
                while not self.stop_event.is_set():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                self.stop()
                
        except Exception as e:
            print(f"{Fore.RED}Error starting assistant: {e}{Fore.RESET}")
            self.stop()

    def _audio_worker(self):
        """
        Audio processing thread.
        Continuously:
        1. Listens for audio input
        2. Transcribes speech to text
        3. Checks for stop commands
        4. Queues transcribed text for processing
        """

        with sr.Microphone() as source:
            print(f"{Fore.CYAN}Calibrating microphone...{Fore.RESET}")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            while not self.stop_event.is_set():
                try:
                    print(f"\n{Fore.CYAN}Listening... (State: {self.state}){Fore.RESET}")
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    
                    # Process audio regardless of state
                    wav_buffer = BytesIO(audio.get_wav_data())
                    text = self.transcriber.transcribe_buffer(wav_buffer)
                    
                    if text and text.strip():
                        text = text.strip().lower()
                        
                        # Always check for stop command
                        if any(stop_cmd in text for stop_cmd in 
                              ["stop", "stop.", "please stop", "stop please", "quiet", "be quiet", "shut up"]):
                            print(f"{Fore.YELLOW}Stop command detected: {text}{Fore.RESET}")
                            self._handle_stop_command()
                            continue
                        
                        # Only process non-stop commands if in LISTENING state
                        if self.state == AssistantState.LISTENING:
                            self.event_queue.put(AssistantEvent(
                                type="transcription",
                                data=text
                            ))
                        
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"{Fore.RED}Audio error: {e}{Fore.RESET}")
                    continue
                
    def _event_worker(self):
        """
        Event processing thread.
        Handles different types of system events:
        - transcription: New user input
        - tts_complete: Speech finished
        """

        while not self.stop_event.is_set():
            try:
                # Get next event
                event = self.event_queue.get(timeout=1)
                
                if event.type == "transcription":
                    self._handle_transcription(event.data)
                elif event.type == "tts_complete":
                    self._handle_tts_complete()
                    
            except Empty:
                continue
            except Exception as e:
                print(f"{Fore.RED}Event error: {e}{Fore.RESET}")
                self.state = AssistantState.LISTENING

    def _monitor_tts_queue(self):
        """
        TTS monitoring thread.
        Checks when speech generation and playback is complete.
        Uses multiple checks to ensure reliable completion detection.
        """
        while not self.stop_event.is_set():
            try:
                # Check if speaking is done
                if (self.state == AssistantState.SPEAKING and 
                    self.tts_handler.sentence_queue.empty() and 
                    self.tts_handler.audio_queue.empty() and 
                    not self.tts_handler.is_playing.is_set()):
                    
                    # Add delay to ensure playback is complete
                    time.sleep(0.5)
                    
                    # Double check queues are still empty
                    if (self.tts_handler.sentence_queue.empty() and 
                        self.tts_handler.audio_queue.empty() and 
                        not self.tts_handler.is_playing.is_set()):
                        
                        # Queue TTS completion event
                        self.event_queue.put(AssistantEvent(type="tts_complete"))
                    
                time.sleep(0.1)  # Prevent busy waiting
                
            except Exception as e:
                print(f"{Fore.RED}TTS monitor error: {e}{Fore.RESET}")


    def _handle_transcription(self, text: str):
        """
        Process transcribed user input.
        Generates LLM response and initiates speech synthesis.
        
        Args:
            text (str): Transcribed user speech
        """
        with self.state_lock:
            print(f"{Fore.GREEN}Transcription: {text}{Fore.RESET}")
            
            # Only process if in LISTENING state
            if self.state == AssistantState.LISTENING:
                self.state = AssistantState.PROCESSING
                
                try:
                    # Generate response
                    print(f"\n{Fore.CYAN}Generating response...{Fore.RESET}")
                    sentence_queue = self.tts_handler.sentence_queue
                    self.llm.process_response(text, sentence_queue)
                    
                    # Move to speaking state
                    self.state = AssistantState.SPEAKING
                    self.is_speaking.set()
                    
                except Exception as e:
                    print(f"{Fore.RED}Processing error: {e}{Fore.RESET}")
                    self.state = AssistantState.LISTENING
                    self.is_speaking.clear()


    def _handle_stop_command(self):
        """
        Handle stop command from user.
        Stops current speech and clears all pending responses.
        """
        print(f"{Fore.YELLOW}Stop command received - stopping all speech...{Fore.RESET}")
        
        with self.state_lock:
            try:
                # Stop current playback
                import sounddevice as sd
                sd.stop()
                
                # Stop TTS and clear queues
                self.tts_handler.clear_queues()
                self.clear_queues()
                
                # Reset flags and state
                self.is_speaking.clear()
                self.state = AssistantState.LISTENING
                
                print(f"{Fore.GREEN}Successfully stopped all speech{Fore.RESET}")
                
            except Exception as e:
                print(f"{Fore.RED}Error in stop command: {str(e)}{Fore.RESET}")

    def _handle_tts_complete(self):
        """
        Handle completion of speech output.
        Prints timing metrics and prepares for next interaction.
        """

        with self.state_lock:
            if self.state == AssistantState.SPEAKING:
                print(f"{Fore.GREEN}TTS complete, changing state to LISTENING{Fore.RESET}")
                # Print timing metrics after processing is complete
                self.timer.print_metrics()
                self.clear_queues()  # Clear any pending audio
                self.is_speaking.clear()
                self.state = AssistantState.LISTENING
                time.sleep(0.5)  # Small delay before listening again

    def clear_queues(self):
        """
        Clear all system queues.
        Removes pending events and audio to be played.
        """

        print(f"{Fore.YELLOW}Clearing all queues...{Fore.RESET}")
        
        # Clear event queue
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except Empty:
                break
            
        # Clear TTS queues and stop playback
        self.tts_handler.clear_queues()
        
        print(f"{Fore.GREEN}All queues cleared{Fore.RESET}")

    def stop(self):
        """
        Shutdown the voice assistant.
        Stops all threads and cleans up resources.
        """
        print(f"\n{Fore.YELLOW}Stopping assistant...{Fore.RESET}")
        self.stop_event.set()
        self.clear_queues()
        
        if hasattr(self, 'audio_thread'):
            self.audio_thread.join()
        if hasattr(self, 'event_thread'):
            self.event_thread.join()
            
        print(f"{Fore.GREEN}Assistant stopped{Fore.RESET}")
