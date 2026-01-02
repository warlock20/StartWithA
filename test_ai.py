# test_ai_service.py
from app.services.ai import ai_service, get_ai_config, AIProvider

def test_ai_service():
    print("=== AI Service Test ===\n")
    
    # 1. Config
    config = get_ai_config()
    print(f"Gemini configured: {config.is_provider_available(AIProvider.GEMINI)}")
    print(f"Claude configured: {config.is_provider_available(AIProvider.CLAUDE)}")
    
    # 2. Service availability
    print(f"\nAI Service available: {ai_service.is_available()}")
    print(f"Available providers: {[p.value for p in ai_service.get_available_providers()]}")
    
    # 3. Quick generation test (if available)
    if ai_service.is_available():
        response = ai_service.generate("Say 'Hello' in one word.")
        print(f"\nTest generation: {response[:50]}...")
        print("\n✅ AI Service working!")
    else:
        print("\n⚠️ No API keys configured")

if __name__ == "__main__":
    test_ai_service()