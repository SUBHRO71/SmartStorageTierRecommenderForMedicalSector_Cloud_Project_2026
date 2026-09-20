"""Build the credential-free inference Lambda source bundle."""

from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DIST = HERE / "dist"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    for name in ("handler.py",):
        shutil.copy2(HERE / name, DIST / name)
    for name in ("decision_engine.py", "retrieval_policy_weights.json"):
        shutil.copy2(ROOT / "src" / "ml_model" / name, DIST / name)
    print(f"Lambda source bundle created at {DIST}")
    print("Install requirements into dist/ or attach boto3 through the Lambda runtime.")


if __name__ == "__main__":
    main()
