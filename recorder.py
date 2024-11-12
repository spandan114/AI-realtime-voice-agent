import speech_recognition as sr
from colorama import Fore, init
from io import BytesIO
from queue import Queue
from threading import Thread, Event
from pydub import AudioSegment 

# Initialize colorama
init()

class AudioProcessor:
    def __init__(self, transcriber):
        print(f"{Fore.GREEN}Initializing Audio Processor...{Fore.RESET}")
        
        self.transcriber = transcriber
        self.recognizer = sr.Recognizer()
        
        # More lenient thresholds
        self.recognizer.energy_threshold = 1000      # Lower for easier detection
        self.recognizer.pause_threshold = 0.5        # Shorter pause
        self.recognizer.phrase_threshold = 0.2       # Shorter minimum speaking time
        self.recognizer.non_speaking_duration = 0.4  # Shorter silence time
        self.recognizer.dynamic_energy_threshold = True
        
        # Lower minimum volume threshold
        self.min_volume_threshold = 200  # Lower minimum RMS
        self.background_noise_level = None

        self.is_recording = False
        self.full_transcription = []
        self.transcription_queue = Queue()
        self.stop_event = Event()
        
    def is_valid_audio(self, audio_segment):
        """Check if audio segment contains valid speech"""
        try:
            duration = len(audio_segment) / 1000.0  # Convert to seconds
            rms = audio_segment.rms
            
            print(f"\n{Fore.CYAN}=== Audio Analysis ==={Fore.RESET}")
            # print(f"Duration: {duration:.2f} seconds")
            # print(f"Volume (RMS): {rms}")
            # print(f"Background Level: {self.background_noise_level}")
            # print(f"Energy Threshold: {self.recognizer.energy_threshold}")
            
            # More lenient validation
            if duration < 0.2:  # Shorter minimum duration
                print(f"{Fore.YELLOW}Audio too short: {duration:.2f}s{Fore.RESET}")
                return False
                
            if rms < self.min_volume_threshold:
                print(f"{Fore.YELLOW}Volume too low: {rms}{Fore.RESET}")
                return False
            
            print(f"{Fore.GREEN}Audio validation passed{Fore.RESET}")
            return True
            
        except Exception as e:
            print(f"{Fore.RED}Error checking audio: {str(e)}{Fore.RESET}")
            return False

    def record_and_process(self):
        try:
            with sr.Microphone() as source:
                print(f"{Fore.YELLOW}Calibrating for ambient noise...{Fore.RESET}")
                # Longer calibration
                self.recognizer.adjust_for_ambient_noise(source, duration=3)
                
                # Store background noise level
                self.background_noise_level = self.recognizer.energy_threshold
                print(f"{Fore.GREEN}Background noise level: {self.background_noise_level}{Fore.RESET}")
                
                # Set threshold higher than background
                self.recognizer.energy_threshold = self.background_noise_level * 2
                print(f"{Fore.GREEN}Speech detection threshold: {self.recognizer.energy_threshold}{Fore.RESET}")

                while not self.stop_event.is_set():
                    try:
                        print(f"\n{Fore.CYAN}Listening...{Fore.RESET}")
                        
                        audio_data = self.recognizer.listen(
                            source,
                            timeout=10,
                            phrase_time_limit=10
                        )
                        
                        # Convert to AudioSegment for analysis
                        wav_buffer = BytesIO(audio_data.get_wav_data())
                        audio_segment = AudioSegment.from_wav(wav_buffer)
                        
                        # Validate audio before processing
                        if not self.is_valid_audio(audio_segment):
                            continue
                        
                        # Reset buffer for transcription
                        wav_buffer.seek(0)
                        
                        try:
                            transcription = self.transcriber.transcribe_buffer(wav_buffer)
                            
                            # Additional validation of transcription
                            if transcription and transcription.strip():
                                self.full_transcription.append(transcription.strip())
                                print(f"{Fore.GREEN}Current: {transcription}{Fore.RESET}")
                                # Add transcription to queue for processing
                                self.transcription_queue.put(transcription.strip())
                                # # Filter out common noise transcriptions
                                # noise_phrases = [".", "...", "um", "uh", "hmm", "background noise"]
                                # if any(phrase in transcription.lower() for phrase in noise_phrases):
                                #     print(f"{Fore.YELLOW}Filtered noise transcription: {transcription}{Fore.RESET}")
                                #     continue
                                
                                # print(f"{Fore.GREEN}Speech detected: {transcription}{Fore.RESET}")
                                # self.full_transcription.append(transcription.strip())
                                # self.transcription_queue.put(transcription.strip())
                            else:
                                print(f"{Fore.YELLOW}No valid transcription generated{Fore.RESET}")
                                
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