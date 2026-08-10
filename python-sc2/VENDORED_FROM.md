# Vendored python-sc2 snapshot

This directory is the Agent-owned runtime dependency copied from the parent
`sharpy-sc2/python-sc2` tree on 2026-07-06.

- Parent repository tree object: `309eadebf07e2d85e37985149e66f2b569b16103`
- Package name/version: `burnysc2 7.1.1`
- License: MIT; see `LICENSE` in this directory.

The Agent must load `sc2` from this directory through `sc2_runtime.py`. A
conda- or site-packages-provided `sc2` is intentionally not accepted because
older builds omit upgrade-to-research-building mappings used by Agent BOs.
