from app.core.config import get_settings

def main():
    settings = get_settings()
    print("=" * 80)
    print("CONFIG VERIFICATION")
    print("=" * 80)
    
    # Check secret key
    print(f"SECRET_KEY is set and long enough? {len(settings.secret_key) >= 32} (length: {len(settings.secret_key)})")
    
    # Check password hashes
    print(f"DASHBOARD_PASSWORD_HASH is set? {bool(settings.dashboard_password_hash.strip())}")
    print(f"DASHBOARD_CONTROL_PASSWORD_HASH is set? {bool(settings.dashboard_control_password_hash.strip())}")
    
    # Check trusted origins/hosts
    print(f"TRUSTED_ORIGINS: {settings.trusted_origins}")
    print(f"TRUSTED_HOSTS: {settings.trusted_hosts}")
    
    print("=" * 80)
    print("Configuration looks valid!")

if __name__ == "__main__":
    main()
