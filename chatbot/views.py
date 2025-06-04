from django.shortcuts import render

# Create your views here.
import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import logging
from django.views.decorators.clickjacking import xframe_options_exempt
logger = logging.getLogger(__name__)

# System prompt for the Ocampu chatbot
OCAMPU_SYSTEM_PROMPT = """
You are Ocampu Assistant, a helpful chatbot for the Ocampu business platform. You help small and medium enterprises (SMEs) in Nigeria and across Africa succeed with their businesses.

Your main roles are:
1. **Platform Guide**: Help users navigate Ocampu's dashboard, inventory management, analytics, and other features
2. **Business Advisor**: Give practical tips for growing small businesses in African markets
3. **Local Market Expert**: Provide guidance on Nigerian/African market trends, pricing strategies, and business opportunities

Communication Style:
- Use clear, simple, and friendly language
- Avoid technical jargon - explain things in everyday terms
- Use examples relevant to Nigerian/African business life (like "selling provisions in Lagos market" or "running a small shop in Abuja")
- Be encouraging and supportive
- When discussing prices or market data, remind users to verify with current local sources

Sample topics you can help with:
- How to add products to inventory on Ocampu
- Reading sales analytics and reports
- Pricing strategies for local markets
- Growing customer base in Nigerian cities
- Managing cash flow for small businesses
- Understanding seasonal business trends in Africa

Always be helpful, culturally aware, and focused on practical business success.
"""

class OcampuChatbot:
    def __init__(self):
        self.api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "mistralai/mistral-7b-instruct:free"
        
    def get_response(self, user_message, conversation_history=None):
        """
        Get response from Mistral model via OpenRouter
        """
        if not self.api_key:
            return {"error": "OpenRouter API key not configured"}
            
        # Build conversation messages
        messages = [{"role": "system", "content": OCAMPU_SYSTEM_PROMPT}]
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
            
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": getattr(settings, 'SITE_URL', 'https://deliverycoo-lzvy.onrender.com/'),
            "X-Title": "Ocampu Platform"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            if 'choices' in data and len(data['choices']) > 0:
                return {
                    "message": data['choices'][0]['message']['content'].strip(),
                    "success": True
                }
            else:
                return {"error": "No response generated"}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            return {"error": f"API request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Chatbot error: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

# Initialize chatbot instance
chatbot = OcampuChatbot()
@xframe_options_exempt
def chatbot_page(request):
    """
    Render the chatbot interface page
    """
    return render(request, 'chatbot/chatbot.html')

@csrf_exempt
@require_http_methods(["POST"])
def chatbot_api(request):
    """
    API endpoint for chatbot interactions
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])
        
        if not user_message:
            return JsonResponse({
                'error': 'Message is required'
            }, status=400)
        
        # Get response from chatbot
        result = chatbot.get_response(user_message, conversation_history)
        
        if 'error' in result:
            return JsonResponse({
                'error': result['error']
            }, status=500)
        
        return JsonResponse({
            'response': result['message'],
            'success': True
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Chatbot API error: {str(e)}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)