"""Reviewed, resume-bound numeric settings for the OCR baseline tool."""

SETTINGS = {
    "version": 1,
    "seed": 20261115,
    "variants": {
        "clean": {
            "dpi": 300, "grayscale": 0, "rotation_degrees": 0,
            "perspective_ratio": 0, "blur_sigma": 0, "jpeg_quality": 0,
        },
        "scan": {
            "dpi": 200, "grayscale": 1, "rotation_degrees": 0,
            "perspective_ratio": 0, "blur_sigma": 0, "jpeg_quality": 70,
        },
        "phone": {
            "dpi": 300, "grayscale": 0, "rotation_degrees": 1.5,
            "perspective_ratio": .01, "blur_sigma": 1.0, "jpeg_quality": 60,
        },
    },
    "quality": {
        "replacement_ratio": .01, "private_use_ratio": .05,
        "combined_ratio": .05,
    },
    "lines": {"tolerance": .6, "overlap_min_fraction": .1},
    "height_boundaries": [12, 20, 32],
    "confidence_boundaries": [.5, .8, .9],
}
