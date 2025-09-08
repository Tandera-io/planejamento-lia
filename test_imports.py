#!/usr/bin/env python3
"""Test script to verify all imports work correctly"""

def test_imports():
    try:
        print("Testing main app import...")
        from main import app
        print("✅ Main app imports successfully")
        
        print("Testing planning router import...")
        from api.routes.planejamento import router
        print("✅ Planning router imports successfully")
        
        print("Testing supabase service import...")
        from services.supabase_service import get_supabase_client
        print("✅ Supabase service imports successfully")
        
        print("Testing auth service import...")
        from api.routes.auth import get_current_user
        print("✅ Auth service imports successfully")
        
        print("Testing openai service import...")
        from services.openai_service import gpt_4_completion
        print("✅ OpenAI service imports successfully")
        
        print("🎉 All core imports working!")
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()
