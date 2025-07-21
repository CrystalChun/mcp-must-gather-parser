import re
from typing import Union, Dict, Any

def sanitize_data(data: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    """
    Sanitizes sensitive data such as pull secrets and email addresses.
    
    Args:
        data: Input string or dictionary containing data to be sanitized
        
    Returns:
        Sanitized version of the input data with sensitive information redacted
    """
    def _sanitize_string(text: str) -> str:
        # Email pattern
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        # Pull secret pattern (matches base64 encoded data and common auth token formats)
        pull_secret_pattern = r'(?:eyJ[a-zA-Z0-9-_=]+\.eyJ[a-zA-Z0-9-_=]+\.[a-zA-Z0-9-_.+/=]+|[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+)'
        
        # Replace emails with [REDACTED_EMAIL]
        text = re.sub(email_pattern, '[REDACTED_EMAIL]', text)
        # Replace pull secrets with [REDACTED_PULL_SECRET]
        text = re.sub(pull_secret_pattern, '[REDACTED_PULL_SECRET]', text)
        
        return text

    if isinstance(data, str):
        return _sanitize_string(data)
    elif isinstance(data, dict):
        sanitized_dict = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized_dict[key] = _sanitize_string(value)
            elif isinstance(value, dict):
                sanitized_dict[key] = sanitize_data(value)
            else:
                sanitized_dict[key] = value
        return sanitized_dict
    else:
        return data
