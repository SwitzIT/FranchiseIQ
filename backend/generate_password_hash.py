"""
Optional helper: generate a bcrypt hash to put in users.json instead of a
plaintext password.

Usage:
    python generate_password_hash.py
    (it will prompt for a password, and print the hash to paste into users.json)

Either plaintext or a bcrypt hash works in users.json — auth.py detects
which one it's looking at automatically (bcrypt hashes always start with
$2a$/$2b$/$2y$). Plaintext is simpler to manage by hand; hashing is more
secure if this file might ever be shared/committed/backed up somewhere you
don't fully control.
"""
import getpass
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if __name__ == "__main__":
    password = getpass.getpass("Password to hash: ")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        print("Passwords didn't match — try again.")
    else:
        print("\nPaste this as the \"password\" value in users.json:\n")
        print(pwd_context.hash(password))
