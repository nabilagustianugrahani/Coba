import os
import sys
from pathlib import Path

# Add the ugc_ai_overpower directory to Python path
ugc_path = Path(__file__).parent.parent
sys.path.insert(0, str(ugc_path))

# Mock the patch function that's imported in conftest
import unittest.mock
sys.modules['unittest.mock'] = unittest.mock