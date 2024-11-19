import os
from utils.sentence_processor import SentenceProcessor
from colorama import Fore
from utils.llm_providers import BaseLLMProvider, OpenAIProvider, GroqProvider


class ResponseGenerator:
    """Main class for handling LLM responses"""
    
    def __init__(self, provider: str = "groq", timer=None):
        self.timer = timer
        self.provider = self._initialize_provider(provider)
        
    def _initialize_provider(self, provider: str) -> BaseLLMProvider:
        """Initialize the specified LLM provider"""
        providers = {
            "openai": (OpenAIProvider, "OPENAI_API_KEY"),
            "groq": (GroqProvider, "GROQ_API_KEY")
        }
        
        if provider not in providers:
            raise ValueError(f"Unsupported provider: {provider}")
            
        provider_class, api_key_name = providers[provider]
        api_key = os.getenv(api_key_name)
        
        if not api_key:
            raise ValueError(f"Missing API key for {provider}. Set {api_key_name} environment variable.")
            
        return provider_class(api_key)
    
    def process_response(self, text: str) -> None:
        """Process streaming response and add complete sentences to queue"""
        try:
            processor = SentenceProcessor()
            full_response = []
            
            # Process streaming response
            for chunk in self.provider.generate_response_stream(text):
                print(chunk, end='', flush=True)  # Display in real-time
                full_response.append(chunk)
                
                # Process chunk into sentences
                sentences = processor.process_chunk(chunk)
                
                # Add complete sentences to queue
                for sentence in sentences:
                    print(f"\n{Fore.GREEN}Queueing sentence for TTS: {sentence}{Fore.RESET}")
                    # sentence_queue.put(sentence)
            
            # Handle any remaining complete sentence
            remaining = processor.get_remaining()
            if remaining:
                print(f"\n{Fore.GREEN}Queueing final sentence: {remaining}{Fore.RESET}")
                # sentence_queue.put(remaining)
            
            print(f"\n{Fore.GREEN}Complete response: {''.join(full_response)}{Fore.RESET}")
            
        except Exception as e:
            print(f"{Fore.RED}Error generating response: {str(e)}{Fore.RESET}")
            # sentence_queue.put("I encountered an error processing your request.")