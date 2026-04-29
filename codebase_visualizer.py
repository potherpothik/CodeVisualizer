"""
╔══════════════════════════════════════════════════════════════════╗
║          PYTHON CODEBASE VISUALIZER → MERMAID GENERATOR          ║
║                   Advanced AI-Ready Edition                       ║
╠══════════════════════════════════════════════════════════════════╣
║  Generates multiple Mermaid diagrams for AI-assisted debugging:  ║
║                                                                  ║
║  1. architecture.mmd    — File/folder structure + imports        ║
║  2. classes.mmd         — Class hierarchy + inheritance          ║
║  3. callgraph.mmd       — Function calls + cross-file flows      ║
║  4. workflow.mmd        — Human-readable execution flow          ║
║  5. erd.mmd             — Human-readable entity relationship map ║
║  6. summary.md          — Full Markdown report for AI agents     ║
║  7. ai_context_primer.md — Paste-ready brief for new AI chats   ║
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
import re
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

    def _current_class_key(self) -> Optional[str]:
        if not self._class_stack:
            return None
        key = f"{self.rel_path}::{self._class_stack[-1]}"
        return key if key in self.classes else None

    def _record_class_attribute(self, name: Optional[str]):
        if not name:
            return
        ckey = self._current_class_key()
        if not ckey:
            return
        attrs = self.classes[ckey].attributes
        if name not in attrs:
            attrs.append(name)

    def _extract_self_attribute(self, target) -> Optional[str]:
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id in ("self", "cls"):
                return target.attr
        return None

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
                    self._record_class_attribute(self._extract_self_attribute(target))
        elif self._class_stack:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._record_class_attribute(target.id)
                else:
                    self._record_class_attribute(self._extract_self_attribute(target))
        else:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.file_info.global_vars.append(target.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        target = node.target
        if self._function_stack:
            fi = self._function_stack[-1]
            if isinstance(target, ast.Name):
                fi.assignments.append(target.id)
            else:
                self._record_class_attribute(self._extract_self_attribute(target))
        elif self._class_stack:
            if isinstance(target, ast.Name):
                self._record_class_attribute(target.id)
            else:
                self._record_class_attribute(self._extract_self_attribute(target))
        else:
            if isinstance(target, ast.Name):
                self.file_info.global_vars.append(target.id)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        target = node.target
        if self._function_stack:
            fi = self._function_stack[-1]
            if isinstance(target, ast.Name):
                fi.assignments.append(target.id)
            else:
                self._record_class_attribute(self._extract_self_attribute(target))
        elif self._class_stack:
            if isinstance(target, ast.Name):
                self._record_class_attribute(target.id)
            else:
                self._record_class_attribute(self._extract_self_attribute(target))
        else:
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
    def __init__(self, root_dir: str, exclude_prefixes: Optional[list[str]] = None):
        self.root_dir = root_dir
        self.exclude_prefixes = exclude_prefixes or []
        self.files: dict[str, FileInfo] = {}
        self.functions: dict[str, FunctionInfo] = {}
        self.classes: dict[str, ClassInfo] = {}
        self.errors: list[str] = []

    def _norm_rel(self, rel: str) -> str:
        return os.path.normpath(rel).replace("\\", "/")

    def _should_skip_path(self, rel_file: str) -> bool:
        """Skip if file path is under any exclude prefix (relative to root_dir)."""
        rel_norm = self._norm_rel(rel_file)
        for raw in self.exclude_prefixes:
            ex = raw.strip()
            if not ex or ex.startswith("#"):
                continue
            ex_norm = self._norm_rel(ex).strip("./")
            if not ex_norm:
                continue
            if rel_norm == ex_norm or rel_norm.startswith(ex_norm + "/"):
                return True
        return False

    def analyze(self):
        for path in Path(self.root_dir).rglob("*.py"):
            if any(part.startswith(".") for part in path.parts):
                continue
            if "__pycache__" in path.parts:
                continue

            rel_file = os.path.relpath(str(path), self.root_dir)
            if self._should_skip_path(rel_file):
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

    def _clean_label(self, text: str, max_len: int = 80) -> str:
        cleaned = " ".join((text or "").split())
        cleaned = cleaned.replace('"', "'")
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[: max_len - 1] + "…"

    def _short_file_label(self, path: str, parts: int = 2) -> str:
        normalized = path.replace("\\", "/")
        chunks = [p for p in normalized.split("/") if p]
        if not chunks:
            return path
        return "/".join(chunks[-parts:])

    def _function_label(self, fn: FunctionInfo) -> str:
        prefix = "async " if fn.is_async else ""
        loc = f"{self._short_file_label(fn.file)}:{fn.lineno}"
        return f"{prefix}{fn.short_name}<br/>{loc}"

    def _call_to_short_name(self, call_expr: str) -> str:
        raw = (call_expr or "").strip()
        if not raw:
            return ""
        if raw.startswith("await "):
            raw = raw[6:].strip()
        raw = raw.split("(", 1)[0].strip()
        raw = re.sub(r"\[.*\]$", "", raw)
        if "." in raw:
            raw = raw.split(".")[-1]
        return re.sub(r"[^0-9A-Za-z_]", "", raw)

    def _method_entity_hints(self, method_name: str) -> set[str]:
        method = (method_name or "").split(".")[-1]
        hints: set[str] = set()
        match_action = re.match(r"^(get|list|find|create|update|delete|add|remove|fetch)_(.+)$", method)
        if match_action:
            candidate = match_action.group(2).rstrip("s")
            if candidate:
                hints.add(candidate.lower())
        match_id = re.match(r"^(.+)_(id|ids)$", method)
        if match_id:
            candidate = match_id.group(1).rstrip("s")
            if candidate:
                hints.add(candidate.lower())
        return hints

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
        lines = [
            "flowchart TD",
            "  %% Human-readable workflow with function labels and call details",
        ]

        if not self.functions:
            lines.append('  empty["No functions discovered"]')
            Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"  ✅ {out}")
            return

        short_to_full = defaultdict(list)
        for key, fn in self.functions.items():
            short_to_full[fn.name].append(key)

        node_lines: list[str] = []
        edge_lines: list[str] = []
        added_nodes: set[str] = set()
        added_edges: set[tuple[str, str]] = set()
        node_ids: dict[str, str] = {}

        def node_id_for(function_key: str) -> str:
            if function_key in node_ids:
                return node_ids[function_key]
            fn = self.functions[function_key]
            readable = re.sub(
                r"[^0-9A-Za-z_]",
                "_",
                f"{fn.short_name}_{self._short_file_label(fn.file)}_{fn.lineno}",
            ).strip("_")
            if not readable:
                readable = "function"
            if readable[0].isdigit():
                readable = f"fn_{readable}"
            suffix = self._safe_id(function_key)[3:]
            node_ids[function_key] = f"{readable}_{suffix}"
            return node_ids[function_key]

        def ensure_node(function_key: str):
            if function_key in added_nodes:
                return
            fn = self.functions[function_key]
            node_id = node_id_for(function_key)
            label = self._clean_label(self._function_label(fn), max_len=100)
            node_lines.append(f'  {node_id}["{label}"]')
            added_nodes.add(function_key)

        # Heuristic entry points
        entries = [k for k, v in self.functions.items() if v.name in ("main", "run", "cli")]
        if not entries:
            entries = list(sorted(self.functions.keys()))[:10]

        for entry_key in entries:
            ensure_node(entry_key)

        visited: set[tuple[str, int]] = set()

        def walk(node_key: str, depth: int):
            if depth > 3:
                return
            visit_key = (node_key, depth)
            if visit_key in visited:
                return
            visited.add(visit_key)

            fn = self.functions[node_key]
            src_id = node_id_for(node_key)
            for call_expr in fn.calls[:30]:
                callee_short = self._call_to_short_name(call_expr)
                if not callee_short:
                    continue
                for target_key in short_to_full.get(callee_short, []):
                    ensure_node(target_key)
                    dst_id = node_id_for(target_key)
                    edge_key = (src_id, dst_id)
                    if edge_key in added_edges:
                        continue
                    added_edges.add(edge_key)
                    call_label = self._clean_label(call_expr, max_len=40)
                    edge_lines.append(f'  {src_id} -->|{call_label}| {dst_id}')
                    walk(target_key, depth + 1)

        for entry_key in entries:
            walk(entry_key, 0)

        lines.extend(node_lines)
        lines.extend(edge_lines)
        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def write_erd(self, output_dir: str):
        out = os.path.join(output_dir, "erd.mmd")
        lines = [
            "erDiagram",
            "  %% Best-effort ERD derived from classes and detected attributes",
        ]

        if not self.classes:
            lines.append("  EMPTY_ENTITY {")
            lines.append("    string note")
            lines.append("  }")
            Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"  ✅ {out}")
            return

        class_names = {c.name: k for k, c in self.classes.items()}
        lowered_name_to_class = {c.name.lower(): c.name for c in self.classes.values()}

        for _key, cls in sorted(self.classes.items()):
            lines.append(f"  {cls.name} {{")
            attrs = sorted(set(cls.attributes))
            if not attrs:
                lines.append("    string _no_fields_detected")
            else:
                for attr in attrs[:30]:
                    safe_attr = self._clean_label(attr, max_len=60).replace(" ", "_")
                    lines.append(f"    string {safe_attr}")
            lines.append("  }")

        relation_lines: set[str] = set()

        # Inheritance relationship.
        for _key, cls in sorted(self.classes.items()):
            for base in cls.bases:
                base_name = base.split(".")[-1]
                if base_name in class_names:
                    relation_lines.add(f"  {base_name} ||--|| {cls.name} : inherits")

        # Attribute-name relationship hints (e.g. user_id -> User).
        for _key, cls in sorted(self.classes.items()):
            for attr in cls.attributes:
                attr_lower = attr.lower()
                candidate = attr_lower
                if candidate.endswith("_id"):
                    candidate = candidate[:-3]
                elif candidate.endswith("_ids"):
                    candidate = candidate[:-4]
                candidate = candidate.rstrip("s")
                target_class = lowered_name_to_class.get(candidate)
                if target_class and target_class != cls.name:
                    relation_lines.add(f"  {cls.name} }}o--|| {target_class} : {attr}")

        # Method-name relationship hints (e.g. get_orders -> Order).
        for _key, cls in sorted(self.classes.items()):
            for method in cls.methods:
                hints = self._method_entity_hints(method)
                for hint in hints:
                    target_class = lowered_name_to_class.get(hint)
                    if target_class and target_class != cls.name:
                        relation_lines.add(f"  {cls.name} ||--o{{ {target_class} : {method}")

        lines.extend(sorted(relation_lines))
        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def _update_json_index_relationships(self, index: dict):
        class_names = {c.name: k for k, c in self.classes.items()}
        lowered_name_to_class = {c.name.lower(): c.name for c in self.classes.values()}

        relationships: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()

        def add_rel(source: str, target: str, relation: str, hint: str):
            key = (source, target, relation)
            if source == target or key in seen:
                return
            seen.add(key)
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "hint": hint,
                }
            )

        for _key, cls in sorted(self.classes.items()):
            for base in cls.bases:
                base_name = base.split(".")[-1]
                if base_name in class_names:
                    add_rel(base_name, cls.name, "inherits", "base class")

        for _key, cls in sorted(self.classes.items()):
            for attr in cls.attributes:
                attr_lower = attr.lower()
                candidate = attr_lower
                if candidate.endswith("_id"):
                    candidate = candidate[:-3]
                elif candidate.endswith("_ids"):
                    candidate = candidate[:-4]
                candidate = candidate.rstrip("s")
                target_class = lowered_name_to_class.get(candidate)
                if target_class:
                    add_rel(cls.name, target_class, "references", f"attribute:{attr}")

            for method in cls.methods:
                for hint in self._method_entity_hints(method):
                    target_class = lowered_name_to_class.get(hint)
                    if target_class:
                        add_rel(cls.name, target_class, "uses", f"method:{method}")

        for class_key, cls in self.classes.items():
            class_entry = index["classes"].get(class_key)
            if class_entry is not None:
                class_entry["attributes"] = sorted(set(cls.attributes))

        index["relationships"] = relationships

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
                        "attributes": v.attributes,
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
            self._update_json_index_relationships(index)
            out = os.path.join(output_dir, "codebase_index.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
            print(f"  ✅ {out}")
        except Exception as e:
            print(f"  ⚠  Failed to generate JSON index: {e}")

    def write_ai_context_primer(self, output_dir: str):
        """Generate a compact, paste-ready AI context primer for new chat sessions.

        The primer is intentionally small enough to paste into any AI chat as the
        very first message so the agent immediately understands the project without
        reading the full codebase.  It covers:
          - What the project is and what it does
          - Key files and their one-line purpose
          - Class and function catalogue (name, file, line)
          - Most important cross-file call relationships
          - Known entry points
          - Where to look for more detail (diagrams, memory log, changelog)
        """
        out = os.path.join(output_dir, "ai_context_primer.md")
        lines: list[str] = []

        # ── Header ────────────────────────────────────────────────────────────
        lines.append("# AI Context Primer\n")
        lines.append(
            "> Paste this file as the **first message** of any new AI chat to avoid\n"
            "> re-explaining the project from scratch.  It is auto-generated by\n"
            "> CodeVisualizer and stays in sync with every `regenerate` run.\n"
        )
        lines.append("")

        # ── Stats ─────────────────────────────────────────────────────────────
        lines.append("## Project snapshot\n")
        lines.append(f"| Metric | Count |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Python files | {len(self.files)} |")
        lines.append(f"| Classes | {len(self.classes)} |")
        lines.append(f"| Functions / methods | {len(self.functions)} |")
        total_loc = sum(fi.loc for fi in self.files.values())
        lines.append(f"| Total LOC | {total_loc} |")
        lines.append("")

        # ── File map ──────────────────────────────────────────────────────────
        lines.append("## File map (key files first)\n")
        by_loc = sorted(self.files.values(), key=lambda x: x.loc, reverse=True)
        for fi in by_loc[:40]:
            n_classes = len(fi.classes)
            n_funcs = len(fi.functions)
            parts = []
            if n_classes:
                parts.append(f"{n_classes} class{'es' if n_classes != 1 else ''}")
            if n_funcs:
                parts.append(f"{n_funcs} fn{'s' if n_funcs != 1 else ''}")
            parts.append(f"{fi.loc} LOC")
            lines.append(f"- `{fi.path}` — {', '.join(parts)}")
        lines.append("")

        # ── Entry points ──────────────────────────────────────────────────────
        entry_names = {"main", "run", "cli", "execute", "start", "app", "setup"}
        entries = [
            fn for fn in self.functions.values()
            if fn.name in entry_names and not fn.parent_class
        ]
        if entries:
            lines.append("## Entry points\n")
            for fn in sorted(entries, key=lambda f: f.name):
                lines.append(f"- `{fn.short_name}()` in `{fn.file}` (line {fn.lineno})")
            lines.append("")

        # ── Class catalogue ───────────────────────────────────────────────────
        if self.classes:
            lines.append("## Classes\n")
            for key in sorted(self.classes.keys()):
                cls = self.classes[key]
                bases_str = f" extends {', '.join(cls.bases)}" if cls.bases else ""
                doc_str = ""
                if cls.docstring:
                    first_doc_line = cls.docstring.strip().splitlines()[0]
                    doc_str = f" — {self._clean_label(first_doc_line, max_len=80)}"
                lines.append(
                    f"- **`{cls.name}`**{bases_str} (`{cls.file}`:{cls.lineno}){doc_str}"
                )
                if cls.methods:
                    method_list = ", ".join(f"`{m}()`" for m in sorted(set(cls.methods))[:12])
                    lines.append(f"  - Methods: {method_list}")
            lines.append("")

        # ── Function catalogue (non-method top-level) ──────────────────────────
        top_level_fns = [
            fn for fn in self.functions.values() if not fn.parent_class
        ]
        if top_level_fns:
            lines.append("## Top-level functions\n")
            for fn in sorted(top_level_fns, key=lambda f: (f.file, f.lineno))[:60]:
                async_tag = "async " if fn.is_async else ""
                ret = f" → `{fn.returns}`" if fn.returns else ""
                doc_str = ""
                if fn.docstring:
                    first_doc = fn.docstring.strip().splitlines()[0]
                    doc_str = f" — {self._clean_label(first_doc, max_len=70)}"
                lines.append(
                    f"- `{async_tag}{fn.name}({', '.join(fn.args)})`{ret}"
                    f" in `{fn.file}`:{fn.lineno}{doc_str}"
                )
            lines.append("")

        # ── Key call relationships ─────────────────────────────────────────────
        short_to_full: dict[str, list[str]] = defaultdict(list)
        for k, fn in self.functions.items():
            short_to_full[fn.name].append(k)

        cross_file_calls: list[tuple[str, str, str]] = []
        for fkey, fn in self.functions.items():
            for call_expr in fn.calls[:30]:
                callee_short = self._call_to_short_name(call_expr)
                if not callee_short:
                    continue
                for target_key in short_to_full.get(callee_short, []):
                    target_fn = self.functions[target_key]
                    if target_fn.file != fn.file:
                        cross_file_calls.append(
                            (fn.short_name, target_fn.short_name, target_fn.file)
                        )

        if cross_file_calls:
            lines.append("## Cross-file call relationships\n")
            seen_calls: set[tuple[str, str]] = set()
            for caller, callee, callee_file in cross_file_calls[:40]:
                key = (caller, callee)
                if key in seen_calls:
                    continue
                seen_calls.add(key)
                lines.append(f"- `{caller}` → `{callee}()` (in `{callee_file}`)")
            lines.append("")

        # ── Where to find more ────────────────────────────────────────────────
        lines.append("## Where to find more\n")
        lines.append(
            "| Artefact | Purpose |\n"
            "|----------|---------|\n"
            "| `mermaid_output/<target>/architecture.mmd` | File dependency graph |\n"
            "| `mermaid_output/<target>/classes.mmd` | Class hierarchy |\n"
            "| `mermaid_output/<target>/callgraph.mmd` | Full function call graph |\n"
            "| `mermaid_output/<target>/workflow.mmd` | Execution flow from entry points |\n"
            "| `mermaid_output/<target>/erd.mmd` | Entity-relationship diagram |\n"
            "| `mermaid_output/<target>/summary.md` | LOC stats + parse errors |\n"
            "| `mermaid_output/<target>/codebase_index.json` | Machine-readable index |\n"
            "| `CodeVisualizer/Readme/AI_PROJECT_MEMORY.md` | Curated change history |\n"
            "| `CHANGELOG.md` (repo root) | Structured modification log |"
        )
        lines.append("")
        lines.append(
            "> **Tip for the AI**: read `AI_PROJECT_MEMORY.md` for the *why* behind\n"
            "> recent changes, and `CHANGELOG.md` for a precise record of *what* changed\n"
            "> and *which files* were touched.  Together they replace the need to scan\n"
            "> commit history manually.\n"
        )

        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def write_all(self, output_dir: str, single_mode: bool = False):
        os.makedirs(output_dir, exist_ok=True)

        # Separate output files (preferred for AI tools)
        self.write_architecture(output_dir)
        self.write_classes(output_dir)
        self.write_callgraph(output_dir)
        self.write_workflow(output_dir)
        self.write_erd(output_dir)
        self.write_summary(output_dir)
        self.write_json_index(output_dir)
        self.write_ai_context_primer(output_dir)


# ─────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Python Codebase Visualizer → Mermaid Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output files:
  architecture.mmd      File/folder structure with import dependencies
  classes.mmd           Class diagram with hierarchy and methods
  callgraph.mmd         Cross-file function call graph
  workflow.mmd          Human-readable execution workflow from entry points
  erd.mmd               Human-readable entity-relationship diagram from classes
  summary.md            Full Markdown report for AI agents
  codebase_index.json   Machine-readable index for tooling
  ai_context_primer.md  Compact paste-ready brief for starting new AI chats
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
    parser.add_argument(
        "--exclude",
        "-x",
        action="append",
        default=[],
        metavar="PREFIX",
        help="Skip Python files under this path prefix (relative to project root). Repeatable.",
    )

    args = parser.parse_args()
    project_path = os.path.abspath(args.project_path)

    if not os.path.isdir(project_path):
        print(f"Error: '{project_path}' is not a valid directory.")
        sys.exit(1)

    print(f"\n{'═' * 60}")
    print(f"  🔍  Analyzing: {project_path}")
    print(f"{'═' * 60}\n")

    viz = ProjectVisualizer(project_path, exclude_prefixes=args.exclude or [])

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
    print("  💡 AI tip: paste ai_context_primer.md as the first message of any")
    print("     new chat — it gives the agent a full project picture instantly.")
    print("     Also feed .mmd diagrams for architecture / call-graph detail.\n")


if __name__ == "__main__":
    main()

