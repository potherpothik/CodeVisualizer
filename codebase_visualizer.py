"""
Backward-compatible entry point.

The canonical implementation now lives in the `codevisualizer` package.
This file exists so existing users who call
    python codebase_visualizer.py <path>
continue to work unchanged.

New usage:
    pip install codevisualizer
    codevis analyze <path>
"""

from codevisualizer._analyzer import (  # noqa: F401  (re-export for importers)
    FunctionInfo,
    ClassInfo,
    FileInfo,
    CodeAnalyzer,
    ProjectVisualizer,
)
from codevisualizer.cli import main

if __name__ == "__main__":
    main()
