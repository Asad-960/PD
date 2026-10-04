"""Start the local API with the repository's existing isolated dependencies."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if (ROOT / ".audit-deps").is_dir():
    sys.path.insert(0, str(ROOT / ".audit-deps"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("backend.api:app", host="127.0.0.1", port=args.port)
