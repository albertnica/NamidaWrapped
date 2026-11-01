"""
NamidaWrapped Setup Wizard Root Entrypoint.
Delegates to src.setup_wizard.main().
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.setup_wizard import main

if __name__ == "__main__":
    main()

