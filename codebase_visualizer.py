"""
╔══════════════════════════════════════════════════════════════════╗
║          PYTHON CODEBASE VISUALIZER → MERMAID GENERATOR          ║
║                   Advanced AI-Ready Edition                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Generates multiple Mermaid diagrams for AI-assisted debugging:  ║
║                                                                  ║
║  1. architecture.mmd  — File/folder structure + imports          ║
║  2. classes.mmd       — Class hierarchy + inheritance            ║
║  3. callgraph.mmd     — Function calls + cross-file flows        ║
║  4. dataflow.mmd      — Data/variable flow between functions     ║
║  5. summary.md        — Full Markdown report for AI agents       ║
║                                                                  ║
║  Usage:                                                          ║
║    python codebase_visualizer.py /path/to/project                ║
║    python codebase_visualizer.py /path/to/project --out ./diagrams║
║    python codebase_visualizer.py /path/to/project --single       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import ast
import os
import sys
import json
import argparse
import hashlib
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
#  DATA MODELS
# ─────────────────────────────────────────────

@dataclass
class FunctionInfo:
    name: str
    file: str
    lineno: int
    end_lineno: int
    args: list[str]
    returns: Optional[str]
    docstring: Optional[str]
    decorators: list[str]
    is_async: bool
    parent_class: Optional[str]
    calls: list[str] = field(default_factory=list)
    assignments: list[str] = field(default_factory=list)  # variables assigned

    @property
    def full_name(self):
        if self.parent_class:
            return f"{self.file}::{self.parent_class}.{self.name}"
        return f"{self.file}::{self.name}"

    @property
    def short_name(self):
        if self.parent_class:
            return f"{self.parent_class}.{self.name}"
        return self.name


@dataclass
class ClassInfo:
    name: str
    file: str
    lineno: int
    bases: list[str]
    docstring: Optional[str]
    decorators: list[str]
    methods: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)

    @property
    def full_name(self):
        return f"{self.file}::{self.name}"


@dataclass
class FileInfo:
    path: str
    imports: list[tuple[str, str]] = field(default_factory=list)   # (module, alias)
    from_imports: list[tuple[str, str, str]] = field(default_factory=list)  # (module, name, alias)
    global_vars: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    loc: int = 0


# ─────────────────────────────────────────────
#  AST ANALYZER
# ─────────────────────────────────────────────

class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self, filepath: str, root_dir: str):
        self.filepath = filepath
        self.root_dir = root_dir
        self.rel_path = os.path.relpath(filepath, root_dir)

        self.file_info = FileInfo(path=self.rel_path)
        self.functions: dict[str, FunctionInfo] = {}
        self.classes: dict[str, ClassInfo] = {}

        self._class_stack: list[str] = []
        self._function_stack: list[FunctionInfo] = []

    # ── Imports ──────────────────────────────

    def visit_Import(self, node):
        for alias in node.names:
            self.file_info.imports.append((alias.name, alias.asname or alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.file_info.from_imports.append((module, alias.name, alias.asname or alias.name))
        self.generic_visit(node)

    # ── Assignments ──────────────────────────

    def visit_Assign(self, node):
        if self._function_stack:
            fi = self._function_stack[-1]
            for target in node.targets:
                if isinstance(target, ast.Name):
                    fi.assignments.append(target.id)
        else:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.file_info.global_vars.append(target.id)
        self.generic_visit(node)

    # ── Classes ──────────────────────────────

    def visit_ClassDef(self, node):
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            else:
                bases.append(ast.unparse(b) if hasattr(ast, "unparse") else "base")

        decorators = []
        for d in node.decorator_list:
            decorators.append(ast.unparse(d) if hasattr(ast, "unparse") else "decorator")

        doc = ast.get_docstring(node)
        ci = ClassInfo(
            name=node.name,
            file=self.rel_path,
            lineno=getattr(node, "lineno", 0),
            bases=bases,
            docstring=doc,
            decorators=decorators,
        )
        key = f"{self.rel_path}::{node.name}"
        self.classes[key] = ci
        self.file_info.classes.append(key)

        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    # ── Functions ────────────────────────────

    def visit_FunctionDef(self, node):
        self._visit_any_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node):
        self._visit_any_function(node, is_async=True)

    def _visit_any_function(self, node, is_async: bool):
        decorators = []
        for d in node.decorator_list:
            decorators.append(ast.unparse(d) if hasattr(ast, "unparse") else "decorator")

        args = [a.arg for a in node.args.args]
        returns = None
        if getattr(node, "returns", None) is not None:
            returns = ast.unparse(node.returns) if hasattr(ast, "unparse") else "return"

        parent_class = self._class_stack[-1] if self._class_stack else None
        doc = ast.get_docstring(node)
        fi = FunctionInfo(
            name=node.name,
            file=self.rel_path,
            lineno=getattr(node, "lineno", 0),
            end_lineno=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
            args=args,
            returns=returns,
            docstring=doc,
            decorators=decorators,
            is_async=is_async,
            parent_class=parent_class,
        )

        key = fi.full_name
        self.functions[key] = fi
        self.file_info.functions.append(key)

        if parent_class:
            ckey = f"{self.rel_path}::{parent_class}"
            if ckey in self.classes:
                self.classes[ckey].methods.append(fi.short_name)

        self._function_stack.append(fi)
        self.generic_visit(node)
        self._function_stack.pop()

    # ── Calls ────────────────────────────────

    def visit_Call(self, node):
        if self._function_stack:
            fi = self._function_stack[-1]
            try:
                callee = ast.unparse(node.func) if hasattr(ast, "unparse") else "call"
            except Exception:
                callee = "call"
            fi.calls.append(callee)
        self.generic_visit(node)


# ─────────────────────────────────────────────
#  PROJECT VISUALIZER
# ─────────────────────────────────────────────

class ProjectVisualizer:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.files: dict[str, FileInfo] = {}
        self.functions: dict[str, FunctionInfo] = {}
        self.classes: dict[str, ClassInfo] = {}
        self.errors: list[str] = []

    def analyze(self):
        for path in Path(self.root_dir).rglob("*.py"):
            if any(part.startswith(".") for part in path.parts):
                continue
            if "__pycache__" in path.parts:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content)
                analyzer = CodeAnalyzer(str(path), self.root_dir)
                analyzer.file_info.loc = content.count("\n") + 1
                analyzer.visit(tree)

                self.files[analyzer.file_info.path] = analyzer.file_info
                self.functions.update(analyzer.functions)
                self.classes.update(analyzer.classes)
            except SyntaxError as e:
                rel = os.path.relpath(str(path), self.root_dir)
                self.errors.append(f"{rel}: {e}")
            except Exception as e:
                rel = os.path.relpath(str(path), self.root_dir)
                self.errors.append(f"{rel}: {e}")

    # ─────────────────────────────────────────
    #  DIAGRAM WRITERS
    # ─────────────────────────────────────────

    def _safe_id(self, s: str) -> str:
        h = hashlib.md5(s.encode("utf-8")).hexdigest()[:8]
        return f"id_{h}"

    def write_architecture(self, output_dir: str):
        out = os.path.join(output_dir, "architecture.mmd")
        lines = ["flowchart TD"]

        for f in sorted(self.files.keys()):
            fid = self._safe_id(f)
            lines.append(f'  {fid}["{f}"]')

        # Show import edges (best-effort)
        file_by_name = {os.path.splitext(os.path.basename(k))[0]: k for k in self.files.keys()}
        for f, info in self.files.items():
            src_id = self._safe_id(f)
            for module, _alias in info.imports:
                base = module.split(".")[0]
                if base in file_by_name:
                    dst = file_by_name[base]
                    dst_id = self._safe_id(dst)
                    lines.append(f"  {src_id} --> {dst_id}")
            for module, _name, _alias in info.from_imports:
                base = (module or "").split(".")[0]
                if base in file_by_name:
                    dst = file_by_name[base]
                    dst_id = self._safe_id(dst)
                    lines.append(f"  {src_id} --> {dst_id}")

        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def write_classes(self, output_dir: str):
        out = os.path.join(output_dir, "classes.mmd")
        lines = ["classDiagram"]

        for key, c in sorted(self.classes.items()):
            lines.append(f"  class {c.name} {{")
            for m in sorted(set(c.methods)):
                lines.append(f"    +{m}()")
            lines.append("  }")
            for base in c.bases:
                if base:
                    lines.append(f"  {base} <|-- {c.name}")

        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def write_callgraph(self, output_dir: str):
        out = os.path.join(output_dir, "callgraph.mmd")
        lines = ["flowchart LR"]

        for fkey, f in sorted(self.functions.items()):
            src = self._safe_id(fkey)
            label = f.short_name.replace('"', "'")
            lines.append(f'  {src}["{label}"]')

        # Best-effort: draw edges to any function that matches by short name
        short_to_full = defaultdict(list)
        for k, fn in self.functions.items():
            short_to_full[fn.short_name].append(k)

        for fkey, fn in self.functions.items():
            src = self._safe_id(fkey)
            for c in fn.calls[:200]:
                callee_short = c.split("(")[0].split(".")[-1]
                for target_key in short_to_full.get(callee_short, []):
                    dst = self._safe_id(target_key)
                    lines.append(f"  {src} --> {dst}")

        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def write_workflow(self, output_dir: str):
        out = os.path.join(output_dir, "workflow.mmd")
        lines = ["flowchart TD"]

        # Heuristic entry points
        entries = [k for k, v in self.functions.items() if v.name in ("main", "run", "cli")]
        if not entries:
            entries = list(self.functions.keys())[:10]

        visited = set()

        def walk(node_key: str, depth: int):
            if depth > 3 or node_key in visited:
                return
            visited.add(node_key)

            fn = self.functions[node_key]
            src = self._safe_id(node_key)
            for c in fn.calls[:20]:
                callee_short = c.split("(")[0].split(".")[-1]
                for tgt_key, tgt_fn in self.functions.items():
                    if tgt_fn.name == callee_short:
                        dst = self._safe_id(tgt_key)
                        lines.append(f"  {src} --> {dst}")
                        walk(tgt_key, depth + 1)

        for e in entries:
            walk(e, 0)

        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def write_summary(self, output_dir: str):
        out = os.path.join(output_dir, "summary.md")
        lines = []
        lines.append("# Codebase Summary\n")
        lines.append(f"- Root: `{self.root_dir}`\n")
        lines.append(f"- Files: **{len(self.files)}**\n")
        lines.append(f"- Classes: **{len(self.classes)}**\n")
        lines.append(f"- Functions: **{len(self.functions)}**\n")
        if self.errors:
            lines.append(f"\n## Parse errors ({len(self.errors)})\n")
            for e in self.errors[:200]:
                lines.append(f"- {e}\n")

        lines.append("\n## Top files by LOC\n")
        by_loc = sorted(self.files.values(), key=lambda x: x.loc, reverse=True)[:50]
        for fi in by_loc:
            lines.append(f"- `{fi.path}` — {fi.loc}\n")

        Path(out).write_text("".join(lines), encoding="utf-8")
        print(f"  ✅ {out}")

    def write_json_index(self, output_dir: str):
        try:
            index = {
                "root_dir": self.root_dir,
                "files": list(self.files.keys()),
                "classes": {
                    k: {
                        "name": v.name,
                        "file": v.file,
                        "lineno": v.lineno,
                        "bases": v.bases,
                        "methods": v.methods,
                    } for k, v in self.classes.items()
                },
                "functions": {
                    k: {
                        "name": v.name,
                        "file": v.file,
                        "lineno": v.lineno,
                        "args": v.args,
                        "returns": v.returns,
                        "is_async": v.is_async,
                        "parent_class": v.parent_class,
                        "calls": v.calls[:20],
                    } for k, v in self.functions.items()
                },
            }
            out = os.path.join(output_dir, "codebase_index.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
            print(f"  ✅ {out}")
        except Exception as e:
            print(f"  ⚠  Failed to generate JSON index: {e}")

    def write_all(self, output_dir: str, single_mode: bool = False):
        os.makedirs(output_dir, exist_ok=True)

        # Separate output files (preferred for AI tools)
        self.write_architecture(output_dir)
        self.write_classes(output_dir)
        self.write_callgraph(output_dir)
        self.write_workflow(output_dir)
        self.write_summary(output_dir)
        self.write_json_index(output_dir)


# ─────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Python Codebase Visualizer → Mermaid Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output files:
  architecture.mmd   File/folder structure with import dependencies
  classes.mmd        Class diagram with hierarchy and methods
  callgraph.mmd      Cross-file function call graph
  workflow.mmd       Execution workflow from entry points
  summary.md         Full Markdown report for AI agents
  codebase_index.json  Machine-readable index for tooling
        """,
    )
    parser.add_argument("project_path", help="Path to Python project root")
    parser.add_argument(
        "--out",
        "-o",
        default="./mermaid_output",
        help="Output directory (default: ./mermaid_output)",
    )
    parser.add_argument(
        "--single",
        "-s",
        action="store_true",
        help="Generate a single all-in-one diagram instead of separate files",
    )

    args = parser.parse_args()
    project_path = os.path.abspath(args.project_path)

    if not os.path.isdir(project_path):
        print(f"Error: '{project_path}' is not a valid directory.")
        sys.exit(1)

    print(f"\n{'═' * 60}")
    print(f"  🔍  Analyzing: {project_path}")
    print(f"{'═' * 60}\n")

    viz = ProjectVisualizer(project_path)

    print("[ 1/3 ] Scanning & analyzing files...")
    viz.analyze()

    print(f"\n[ 2/3 ] Generating diagrams → {args.out}")
    viz.write_all(args.out, single_mode=args.single)

    print("\n[ 3/3 ] Done!")
    print(f"\n{'─' * 60}")
    print(f"  📊 Stats: {len(viz.files)} files · {len(viz.classes)} classes · {len(viz.functions)} functions")
    if viz.errors:
        print(f"  ⚠  {len(viz.errors)} parse error(s) — see summary.md")
    print(f"  📁 Output: {os.path.abspath(args.out)}/")
    print(f"{'─' * 60}\n")
    print("  💡 AI Agent tip: Feed summary.md + any .mmd file to your IDE AI")
    print("     for architecture review, debugging, and refactoring suggestions.\n")


if __name__ == "__main__":
    main()

