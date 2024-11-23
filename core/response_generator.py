import os
import time
from utils.sentence_processor import SentenceProcessor
from colorama import Fore
from utils.llm_providers import BaseLLMProvider, OpenAIProvider, GroqProvider
from config.logging import get_logger
from utils.queue_manager import QueueManager

logger = get_logger(__name__)

class ResponseGenerator:
    """Main class for handling LLM responses"""
    
    def __init__(self,connection_manager, provider: str = "groq"):
        self.provider = self._initialize_provider(provider)
        self.queue_manager = QueueManager(connection_manager)
        
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
    
    async def process_response(self, text: str, user_id: str) -> None:
        """Process streaming response and add complete sentences to queue"""
        try:
            processor = SentenceProcessor()
            full_response = []

            # Process streaming response
            for chunk in self.provider.generate_response_stream(text):
                full_response.append(chunk)
                
                # Process chunk into sentences
                sentences = processor.process_chunk(chunk)
                
                # Add complete sentences to queue
                for sentence in sentences:
                    logger.info(f"{Fore.GREEN}Send sentence for TTS: {sentence}{Fore.RESET}")
                    # Push message to redis queue
                    await self.queue_manager.put(user_id, {
                        "type": "sentence",
                        "content": sentence,
                        "timestamp": int(time.time())
                    })
                    
            
            # Handle any remaining complete sentence
            remaining = processor.get_remaining()
            if remaining:
                logger.info(f"{Fore.GREEN}Send final sentence: {remaining}{Fore.RESET}")
                # Push message to redis queue
                await self.queue_manager.put(user_id, {
                    "type": "sentence",
                    "content": remaining,
                    "timestamp": int(time.time())
                })
                
                
            
            logger.info(f"{Fore.GREEN}Complete response: {''.join(full_response)}{Fore.RESET}")
            
        except Exception as e:
            logger.error(f"{Fore.RED}Error generating response: {str(e)}{Fore.RESET}")