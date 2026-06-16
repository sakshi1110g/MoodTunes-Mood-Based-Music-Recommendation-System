import os
import secrets

# Generate a secure secret key
secret_key = secrets.token_hex(16)  # 16 bytes = 32 characters
print(secret_key)