import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL: str = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_connection():
    try:
        result = supabase.table("entries").select("id").limit(1).execute()
        print(f"✓ Connected to Supabase — entries table accessible")
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()