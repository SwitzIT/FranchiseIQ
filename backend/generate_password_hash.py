"""
Simpler alternative to generate_password_hash.py — no confirmation step,
just hashes whatever you type once. Use this if you keep hitting
"Passwords didn't match" due to hidden-input typos and want to move
faster.

Usage:
    python generate_password_hash_simple.py

Optional: verify a password against an existing hash from users.json
(useful to confirm you copied the hash correctly, or that a password you
remember actually matches what's stored):
    python generate_password_hash_simple.py --verify
"""
import sys
import getpass
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if __name__ == "__main__":
    if "--verify" in sys.argv:
        pw = getpass.getpass("Password to check: ")
        existing_hash = input("Paste the existing hash from users.json: ").strip()
        print("MATCH" if pwd_context.verify(pw, existing_hash) else "NO MATCH")
    else:
        pw = getpass.getpass("Password to hash: ")
        print("\nPaste this as the \"password\" value in users.json:\n")
        print(pwd_context.hash(pw))