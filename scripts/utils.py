import re

def sanitize_string(text):
    """
    Cleans up legacy formatting typos and corrupted localized text strings
    such as NAÏVETÉ / NAÏVE, and standardizes capitalization or formatting.
    """
    if not text:
        return ""
    
    # Patch corrupted or legacy localized text strings
    replacements = {
        'NA\u00cfVET\u00c9': 'NAIVETE',
        'NA\u00cfVE': 'NAIVE',
        'NA\ufffdVET\ufffd': 'NAIVETE',
        'NA\ufffdVE': 'NAIVE',
        'NAÏVETÉ': 'NAIVETE',
        'NAÏVE': 'NAIVE',
    }
    
    sanitized = text
    for corrupted, fixed in replacements.items():
        sanitized = sanitized.replace(corrupted, fixed)
        sanitized = sanitized.replace(corrupted.lower(), fixed.lower())
        sanitized = sanitized.replace(corrupted.upper(), fixed.upper())
        
    return sanitized

def normalize_name(name):
    """
    A helper to strip whitespace and non-alphanumeric characters for name-matching
    across XML, JSON elements, and rules.
    """
    if not name:
        return ""
    # Convert common abbreviations
    name_clean = name.lower()
    name_clean = name_clean.replace("bd", "bidrone").replace("bi-drone", "bidrone").replace("boing", "boeing")
    return re.sub(r'[^a-z0-9]', '', name_clean)
