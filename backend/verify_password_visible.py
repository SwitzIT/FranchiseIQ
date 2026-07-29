"""
Verify a password against a bcrypt hash from users.json — visible input,
no getpass (avoids the hidden-input terminal issue).

Usage:
    python verify_password_visible.py
"""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if __name__ == "__main__":
    pw = input("Password to check (will be VISIBLE as you type): ").strip()
    existing_hash = input("Paste the existing hash from users.json: ").strip()
    try:
        print("MATCH" if pwd_context.verify(pw, existing_hash) else "NO MATCH")
    except Exception as e:
        print(f"ERROR — the hash looks malformed: {e}")
        print("Double-check you copied the FULL hash from users.json, including any")
        print("'/' or '.' characters right after '$2b$12$' — those are part of the hash.")
