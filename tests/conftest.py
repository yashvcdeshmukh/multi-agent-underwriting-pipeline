"""Pytest must not sleep on the agent retry backoff."""

import os

os.environ["UNDERWRITING_RETRY_BASE_SECONDS"] = "0"
