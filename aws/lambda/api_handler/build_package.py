"""Build the API Lambda source bundle without contacting AWS."""

from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DIST = HERE / "dist"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy2(HERE / "handler.py", DIST / "handler.py")
    for name in ("decision_engine.py", "retrieval_policy_weights.json"):
        shutil.copy2(ROOT / "src" / "ml_model" / name, DIST / name)
    print(f"API Lambda source bundle created at {DIST}")


if __name__ == "__main__":
    main()
