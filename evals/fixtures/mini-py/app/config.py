import os

DATABASE_URL = os.environ["DATABASE_URL"]
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")
