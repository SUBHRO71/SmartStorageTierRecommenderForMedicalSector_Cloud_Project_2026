"""Training is intentionally disabled for the current project architecture."""


def main():
    raise SystemExit(
        "No training step is required. Use extract_pretrained_features.py to run the "
        "published chest X-ray weights, then use decision_engine.py for tier selection. "
        "The previous experiment is preserved as legacy_training.py for audit history."
    )


if __name__ == "__main__":
    main()
