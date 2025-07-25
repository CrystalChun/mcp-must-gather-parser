import re
from typing import Union, Dict, Any

def sanitize_data(data: Union[str, Dict[str, Any]]) -> Union[str, Dict[str, Any]]:
    """
    Sanitizes sensitive data such as pull secrets, email addresses, SSH keys, IP addresses,
    DNS names, usernames, passwords, and certificates.
    
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
        
        # SSH key patterns (matches both public and private key formats)
        ssh_private_key_pattern = r'-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----[A-Za-z0-9\s/+=]+-----END (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----'
        ssh_public_key_pattern = r'ssh-(?:rsa|dss|ed25519)\s+[A-Za-z0-9/+=]+(?:\s+[\w@.-]+)?'
        
        # IPv4 pattern
        ipv4_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        
        # IPv6 pattern
        ipv6_pattern = r'\b(?:(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|:(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9]))\b'
        
        # DNS name pattern (matches domain names and hostnames)
        dns_pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        
        # Username pattern (common formats in logs and configs)
        username_pattern = r'\b(?:user(?:name)?|admin|root)[\s:=]+[\'"]*([a-zA-Z0-9_.-]+)[\'"]*'
        
        # Password pattern (common formats in logs and configs)
        password_pattern = r'\b(?:password|pwd|passwd)[\s:=]+[\'"]*([^\s\'"]+)[\'"]*'

        # Certificate patterns
        cert_patterns = {
            # X.509 Certificate
            'x509_cert': r'-----BEGIN CERTIFICATE-----[A-Za-z0-9\s/+=]+-----END CERTIFICATE-----',
            # Certificate Signing Request
            'csr': r'-----BEGIN CERTIFICATE REQUEST-----[A-Za-z0-9\s/+=]+-----END CERTIFICATE REQUEST-----',
            # Private key in PEM format (including encrypted)
            'private_key': r'-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----(?:.*?Proc-Type: 4,ENCRYPTED.*?)?[A-Za-z0-9\s/+=]+-----END (?:RSA |DSA |EC )?PRIVATE KEY-----',
            # Public key in PEM format
            'public_key': r'-----BEGIN PUBLIC KEY-----[A-Za-z0-9\s/+=]+-----END PUBLIC KEY-----',
            # PKCS#7/P7B certificate
            'pkcs7': r'-----BEGIN PKCS7-----[A-Za-z0-9\s/+=]+-----END PKCS7-----',
            # Certificate fingerprints (MD5, SHA-1, SHA-256)
            'fingerprint': r'\b(?:[0-9a-fA-F]{2}:){15}[0-9a-fA-F]{2}\b|\b(?:[0-9a-fA-F]{2}:){19}[0-9a-fA-F]{2}\b|\b(?:[0-9a-fA-F]{2}:){31}[0-9a-fA-F]{2}\b',
            # Certificate serial numbers
            'serial': r'\bcertificate serial number:?\s*([0-9a-fA-F:]+)\b'
        }
        
        # Replace sensitive data with redacted markers
        text = re.sub(email_pattern, '[REDACTED_EMAIL]', text)
        text = re.sub(pull_secret_pattern, '[REDACTED_PULL_SECRET]', text)
        text = re.sub(ssh_private_key_pattern, '[REDACTED_SSH_PRIVATE_KEY]', text)
        text = re.sub(ssh_public_key_pattern, '[REDACTED_SSH_PUBLIC_KEY]', text)
        text = re.sub(ipv4_pattern, '[REDACTED_IPV4]', text)
        text = re.sub(ipv6_pattern, '[REDACTED_IPV6]', text)
        text = re.sub(dns_pattern, '[REDACTED_DNS]', text)
        text = re.sub(username_pattern, r'username: [REDACTED_USERNAME]', text)
        text = re.sub(password_pattern, r'password: [REDACTED_PASSWORD]', text)
        
        # Replace certificate data
        for cert_type, pattern in cert_patterns.items():
            text = re.sub(pattern, f'[REDACTED_{cert_type.upper()}]', text, flags=re.DOTALL)
        
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
