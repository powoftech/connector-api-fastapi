import re

from pydantic import EmailStr, validate_email


def email_validator(email: EmailStr):
    lowercase_email = email.lower()
    _, normalized_email = validate_email(lowercase_email)
    domain = normalized_email.split("@")[1]

    BLACKLISTED_DOMAINS = ["example.com"]

    if domain in BLACKLISTED_DOMAINS:
        raise ValueError("Email domain not allowed")

    return email


def username_validator(username: str):
    lowercase_username = username.lower()

    if len(lowercase_username) < 3 or len(lowercase_username) > 30:
        raise ValueError("Username must be between 3 and 30 characters")

    regex = r"^[a-zA-Z0-9_]+$"

    BLACKLISTED_USERNAMES = [
        "api",
        "login",
        "for-you",
        "following",
        "liked",
        "saved",
        "search",
        "activity",
        "notifications",
        "messages",
        "accounts",
        "settings",
        "insights",
    ]

    # Check if username contains only letters, numbers, and underscores
    if not re.match(regex, lowercase_username):
        raise ValueError("Username must contain only letters, numbers, and underscores")

    # Check if username contains at least one letter
    if not any(char.isalpha() for char in username):
        raise ValueError("Username must contain at least one letter")

    if lowercase_username in BLACKLISTED_USERNAMES:
        raise ValueError("Username is not allowed")

    return username


def name_validator(name: str):
    if len(name) < 2:
        raise ValueError("Name must be at least 2 characters long")
    return name
