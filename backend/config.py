import os

def load_env_file(env_path: str = None):
    """
    Lightweight zero-dependency .env loader using Python stdlib.
    Loads environment variables from .env file into os.environ if not already present.
    """
    if env_path is None:
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(root_dir, ".env")
        
    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                # Set in os.environ if not already defined
                if key and not os.environ.get(key):
                    os.environ[key] = val
    except Exception as e:
        print(f"[CONFIG ENV LOAD WARNING]: {e}")

# Automatically load .env on import
load_env_file()
