"""AppWren: an open system of record for application portfolio management."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("appwren")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"

PRODUCT_NAME = "AppWren"
TAGLINE = "Know every application, and what to do with it."
