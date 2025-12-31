import os
from pathlib import Path
import pytest


# Load .env file from tests directory if it exists
def pytest_configure(config):
    """Load environment variables from tests/.env before running tests"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print(f"\n✅ Loading environment variables from {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
    else:
        print(f"\n⚠️  No .env file found at {env_file}")
        print("Integration tests will be skipped. Create tests/.env from tests/.env.example")
