def sanitize(value):\n    return value.strip().replace('<', '').replace('>', '')
