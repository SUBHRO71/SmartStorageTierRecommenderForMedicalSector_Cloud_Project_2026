"""Fetch a few permitted LUMIERE ZIP members using HTTP byte ranges.

The complete archive is 32 GB. Refuse servers ignoring Range, enforce a byte
budget, and extract only explicitly selected files into a new sample directory.
"""
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]
URL = "https://ndownloader.figshare.com/files/38249697"
SIZE = 32565467707


class RemoteZip(io.RawIOBase):
    def __init__(self, budget=100*1024**2):
        self.position, self.downloaded, self.budget = 0, 0, budget
        self.cache = {}

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position+offset if whence == 1 else SIZE+offset
        if self.position < 0: raise ValueError("Negative remote ZIP position")
        return self.position

    def read(self, length=-1):
        length = min(SIZE-self.position, length if length >= 0 else SIZE-self.position)
        if length <= 0: return b""
        start, end = self.position, self.position+length-1
        key = (start, end)
        if key not in self.cache:
            if self.downloaded+length > self.budget: raise ValueError("Sample download exceeds byte budget")
            request = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(request, timeout=120) as response:
                if response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/"):
                    raise ValueError("Publisher did not honor the requested range; full download refused")
                self.cache[key] = response.read(length+1)
                if len(self.cache[key]) != length: raise ValueError("Unexpected byte range length")
            self.downloaded += length
        self.position += length
        return self.cache[key]


def main():
    remote = RemoteZip()
    with zipfile.ZipFile(remote) as archive:
        names = archive.namelist()
        out = ROOT / "dataset/raw/longitudinal/lumiere"
        (out / "zip_members.json").write_text(json.dumps(names, indent=2))
        print('Members', len(names), 'index bytes downloaded', remote.downloaded)
        # Subject selected deterministically from the locked test split, without
        # inspecting future intervals or prediction quality.
        import pandas as pd
        rows = pd.read_json(ROOT / "dataset/processed/longitudinal/examples.json")
        demo = rows[(rows.cohort == "LUMIERE") & (rows.split == "test") & (rows.visit_index >= 3) & rows.log_mask_volume.notna()].sort_values(["subject", "day"]).iloc[0]
        matching = [n for n in names if f"{demo.subject}/{demo.timepoint}/" in n and "DeepBraTumIA-segmentation/atlas/skull_strip/" in n and n.endswith('.nii.gz')]
        selected = [n for n in matching if Path(n).name in ('ct1_skull_strip.nii.gz', 't1_skull_strip.nii.gz', 't2_skull_strip.nii.gz', 'flair_skull_strip.nii.gz')]
        print('Subject', demo.subject, 'timepoint', demo.timepoint, 'selected', selected, flush=True)
        if len(selected) != 4: raise ValueError('The deterministic sample does not contain four publisher-processed volumes')
        folder = out / "aws_sample"
        folder.mkdir(exist_ok=True)
        import hashlib
        manifest = []
        for name in selected:
            destination = folder / Path(name).name
            if not destination.exists(): destination.write_bytes(archive.read(name))
            data = destination.read_bytes()
            manifest.append(dict(member=name, name=destination.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            print(destination.name, len(data), flush=True)
        context = demo.to_dict()
        context.pop('next_days', None) # Future target never sent to the live model.
        context['manifest'] = manifest
        context['publisher_url'] = URL
        context['permission'] = 'LUMIERE publisher public release; non-commercial research pilot; no onward public image distribution'
        (folder / 'context.json').write_text(json.dumps(context, indent=2, default=lambda x: x.tolist()))
        print('Total transferred', remote.downloaded, flush=True)


if __name__ == '__main__': main()
