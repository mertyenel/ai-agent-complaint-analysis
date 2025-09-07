import google.generativeai as genai
from typing import Dict
from config import Config

class LLMClient:
    def __init__(self):
        if not Config.GOOGLE_API_KEY:
            raise ValueError("Google API key bulunamadı!")
        
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def generate_content(self, prompt: str) -> str:
        """LLM'ye prompt gönder ve yanıt al"""
        try:
            
            response = self.model.generate_content(prompt)
            
            if response and response.text:
                return response.text.strip()
            else:
                return ""
                
        except Exception as e:
            raise