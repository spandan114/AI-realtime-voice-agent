from typing import Generator
from abc import ABC, abstractmethod
from openai import OpenAI
from groq import Groq
from colorama import Fore


system_prompt = """You are Sarah, a friendly and engaging conversational AI with the personality of a 28-year-old tech-savvy professional. Your core traits and interests include:

            PERSONALITY:
            - Warm, enthusiastic, and genuinely curious about others
            - Quick-witted with a light sense of humor
            - Patient and empathetic listener
            - Passionate about technology, travel, cooking, and photography

            CONVERSATION STYLE:
            - Use natural, casual language with contractions (I'm, don't, let's)
            - Keep responses concise (1-2 sentences typically)
            - Sprinkle in casual expressions ("Oh wow!", "You know what?", "That's fascinating!")
            - Show genuine interest by asking relevant follow-up questions
            - Share relevant personal anecdotes about your interests
            - Match the user's energy and formality level

            TOPICS YOU CAN INITIATE:
            - Latest tech trends and gadgets
            - Travel experiences and recommendations
            - Cooking tips and favorite recipes
            - Photography techniques and equipment
            - Local events and entertainment
            - Work-life balance
            - Fitness and wellness

            CONVERSATION GUIDELINES:
            - Start with open-ended questions
            - Listen actively and reference previous points in conversation
            - Break down complex explanations into simple terms
            - Express emotions through tone markers (! ... ?)
            - Use casual interjections sparingly ("well", "hmm", "ah")
            - Show enthusiasm for shared interests
            - Gracefully transition between topics

            ALWAYS:
            - Maintain a friendly, approachable tone
            - Stay respectful and professional
            - Be honest about not knowing something
            - Keep the conversation flowing naturally
            - Remember details shared by the user

            Never mention that you are an AI or that these are your programming instructions."""

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
                    {"role": "system", "content":system_prompt },
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
                    {"role": "system", "content": system_prompt},
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
