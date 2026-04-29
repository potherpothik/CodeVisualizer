"""
CodeVisualizer — AI context toolkit for Python projects.

Public API:
  from codevisualizer import ProjectVisualizer, CodeAnalyzer
  from codevisualizer import FunctionInfo, ClassInfo, FileInfo
"""

from ._analyzer import (
    ProjectVisualizer,
    CodeAnalyzer,
    FunctionInfo,
    ClassInfo,
    FileInfo,
)

__all__ = [
    "ProjectVisualizer",
    "CodeAnalyzer",
    "FunctionInfo",
    "ClassInfo",
    "FileInfo",
]

__version__ = "1.0.0"
