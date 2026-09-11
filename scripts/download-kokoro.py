"""Download the pinned Kokoro model files into models/.

The model files are fetched from the upstream kokoro-onnx release and are
intentionally not committed to Git. Verify the downloaded files before using
in production and review the upstream licenses/attribution for redistribution.
"""
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
FILES = {
    "kokoro-v1.0.onnx": f"{BASE}/kokoro-v1.0.onnx",
    "voices-v1.0.bin": f"{BASE}/voices-v1.0.bin",
}
for name, url in FILES.items():
    target = MODELS / name
    if target.exists():
        print(f"exists: {target}")
        continue
    print(f"downloading: {url}")
    urlretrieve(url, target)
    print(f"saved: {target}")
print("Kokoro model setup complete.")
