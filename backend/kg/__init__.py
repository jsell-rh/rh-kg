"""Red Hat Knowledge Graph - Modern Python infrastructure for knowledge management."""

__version__ = "0.1.0"
__author__ = "John Sell"
__email__ = "jsell@redhat.com"

# Re-export main components for easy access
from kg.cli import *  # noqa: F403
from kg.core import *  # noqa: F403

__all__ = [
    "__author__",
    "__email__",
    "__version__",
]
