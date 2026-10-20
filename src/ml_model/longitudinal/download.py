"""Download publisher metadata only; raw TCGA pixels require controlled access."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
FILES = {
    "lumiere": {
        "LUMIERE-Demographics_Pathology.csv": "https://ndownloader.figshare.com/files/37575637",
        "LUMIERE-datacompleteness.csv": "https://ndownloader.figshare.com/files/37575523",
        "LUMIERE-MRinfo.csv": "https://ndownloader.figshare.com/files/37691442",
        "LUMIERE-pyradiomics-deepbratumia-features.csv": "https://ndownloader.figshare.com/files/37681080",
        "LUMIERE-readme.pdf": "https://ndownloader.figshare.com/files/37983597",
    },
    "tcga": {
        "TCIA_TCGA-GBM_09-16-2015-nbia-digest.xlsx": "https://www.cancerimagingarchive.net/wp-content/uploads/TCIA_TCGA-GBM_09-16-2015-nbia-digest.xlsx",
        "GC_manifest_TCGA-GBM_20260326.csv": "https://www.cancerimagingarchive.net/wp-content/uploads/GC_manifest_TCGA-GBM_20260326.csv",
    },
}


def download():
    manifest = []
    for cohort, files in FILES.items():
        folder = ROOT / "dataset/raw/longitudinal" / cohort
        folder.mkdir(parents=True, exist_ok=True)
        for name, url in files.items():
            path = folder / name
            if not path.exists():
                with urllib.request.urlopen(url, timeout=120) as response:
                    path.write_bytes(response.read())
            data = path.read_bytes()
            manifest.append(dict(cohort=cohort, name=name, url=url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    path = ROOT / "dataset/raw/longitudinal/manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    print(json.dumps(download(), indent=2))
