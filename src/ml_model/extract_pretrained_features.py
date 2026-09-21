"""Extract chest X-ray pathology scores from published pretrained weights.

No training occurs. On first use torchxrayvision downloads its published
`densenet121-res224-all` weights into the normal PyTorch cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


class PretrainedChestXrayExtractor:
    model_name = "densenet121-res224-all"

    def __init__(self):
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        try:
            import torch
            import torchxrayvision as xrv
        except ImportError as exc:
            raise RuntimeError(
                "Install src/ml_model/requirements.txt before extracting image features"
            ) from exc
        self.torch = torch
        self.xrv = xrv
        # PyTorch 2.6+ defaults torch.load to weights_only=True, while the
        # published TorchXRayVision checkpoint predates that format. Scope the
        # compatibility override to loading this official package checkpoint.
        original_torch_load = torch.load

        def load_official_checkpoint(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return original_torch_load(*args, **kwargs)

        torch.load = load_official_checkpoint
        try:
            self.model = xrv.models.DenseNet(weights=self.model_name)
        finally:
            torch.load = original_torch_load
        self.model.eval()
        self.transforms = (
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(224),
        )

    def extract(self, image_path: str):
        import imageio.v2 as imageio
        import numpy as np

        image = imageio.imread(image_path)
        if image.ndim > 2:
            image = image[..., 0]
        if np.issubdtype(image.dtype, np.integer):
            max_value = np.iinfo(image.dtype).max
        else:
            max_value = 1.0 if float(image.max()) <= 1.0 else 255.0
        image = self.xrv.datasets.normalize(image, max_value, reshape=True)
        for transform in self.transforms:
            image = transform(image)
        tensor = self.torch.from_numpy(image)
        with self.torch.inference_mode():
            probabilities = self.model(tensor[None, ...])[0].cpu().tolist()
        return {
            name: float(score)
            for name, score in zip(self.model.pathologies, probabilities)
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract pathology scores using published pretrained weights; no training"
    )
    parser.add_argument("image", help="Path to a chest X-ray image")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()
    image_path = Path(args.image)
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    output = {
        "source_image": image_path.name,
        "source_sha256": digest,
        "weights": PretrainedChestXrayExtractor.model_name,
        "pathology_scores": PretrainedChestXrayExtractor().extract(args.image),
    }
    payload = json.dumps(output, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
