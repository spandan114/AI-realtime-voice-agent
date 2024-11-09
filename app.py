import os
from dotenv import load_dotenv
load_dotenv()
from recorder import AudioProcessor
from transcription import AudioTranscriber
import colorama

def main():
    load_dotenv()
    api_key = os.getenv("DEEPGRAM_API_KEY")
    
    # Initialize transcriber
    transcriber = AudioTranscriber(api_key, model='deepgram')
    
    # Initialize audio processor
    processor = AudioProcessor(transcriber=transcriber)
    
    try:
        processor.start()
    except KeyboardInterrupt:
        print("\nReceived KeyboardInterrupt...")
    except Exception as e:
        print(f"{colorama.Fore.RED}Error: {str(e)}{colorama.Fore.RESET}")
    finally:
        processor.stop()

if __name__ == "__main__":
    main()