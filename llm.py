import os
from timing_utils import time_process
from abc import ABC, abstractmethod
from openai import OpenAI
from groq import Groq
from colorama import Fore

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate_response(self, text: str) -> str:
        """Generate response from input text"""
        pass

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
    def generate_response(self, text: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful voice assistant. Keep responses concise and natural."},
                    {"role": "user", "content": text}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"{Fore.RED}OpenAI Error: {str(e)}{Fore.RESET}")
            return "I encountered an error processing your request."

class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "mixtral-8x7b-32768"):
        self.client = Groq(api_key=api_key)
        self.model = model
        
    def generate_response(self, text: str) -> str:
        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful voice assistant. Keep responses concise and natural."},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
                max_tokens=150
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"{Fore.RED}Groq Error: {str(e)}{Fore.RESET}")
            return "I encountered an error processing your request."


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
    
    @time_process("response_generation")
    def get_response(self, text: str) -> str:
        """Generate response using the configured LLM provider"""
        try:
            response = self.provider.generate_response(text)
            print(f"{Fore.GREEN}Assistant: {response}{Fore.RESET}")
            return response
        except Exception as e:
            print(f"{Fore.RED}Error generating response: {str(e)}{Fore.RESET}")
            return "I encountered an error processing your request."