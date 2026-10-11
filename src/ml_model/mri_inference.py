"""Frozen SegResNet adapter with pinned published weights and strict input gates."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

REVISION = "04689f51062d1ec889c8af2e78fc0369c6fda36d"  # MONAI bundle tag 0.5.4
EXPECTED_SHA256 = "860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae"
CACHE = Path(os.environ.get("MRI_BUNDLE_DIR", Path.home() / ".cache/cloudtier/brats-0.5.4"))
CHECKPOINT = CACHE / "models/model.pt"


def checkpoint_ready():
    return CHECKPOINT.is_file()


def download():
    from huggingface_hub import snapshot_download
    snapshot_download("MONAI/brats_mri_segmentation", revision=REVISION, local_dir=CACHE,
                      allow_patterns=["models/model.pt", "configs/metadata.json", "configs/inference.json", "docs/README.md", "LICENSE"])
    print(json.dumps({"checkpoint": str(CHECKPOINT), "revision": REVISION,
                      "sha256": hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()}, indent=2))


def load_network(device="cpu"):
    import torch
    from monai.networks.nets import SegResNet
    if hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Checkpoint checksum does not match the verified published bundle")
    network = SegResNet(blocks_down=[1, 2, 2, 4], blocks_up=[1, 1, 1], init_filters=16,
                        in_channels=4, out_channels=3, dropout_prob=0.2).to(device)
    weights = torch.load(CHECKPOINT, map_location=device, weights_only=True)
    network.load_state_dict(weights.get("model", weights.get("state_dict", weights)))
    network.eval()
    return network


def run_study(study):
    import nibabel as nib
    import numpy as np
    import torch
    import monai
    from monai.inferers import sliding_window_inference
    start = time.perf_counter()
    inputs = [next(o for o in study["objects"] if o["role"] == role) for role in ("T1ce", "T1", "T2", "FLAIR")]
    images = [nib.load(o["file"]) for o in inputs]
    reference = images[0]
    for image in images:
        if image.shape != reference.shape or not np.allclose(image.affine, reference.affine, atol=1e-4):
            raise ValueError("The four volumes must have matching dimensions and affine alignment")
        if not np.allclose(image.header.get_zooms()[:3], (1, 1, 1), atol=.01):
            raise ValueError("This checkpoint requires preprocessed 1 mm isotropic volumes")
        if max(image.shape) > 512 or np.prod(image.shape) > 256 ** 3:
            raise ValueError("The local worker accepts volumes up to 256 cubed voxels and 512 per axis")
    channels = []
    for image in images:
        values = image.get_fdata(dtype=np.float32)
        if not np.isfinite(values).all():
            raise ValueError("A volume contains non-finite intensities")
        mask = values != 0
        if mask.sum() < 8 or float(values[mask].std()) <= 1e-8:
            raise ValueError("A sequence is empty or has no intensity variation")
        values[mask] = (values[mask] - values[mask].mean()) / values[mask].std()
        channels.append(values)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    network = load_network(device)
    tensor = torch.as_tensor(np.stack(channels)[None], device=device)
    # Smaller CPU windows bound memory; the fully convolutional weights are unchanged.
    roi = (240, 240, 160) if device == "cuda" else (96, 96, 96)
    with torch.inference_mode():
        output = sliding_window_inference(tensor, roi, 1, network, overlap=.5)
        masks = (torch.sigmoid(output)[0] >= .5).cpu().numpy()
    masks[0] |= masks[2]
    masks[1] |= masks[0]
    destination = Path(inputs[0]["file"]).parent
    voxel_mL = abs(float(np.linalg.det(reference.affine[:3, :3]))) / 1000
    volumes = {}
    for channel, name in enumerate(("TC", "WT", "ET")):
        volumes[name] = round(float(masks[channel].sum()) * voxel_mL, 3)
        nib.save(nib.Nifti1Image(masks[channel].astype("uint8"), reference.affine), destination / f"prediction_{name}.nii.gz")
    return {"status": "READY", "model": "MONAI BraTS SegResNet 0.5.4", "revision": REVISION,
            "checkpoint_sha256": hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest(),
            "input_sha256": [o["sha256"] for o in inputs], "volumes_mL": volumes,
            "runtime_seconds": round(time.perf_counter() - start, 2), "device": device,
            "runtime_versions": {"monai": monai.__version__, "torch": torch.__version__},
            "roi": list(roi), "normalization": "channel-wise nonzero z-score", "threshold": .5,
            "postprocessing": "ET included in TC; TC included in WT, following priority-label semantics",
            "message": "Research segmentation. No diagnostic or retrieval probability output."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", help="Download pinned official checkpoint")
    parser.add_argument("--smoke-test", action="store_true", help="Check published weights with synthetic tensor; not clinical validation")
    args = parser.parse_args()
    if args.download:
        download()
    if args.smoke_test:
        import torch
        with torch.inference_mode():
            output = load_network()(torch.randn(1, 4, 32, 32, 32))
        print(json.dumps({"shape": list(output.shape), "finite": bool(torch.isfinite(output).all()), "input": "synthetic compatibility test"}))
