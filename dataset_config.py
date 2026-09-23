"""Central dataset configuration registry.

All dataset-specific behavior is driven by CGAN_DATASET environment variable.
This module is the single source of truth for field sets, truth loading behavior,
climatology settings, and download sources across IMERG, CHIRPS, and RFE datasets.

Usage:
    import dataset_config
    cfg = dataset_config.get_active_dataset()
    field_set = cfg["field_sets"][cfg["default_field_set"]]
"""

import os

# ── IFS field lists (shared building blocks) ─────────────────────────────────
_F13 = ['cp', 'mcc', 'sp', 'ssr', 't2m', 'tciw', 'tclw', 'tcrw', 'tcw', 'tcwv', 'tp', 'u700', 'v700']
_F14_CAPE = ['cape'] + _F13
_F14_CLIM = ['climatology'] + _F13

DATASETS = {
    "imerg": {
        "name": "IMERG",
        "accumulations": ["6h", "24h"],
        "default_accumulation": "6h",

        # field_sets: name → (all_fcst_fields, accumulated_fields, nonnegative_fields, clim_channels)
        "field_sets": {
            "6h_default": (
                _F14_CAPE,
                ['cp', 'ssr', 'tp'],
                [f for f in _F14_CAPE if f not in ('u700', 'v700')],
                0,
            ),
            "24h_default": (
                _F13,
                ['cp', 'ssr', 'tp'],
                [f for f in _F13 if f not in ('u700', 'v700')],
                0,
            ),
        },
        "default_field_set_6h": "6h_default",
        "default_field_set_24h": "24h_default",

        # truth loading behaviour
        "truth_nan_to_zero": False,
        "truth_unit_conversion": 1.0,   # no conversion (already mm/hr)

        # climatology
        "climatology_channels": 0,

        # paths (relative to project root)
        "data_root": "datasets/imerg",
    },

    "chirps": {
        "name": "CHIRPS",
        "accumulations": ["24h"],
        "default_accumulation": "24h",

        "field_sets": {
            # run07: 14 fields (climatology + 13 IFS) = 28 channels
            "run07": (
                _F14_CLIM,
                ['cp', 'ssr', 'tp'],
                ['climatology'] + [f for f in _F13 if f not in ('u700', 'v700')],
                0,      # climatology loaded as a regular field, not via clim channels
            ),
        },
        "default_field_set_24h": "run07",

        "truth_nan_to_zero": True,
        "truth_unit_conversion": 1.0 / 24.0,   # mm/day → mm/hr

        "climatology_channels": 0,

        "data_root": "datasets/chirps",
    },

    "rfe": {
        "name": "RFE",
        "accumulations": ["24h"],
        "default_accumulation": "24h",

        "field_sets": {
            # run11: 13 IFS fields + 2 climatology channels = 28 channels
            "run11": (
                _F13,
                ['cp', 'ssr', 'tp'],
                [f for f in _F13 if f not in ('u700', 'v700')],
                2,      # mean + sd climatology channels appended by data.py
            ),
        },
        "default_field_set_24h": "run11",

        "truth_nan_to_zero": True,
        "truth_unit_conversion": 1.0 / 24.0,   # mm/day → mm/hr

        "climatology_channels": 2,

        "data_root": "datasets/rfe",
    },
}


def get_active_dataset():
    """Return the config dict for the active dataset (from CGAN_DATASET env var)."""
    name = os.environ.get("CGAN_DATASET", "imerg").lower()
    if name not in DATASETS:
        raise ValueError(
            f"CGAN_DATASET={name!r} unknown; pick one of {sorted(DATASETS)}"
        )
    return DATASETS[name]


def get_active_dataset_name():
    """Return the active dataset name string."""
    return os.environ.get("CGAN_DATASET", "imerg").lower()
