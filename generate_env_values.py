import secrets
import bcrypt
from dotenv import load_dotenv
import os

def get_bcrypt_hash(password: str) -> str:
    # Encode password to bytes
    password_bytes = password.encode("utf-8")
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    # Return as string
    return hashed.decode("utf-8")

def main():
    # 1. Generate cryptographically secure SECRET_KEY (64 chars, more than enough)
    secret_key = secrets.token_urlsafe(48)  # gives ~64 chars
    
    # 2. Load current env to get passwords
    load_dotenv()
    admin_password = os.getenv("DASHBOARD_ADMIN_PASSWORD", "psyger-0")
    control_password = os.getenv("DASHBOARD_CONTROL_PASSWORD", "psyger-100")
    
    # 3. Generate bcrypt hashes
    admin_hash = get_bcrypt_hash(admin_password)
    control_hash = get_bcrypt_hash(control_password)
    
    # Print everything
    print("=" * 80)
    print("GENERATED VALUES")
    print("=" * 80)
    print(f"SECRET_KEY={secret_key}")
    print(f"DASHBOARD_PASSWORD_HASH={admin_hash}")
    print(f"DASHBOARD_CONTROL_PASSWORD_HASH={control_hash}")
    print("=" * 80)
    print("NOTE: For SESSION_STRING, run generate_session.py (requires manual Telegram login)!")

if __name__ == "__main__":
    main()
