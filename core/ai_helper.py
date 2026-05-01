import google.generativeai as genai
import os

def ask_gemini(prompt):
    # Lấy key Gemini từ biến môi trường GEMINI_API_KEY
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "Chưa cấu hình API Key!"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Lỗi AI: {str(e)}"