
import sys
import os
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath("."))

load_dotenv()

from src.crew import run_complaint_pipeline

try:
    result = run_complaint_pipeline(
        complaint_text="There is a big pathhole near my house for last 3 months no one taking any action",
        user_state="Andhra Pradesh"
    )
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
