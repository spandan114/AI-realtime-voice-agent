import os
import re
from queue import Queue
from typing import Generator, Optional, Set
from timing_utils import time_process
from abc import ABC, abstractmethod
from openai import OpenAI
from groq import Groq
from colorama import Fore

class SentenceProcessor:
    """Helper class to process streaming text into complete sentences"""
    
    def __init__(self):
        self.buffer = ""
        # More comprehensive sentence ending pattern
        self.sentence_end_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$')
        self.processed_sentences: Set[str] = set()  # Track processed sentences
        
    def _clean_sentence(self, sentence: str) -> str:
        """Clean and normalize a sentence"""
        # Remove extra whitespace and normalize
        cleaned = ' '.join(sentence.split())
        # Ensure the sentence has proper ending punctuation
        if cleaned and cleaned[-1] not in '.!?':
            cleaned += '.'
        return cleaned
    
    def _is_complete_sentence(self, text: str) -> bool:
        """Check if text forms a complete sentence"""
        # Basic checks for sentence completeness
        if not text:
            return False
        
        # Check for proper sentence structure (starts with capital, ends with punctuation)
        has_proper_start = text[0].isupper() if text else False
        has_proper_end = text[-1] in '.!?' if text else False
        min_word_count = len(text.split()) >= 2  # At least 2 words
        
        return has_proper_start and has_proper_end and min_word_count
    
    def process_chunk(self, text: str) -> list[str]:
        """Process a chunk of text and return complete, unique sentences"""
        self.buffer += text
        sentences = []
        
        # Split buffer into potential sentences
        potential_sentences = self.sentence_end_pattern.split(self.buffer)
        
        # If we have multiple potential sentences
        if len(potential_sentences) > 1:
            # Process all but the last piece (which might be incomplete)
            complete_sentences = potential_sentences[:-1]
            self.buffer = potential_sentences[-1]
            
            for sentence in complete_sentences:
                cleaned_sentence = self._clean_sentence(sentence)
                if (self._is_complete_sentence(cleaned_sentence) and 
                    cleaned_sentence not in self.processed_sentences):
                    sentences.append(cleaned_sentence)
                    self.processed_sentences.add(cleaned_sentence)
                    print(f"{Fore.CYAN}New complete sentence detected: {cleaned_sentence}{Fore.RESET}")
        else:
            # Check if our single buffer is a complete sentence
            if text.strip() and self._is_complete_sentence(self.buffer):
                cleaned_sentence = self._clean_sentence(self.buffer)
                if cleaned_sentence not in self.processed_sentences:
                    sentences.append(cleaned_sentence)
                    self.processed_sentences.add(cleaned_sentence)
                    self.buffer = ""
                    print(f"{Fore.CYAN}New complete sentence detected: {cleaned_sentence}{Fore.RESET}")
        
        return sentences
    
    def get_remaining(self) -> Optional[str]:
        """Get any remaining text in buffer if it forms a complete sentence"""
        if self.buffer:
            cleaned_buffer = self._clean_sentence(self.buffer)
            if (self._is_complete_sentence(cleaned_buffer) and 
                cleaned_buffer not in self.processed_sentences):
                self.buffer = ""
                self.processed_sentences.add(cleaned_buffer)
                return cleaned_buffer
        return None

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
                    {"role": "system", "content": "You are a helpful voice assistant. Keep responses concise and natural. Always use complete sentences with proper punctuation."},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
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
                    {"role": "system", "content": "You are a helpful voice assistant. Keep responses concise and natural. Always use complete sentences with proper punctuation."},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
                max_tokens=150,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"{Fore.RED}Groq Error: {str(e)}{Fore.RESET}")
            yield "I encountered an error processing your request."

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
    def process_response(self, text: str, sentence_queue: Queue) -> None:
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
                    sentence_queue.put(sentence)
            
            # Handle any remaining complete sentence
            remaining = processor.get_remaining()
            if remaining:
                print(f"\n{Fore.GREEN}Queueing final sentence: {remaining}{Fore.RESET}")
                sentence_queue.put(remaining)
            
            print(f"\n{Fore.GREEN}Complete response: {''.join(full_response)}{Fore.RESET}")
            
        except Exception as e:
            print(f"{Fore.RED}Error generating response: {str(e)}{Fore.RESET}")
            sentence_queue.put("I encountered an error processing your request.")