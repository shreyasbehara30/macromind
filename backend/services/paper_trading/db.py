from supabase import create_client, Client
from core.config import settings

def get_supabase() -> Client:
    # Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to be set
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase credentials not configured in settings.")
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
