"""
Password-hash helper that avoids getpass entirely — some terminals
(certain VS Code/Windows Terminal/PowerShell configurations) don't
support getpass's hidden-input mechanism properly, causing it to hang or
silently ignore keystrokes. This version uses plain input(), so your
password IS visible on screen as you type — fine for a one-time local
setup step, just don't run this with anyone looking over your shoulder,
and don't leave the terminal history sitting on screen afterward.

Usage:
    python generate_password_hash_visible.py
"""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if __name__ == "__main__":
    pw = input("Password to hash (will be VISIBLE as you type): ").strip()
    if not pw:
        print("Empty input — nothing to hash.")
    else:
        print("\nPaste this as the \"password\" value in users.json:\n")
        print(pwd_context.hash(pw))
        print("\n(Clear your terminal scrollback now if anyone else can see this screen: 'cls')")
