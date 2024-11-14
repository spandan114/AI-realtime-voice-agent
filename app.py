import os
from dotenv import load_dotenv
from recorder import AudioProcessor
from transcription import AudioTranscriber
from llm import ResponseGenerator
from tts import TextToSpeechHandler
from timing_utils import ProcessTimer
import colorama
from colorama import Fore
from threading import Thread, Event
from queue import Empty
import time


class AssistantManager:
    def __init__(self):
        load_dotenv()

        self.timer = ProcessTimer()

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.transcriber = AudioTranscriber(self.api_key, model='vosk', timer=self.timer)
        self.response_generator = ResponseGenerator(provider='openai', timer=self.timer)  # Supported providers: 'openai' or 'groq'
        self.processor = AudioProcessor(transcriber=self.transcriber)
        self.tts_handler = TextToSpeechHandler(provider_name="openai", timer=self.timer)
        self.stop_event = Event()
        self.is_processing = False

    def process_transcriptions(self, transcription_queue):
        """Process transcriptions from queue and generate responses"""
        while not self.stop_event.is_set():
            try:
                # Non-blocking queue check
                transcription = transcription_queue.get(timeout=1)
                
                if transcription:
                    # Set processing flag
                    self.is_processing = True
                    
                    # Generate response
                    print(f"\n{Fore.CYAN}=== Generating Response for: {transcription} ==={Fore.RESET}")
                    try:

                        # response = self.response_generator.get_response(transcription)

                        # print(f"\n{Fore.GREEN}=== AI Response ==={Fore.RESET}")
                        # print(f"{Fore.YELLOW}{response}{Fore.RESET}")

                        # Convert response to speech
                        # self.tts_handler.speak(response)

                        # Get the TTS sentence queue from your TTS handler
                        sentence_queue = self.tts_handler.sentence_queue
                        
                        # Process response and send sentences directly to TTS
                        self.response_generator.process_response(transcription, sentence_queue)
                    

                        # Print timing metrics after processing is complete
                        self.timer.print_metrics()

                    except Exception as e:
                        print(f"{Fore.RED}Error generating response: {str(e)}{Fore.RESET}")
                    
                    # Clear processing flag
                    self.is_processing = False
                    
            except Empty:
                # No transcription available, continue waiting
                continue
            except Exception as e:
                print(f"{Fore.RED}Error processing transcription: {str(e)}{Fore.RESET}")

    def start(self):
        """Start the assistant"""
        try:
            # Start audio processing and get transcription queue
            transcription_queue = self.processor.start()
            
            # Start processing thread
            processing_thread = Thread(target=self.process_transcriptions, args=(transcription_queue,))
            processing_thread.start()
            
            # Wait for keyboard interrupt
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\nReceived KeyboardInterrupt...")
                self.stop()
                processing_thread.join()
                
        except Exception as e:
            print(f"{colorama.Fore.RED}Error: {str(e)}{colorama.Fore.RESET}")
            self.stop()

    def stop(self):
        """Stop all processes"""
        self.stop_event.set()
        self.processor.stop()
        self.tts_handler.stop()

def main():
    assistant = AssistantManager()
    assistant.start()

if __name__ == "__main__":
    main()