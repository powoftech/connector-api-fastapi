import re

from pydantic import EmailStr, validate_email


def email_validator(email: EmailStr):
    _, normalized_email = validate_email(email.lower())
    domain = normalized_email.split("@")[1]

    BLACKLISTED_DOMAINS = ["example.com"]

    if domain in BLACKLISTED_DOMAINS:
        raise ValueError("Email domain not allowed")

    return email


def username_validator(username: str):
    if len(username) < 3 or len(username) > 30:
        raise ValueError("Username must be between 3 and 30 characters")

    regex = r"^[a-zA-Z0-9_]+$"

    # Check if username contains only letters, numbers, and underscores
    if not re.match(regex, username):
        raise ValueError("Username must contain only letters, numbers, and underscores")

    # Check if username contains at least one letter
    if not any(char.isalpha() for char in username):
        raise ValueError("Username must contain at least one letter")

    return username

def name_validator(name: str):
    if len(name) < 2:
        raise ValueError("Name must be at least 2 characters long")
    return name
