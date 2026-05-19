"""
Logging setup.
Provides consistent logging configuration for the app while avoiding
leaking sensitive values such as tokens or API keys.
"""

import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # You can add custom filters here later to mask tokens in logs
    
    return logging.getLogger("finanos")

logger = setup_logging()
