"""Extract chest X-ray pathology scores from published pretrained weights.

No training occurs. On first use torchxrayvision downloads its published
`densenet121-res224-all` weights into the normal PyTorch cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class PretrainedChestXrayExtractor:
    model_name = "densenet121-res224-all"

    def __init__(self):
        try:
            import torch
            import torchxrayvision as xrv
        except ImportError as exc:
            raise RuntimeError(
                "Install src/ml_model/requirements.txt before extracting image features"
            ) from exc
        self.torch = torch
        self.xrv = xrv
        self.model = xrv.models.DenseNet(weights=self.model_name)
        self.model.eval()
        self.transforms = (
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(224),
        )

    def extract(self, image_path: str):
        image = self.xrv.utils.load_image(image_path)
        tensor = self.torch.from_numpy(image)
        for transform in self.transforms:
            tensor = transform(tensor)
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
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
