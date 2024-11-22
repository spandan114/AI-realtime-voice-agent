from typing import Generator
from abc import ABC, abstractmethod
from openai import OpenAI
from groq import Groq
from colorama import Fore


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate_response_stream(self, text: str) -> Generator[str, None, None]:
        """Generate streaming response from input text"""
        pass

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
    def generate_response_stream(self, text: str) -> Generator[str, None, None]:
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": """You are a natural conversational AI assistant. Follow these rules:
            - Use contractions and informal language (I'm, don't, let's)
            - Keep responses brief (1-2 sentences when possible)
            - Include conversational fillers sparingly ("well", "you know", "hmm")
            - Use dynamic intonation markers (? ! ...)
            - Express empathy and personality through tone
            - Break complex information into digestible chunks
            - Adapt speaking style to match user's formality level"""},
                    {"role": "user", "content": text}
                ],
                temperature=0.8,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"{Fore.RED}OpenAI Error: {str(e)}{Fore.RESET}")
            yield "I encountered an error processing your request."

class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "mixtral-8x7b-32768"):
        self.client = Groq(api_key=api_key)
        self.model = model
        
    def generate_response_stream(self, text: str) -> Generator[str, None, None]:
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": """You are a natural conversational AI assistant. Follow these rules:
            - Use contractions and informal language (I'm, don't, let's)
            - Keep responses brief (1-2 sentences when possible)
            - Include conversational fillers sparingly ("well", "you know", "hmm")
            - Use dynamic intonation markers (? ! ...)
            - Express empathy and personality through tone
            - Break complex information into digestible chunks
            - Adapt speaking style to match user's formality level"""},
                    {"role": "user", "content": text}
                ],
                temperature=0.8,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"{Fore.RED}Groq Error: {str(e)}{Fore.RESET}")
            yield "I encountered an error processing your request."
