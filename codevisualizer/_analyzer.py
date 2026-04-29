"""
Core analysis engine: data models, AST analyzer, and project visualizer.
Extracted from the standalone codebase_visualizer.py for use as a package.
"""

import ast
import os
import json
import re
import hashlib
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple

# ─────────────────────────────────────────────
#  DATA MODELS
# ─────────────────────────────────────────────

@dataclass
class FunctionInfo:
    name: str
    file: str
    lineno: int
    end_lineno: int
    args: List[str]
    returns: Optional[str]
    docstring: Optional[str]
    decorators: List[str]
    is_async: bool
    parent_class: Optional[str]
    calls: List[str] = field(default_factory=list)
    unresolved_calls: List[str] = field(default_factory=list)
    assignments: List[str] = field(default_factory=list)

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
    bases: List[str]
    docstring: Optional[str]
    decorators: List[str]
    methods: List[str] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    # Framework-aware field descriptors: {attr_name: field_type}
    # e.g. {"partner_id": "Many2one", "line_ids": "One2many"}
    orm_fields: Dict[str, str] = field(default_factory=dict)

    @property
    def full_name(self):
        return f"{self.file}::{self.name}"


@dataclass
class FileInfo:
    path: str
    imports: List[Tuple[str, str]] = field(default_factory=list)         # (module, alias)
    from_imports: List[Tuple[str, str, str]] = field(default_factory=list)  # (module, name, alias)
    global_vars: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    loc: int = 0
    # Package this file belongs to (relative path to __init__.py dir, or "")
    package: str = ""
    # Detected entry-point patterns: list of (kind, name, lineno)
    # kind: "cli_main" | "argparse" | "click" | "django_url" | "odoo_route" | "drf_router"
    entry_points: List[Tuple[str, str, int]] = field(default_factory=list)


# ─────────────────────────────────────────────
#  AST ANALYZER
# ─────────────────────────────────────────────

class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self, filepath: str, root_dir: str):
        self.filepath = filepath
        self.root_dir = root_dir
        self.rel_path = os.path.relpath(filepath, root_dir)

        self.file_info = FileInfo(path=self.rel_path)
        self.functions: Dict[str, FunctionInfo] = {}
        self.classes: Dict[str, ClassInfo] = {}

        self._class_stack: List[str] = []
        self._function_stack: List[FunctionInfo] = []

        # Symbol table: maps local name → qualified source
        # e.g. {"os": "os", "Path": "pathlib.Path", "MyClass": "<local>"}
        self._symbol_table: Dict[str, str] = {}
        # Module aliases: "import os as operating_system" → {"operating_system": "os"}
        self._module_aliases: Dict[str, str] = {}
        # Locally defined names (functions, classes, global vars)
        self._local_defs: Set[str] = set()

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
            used_name = alias.asname or alias.name
            self.file_info.imports.append((alias.name, used_name))
            # "import os" → os resolves to module "os"
            # "import os.path" → os resolves to module "os.path" (top-level only for attr resolution)
            self._symbol_table[used_name] = alias.name
            self._module_aliases[used_name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            used_name = alias.asname or alias.name
            self.file_info.from_imports.append((module, alias.name, used_name))
            # "from pathlib import Path" → Path resolves to "pathlib.Path"
            self._symbol_table[used_name] = f"{module}.{alias.name}" if module else alias.name
        self.generic_visit(node)

    # ── ORM field detection ───────────────────

    # Django: models.ForeignKey / models.ManyToManyField / models.OneToOneField
    # Odoo:   fields.Many2one / fields.One2many / fields.Many2many
    _ORM_RELATION_FIELDS = {
        # Django
        "ForeignKey", "ManyToManyField", "OneToOneField",
        # Odoo / generic
        "Many2one", "One2many", "Many2many",
    }

    def _detect_orm_field(self, value_node) -> Optional[str]:
        """Return the ORM field type if this AST node is a relational field call."""
        if not isinstance(value_node, ast.Call):
            return None
        func = value_node.func
        if isinstance(func, ast.Attribute):
            attr = func.attr
        elif isinstance(func, ast.Name):
            attr = func.id
        else:
            return None
        return attr if attr in self._ORM_RELATION_FIELDS else None

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
                    attr_name = target.id
                    self._record_class_attribute(attr_name)
                    # ORM relational field detection
                    orm_type = self._detect_orm_field(node.value)
                    if orm_type:
                        ckey = self._current_class_key()
                        if ckey and attr_name:
                            self.classes[ckey].orm_fields[attr_name] = orm_type
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
        self._local_defs.add(node.name)
        self._symbol_table[node.name] = "<local>"

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

        if not parent_class:
            # Register as a local top-level symbol so callers can resolve it
            self._local_defs.add(node.name)
            self._symbol_table[node.name] = "<local>"

        if parent_class:
            ckey = f"{self.rel_path}::{parent_class}"
            if ckey in self.classes:
                self.classes[ckey].methods.append(fi.short_name)

        # Entry-point detection via decorators
        self._check_entrypoint_decorators(node, fi)

        self._function_stack.append(fi)
        self.generic_visit(node)
        self._function_stack.pop()

    _CLICK_DECORATORS = {"command", "group", "pass_context", "pass_obj"}
    _ODOO_ROUTE_DECORATORS = {"route", "http.route"}
    _DRF_DECORATORS = {"api_view", "action"}

    def _check_entrypoint_decorators(self, node, fi: "FunctionInfo"):
        for dec_str in fi.decorators:
            lineno = getattr(node, "lineno", 0)
            # click: @click.command / @click.group
            if re.search(r"\bclick\.(command|group)\b", dec_str):
                self.file_info.entry_points.append(("click", fi.name, lineno))
            # Django/Odoo http.route
            elif re.search(r"\bhttp\.route\b", dec_str):
                self.file_info.entry_points.append(("odoo_route", fi.name, lineno))
            # DRF @api_view / @action
            elif re.search(r"\bapi_view\b|\baction\b", dec_str):
                self.file_info.entry_points.append(("drf_router", fi.name, lineno))
            # argparse-style: detect add_argument / parse_args in body via assignment names
        # argparse detection: if function body contains ArgumentParser()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                try:
                    callee = ast.unparse(child.func) if hasattr(ast, "unparse") else ""
                except Exception:
                    callee = ""
                if "ArgumentParser" in callee:
                    self.file_info.entry_points.append(
                        ("argparse", fi.name, getattr(node, "lineno", 0))
                    )
                    break  # only record once per function

    # ── Entry-point detection ─────────────────

    def visit_If(self, node):
        """Detect `if __name__ == '__main__':` blocks."""
        if self._is_main_guard(node):
            self.file_info.entry_points.append(
                ("cli_main", "__main__", getattr(node, "lineno", 0))
            )
        self.generic_visit(node)

    @staticmethod
    def _is_main_guard(node) -> bool:
        test = node.test
        if not isinstance(test, ast.Compare):
            return False
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            return False
        left = test.left
        comps = test.comparators
        if len(comps) != 1:
            return False
        # __name__ == "__main__" or "__main__" == __name__
        def _is_name_attr(n):
            return isinstance(n, ast.Name) and n.id == "__name__"
        def _is_main_str(n):
            return isinstance(n, ast.Constant) and n.value == "__main__"
        return (_is_name_attr(left) and _is_main_str(comps[0])) or \
               (_is_main_str(left) and _is_name_attr(comps[0]))

    # ── Calls ────────────────────────────────

    def _resolve_call(self, node_func) -> Tuple[str, bool]:
        """Return (callee_expr, is_resolved).

        is_resolved=True  when the callee name maps to a local def or an
                          imported name in this file's symbol table.
        is_resolved=False when the name is ambiguous / unknown.
        """
        try:
            callee = ast.unparse(node_func) if hasattr(ast, "unparse") else "call"
        except Exception:
            return ("call", False)

        if isinstance(node_func, ast.Name):
            name = node_func.id
            if name in self._local_defs:
                return (callee, True)
            if name in self._symbol_table:
                return (callee, True)
            return (callee, False)

        if isinstance(node_func, ast.Attribute):
            # module.func() — resolve if module is a known import alias
            if isinstance(node_func.value, ast.Name):
                obj = node_func.value.id
                if obj in self._module_aliases or obj in self._local_defs:
                    return (callee, True)
            return (callee, False)

        return (callee, False)

    def visit_Call(self, node):
        if self._function_stack:
            fi = self._function_stack[-1]
            callee, resolved = self._resolve_call(node.func)
            fi.calls.append(callee)
            if not resolved:
                fi.unresolved_calls.append(callee)
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

    def _detect_package(self, rel_file: str) -> str:
        """Return the package folder for a file (the deepest dir with __init__.py)."""
        parts = rel_file.replace("\\", "/").split("/")
        for i in range(len(parts) - 1, 0, -1):
            pkg_dir = "/".join(parts[:i])
            init = os.path.join(self.root_dir, pkg_dir, "__init__.py")
            if os.path.exists(init):
                return pkg_dir
        return ""

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
                analyzer.file_info.package = self._detect_package(rel_file)
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

    def _detect_entry_function_keys(self) -> List[str]:
        """Return function keys that are real entry points (from file-level detection)."""
        result: List[str] = []
        seen: Set[str] = set()

        # From file-level entry_points metadata
        for file_path, fi in self.files.items():
            for (kind, name, lineno) in fi.entry_points:
                # Find the matching function key
                for fkey, fn in self.functions.items():
                    if fn.file == file_path and fn.name == name and fkey not in seen:
                        result.append(fkey)
                        seen.add(fkey)
                        break

        # Django urls.py — any file named urls.py has implicit entry-point status
        for fkey, fn in self.functions.items():
            if fn.file.endswith("urls.py") and fkey not in seen:
                result.append(fkey)
                seen.add(fkey)

        return result

    def _method_entity_hints(self, method_name: str) -> Set[str]:
        method = (method_name or "").split(".")[-1]
        hints: Set[str] = set()
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

    def _build_import_edges(self) -> Dict[Tuple[str, str], int]:
        """Return {(src_file, dst_file): count} for all intra-project import edges."""
        file_by_name = {os.path.splitext(os.path.basename(k))[0]: k for k in self.files.keys()}
        edges: Dict[Tuple[str, str], int] = defaultdict(int)
        for f, info in self.files.items():
            for module, _alias in info.imports:
                base = module.split(".")[0]
                if base in file_by_name:
                    edges[(f, file_by_name[base])] += 1
            for module, _name, _alias in info.from_imports:
                base = (module or "").split(".")[0]
                if base in file_by_name:
                    edges[(f, file_by_name[base])] += 1
        return dict(edges)

    def write_architecture(self, output_dir: str):
        out = os.path.join(output_dir, "architecture.mmd")
        lines = ["flowchart TD"]

        # Count in-degree (import count) per file to highlight hubs
        import_edges = self._build_import_edges()
        in_degree: Dict[str, int] = defaultdict(int)
        for (src, dst), cnt in import_edges.items():
            in_degree[dst] += cnt

        hub_threshold = 3

        for f in sorted(self.files.keys()):
            fid = self._safe_id(f)
            label = self._short_file_label(f, parts=2)
            if in_degree[f] >= hub_threshold:
                lines.append(f'  {fid}(("{label}")):::hub')
            else:
                lines.append(f'  {fid}["{label}"]')

        # Edges with weight labels (count > 1 shown explicitly)
        seen_edges: Set[Tuple[str, str]] = set()
        for (src, dst), cnt in sorted(import_edges.items()):
            src_id = self._safe_id(src)
            dst_id = self._safe_id(dst)
            edge_key = (src_id, dst_id)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            if cnt > 1:
                lines.append(f"  {src_id} -->|{cnt}| {dst_id}")
            else:
                lines.append(f"  {src_id} --> {dst_id}")

        lines.append("  classDef hub fill:#f96,stroke:#c60,color:#000")

        Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  ✅ {out}")

    def write_package_graph(self, output_dir: str):
        """Write a package-level (folder) dependency graph with edge weights."""
        out = os.path.join(output_dir, "packages.mmd")
        lines = ["flowchart TD", "  %% Package-level dependency graph (folders / Python packages)"]

        # Collect all packages (non-empty package dirs + root "." bucket)
        packages: Set[str] = set()
        for fi in self.files.values():
            pkg = fi.package or "."
            packages.add(pkg)

        # Map file → package
        file_to_pkg: Dict[str, str] = {
            fi.path: (fi.package or ".") for fi in self.files.values()
        }

        # Aggregate import edges to package level
        import_edges = self._build_import_edges()
        pkg_edges: Dict[Tuple[str, str], int] = defaultdict(int)
        for (src_f, dst_f), cnt in import_edges.items():
            src_pkg = file_to_pkg.get(src_f, ".")
            dst_pkg = file_to_pkg.get(dst_f, ".")
            if src_pkg != dst_pkg:
                pkg_edges[(src_pkg, dst_pkg)] += cnt

        # In-degree for hub highlighting
        pkg_in_degree: Dict[str, int] = defaultdict(int)
        for (_, dst), cnt in pkg_edges.items():
            pkg_in_degree[dst] += cnt

        hub_threshold = 5

        for pkg in sorted(packages):
            pid = self._safe_id(pkg)
            label = pkg.replace("/", ".")
            if pkg_in_degree[pkg] >= hub_threshold:
                lines.append(f'  {pid}(("{label}")):::hub')
            else:
                lines.append(f'  {pid}["{label}"]')

        seen_pkg_edges: Set[Tuple[str, str]] = set()
        for (src_pkg, dst_pkg), cnt in sorted(pkg_edges.items(), key=lambda x: -x[1]):
            src_id = self._safe_id(src_pkg)
            dst_id = self._safe_id(dst_pkg)
            edge_key = (src_id, dst_id)
            if edge_key in seen_pkg_edges:
                continue
            seen_pkg_edges.add(edge_key)
            lines.append(f"  {src_id} -->|{cnt}| {dst_id}")

        lines.append("  classDef hub fill:#f96,stroke:#c60,color:#000")

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

    def _build_callgraph_edges(self) -> Tuple[List[Tuple[str, str]], List[str]]:
        """Return (resolved_edges, unresolved_call_exprs).

        resolved_edges: list of (caller_key, callee_key) — both sides known.
        unresolved_call_exprs: flat list of call expressions that could not be
            resolved to a known function in this project.

        Resolution rules (in order):
        1. Call is already tagged as unresolved by CodeAnalyzer → skip edge.
        2. Callee short-name matches exactly one function in the project → edge.
        3. Callee short-name matches multiple functions → draw edges to all
           (ambiguous but better than nothing; we label them "ambiguous").
        4. No match → unresolved.
        """
        short_to_full: Dict[str, List[str]] = defaultdict(list)
        for k, fn in self.functions.items():
            short_to_full[fn.short_name].append(k)
            short_to_full[fn.name].append(k)

        # Build a set of all unresolved call text (per function) for fast lookup
        unresolved_by_fn: Dict[str, Set[str]] = {}
        for fkey, fn in self.functions.items():
            unresolved_by_fn[fkey] = set(fn.unresolved_calls)

        resolved_edges: List[Tuple[str, str]] = []
        unresolved_calls: List[str] = []
        seen_edges: Set[Tuple[str, str]] = set()

        for fkey, fn in self.functions.items():
            fn_unresolved = unresolved_by_fn[fkey]
            for call_expr in fn.calls[:200]:
                # Skip calls the analyzer flagged as unresolved
                if call_expr in fn_unresolved:
                    unresolved_calls.append(call_expr)
                    continue
                callee_short = self._call_to_short_name(call_expr)
                if not callee_short:
                    continue
                targets = short_to_full.get(callee_short, [])
                if not targets:
                    unresolved_calls.append(call_expr)
                    continue
                for target_key in targets:
                    edge = (fkey, target_key)
                    if edge not in seen_edges:
                        seen_edges.add(edge)
                        resolved_edges.append(edge)

        return resolved_edges, unresolved_calls

    def write_callgraph(self, output_dir: str):
        out = os.path.join(output_dir, "callgraph.mmd")
        lines = ["flowchart LR"]

        for fkey, f in sorted(self.functions.items()):
            src = self._safe_id(fkey)
            label = f.short_name.replace('"', "'")
            lines.append(f'  {src}["{label}"]')

        resolved_edges, _unresolved = self._build_callgraph_edges()
        for caller_key, callee_key in resolved_edges:
            src = self._safe_id(caller_key)
            dst = self._safe_id(callee_key)
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

        # Prefer real entry points detected from file analysis
        entries = self._detect_entry_function_keys()
        if not entries:
            # Fallback: name-heuristic
            entries = [k for k, v in self.functions.items() if v.name in ("main", "run", "cli", "execute", "start")]
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

    # ORM field → ERD cardinality mapping
    _ORM_FIELD_CARDINALITY: Dict[str, str] = {
        "ForeignKey":       "}}o--||",   # many-to-one
        "Many2one":         "}}o--||",
        "ManyToManyField":  "}}o--o{",   # many-to-many
        "Many2many":        "}}o--o{",
        "OneToOneField":    "||--||",    # one-to-one
        "One2many":         "||--o{",    # one-to-many (inverse)
    }

    def write_erd(self, output_dir: str):
        out = os.path.join(output_dir, "erd.mmd")
        lines = [
            "erDiagram",
            "  %% ERD: ORM-aware (Django/Odoo fields) + attribute-name heuristics",
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
                    # Use ORM field type if detected, else "string"
                    field_type = cls.orm_fields.get(attr, "string")
                    safe_attr = self._clean_label(attr, max_len=60).replace(" ", "_")
                    lines.append(f"    {field_type} {safe_attr}")
            lines.append("  }")

        relation_lines: Set[str] = set()

        # ORM-aware relationships (highest priority — type-correct)
        for _key, cls in sorted(self.classes.items()):
            for attr_name, field_type in cls.orm_fields.items():
                cardinality = self._ORM_FIELD_CARDINALITY.get(field_type, "}}o--||")
                # Try to find the target model from attribute name
                candidate = attr_name.lower()
                for suffix in ("_id", "_ids", "_id"):
                    if candidate.endswith(suffix):
                        candidate = candidate[: -len(suffix)]
                        break
                candidate = candidate.rstrip("s")
                target_class = lowered_name_to_class.get(candidate)
                if target_class and target_class != cls.name:
                    relation_lines.add(
                        f"  {cls.name} {cardinality} {target_class} : {attr_name}"
                    )

        # Inheritance relationship.
        for _key, cls in sorted(self.classes.items()):
            for base in cls.bases:
                base_name = base.split(".")[-1]
                if base_name in class_names:
                    relation_lines.add(f"  {base_name} ||--|| {cls.name} : inherits")

        # Attribute-name relationship hints (fallback for non-ORM attributes)
        for _key, cls in sorted(self.classes.items()):
            for attr in cls.attributes:
                if attr in cls.orm_fields:
                    continue  # already handled above
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

        # Method-name relationship hints
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

        relationships: List[Dict[str, str]] = []
        seen: Set[Tuple[str, str, str]] = set()

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
            # ORM-aware relationships (higher confidence)
            for attr_name, field_type in cls.orm_fields.items():
                candidate = attr_name.lower()
                for suffix in ("_id", "_ids"):
                    if candidate.endswith(suffix):
                        candidate = candidate[: -len(suffix)]
                        break
                candidate = candidate.rstrip("s")
                target_class = lowered_name_to_class.get(candidate)
                if target_class:
                    add_rel(cls.name, target_class, f"orm:{field_type}", f"attribute:{attr_name}")

            for attr in cls.attributes:
                if attr in cls.orm_fields:
                    continue
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
                "files": {
                    k: {
                        "path": v.path,
                        "loc": v.loc,
                        "package": v.package,
                        "entry_points": v.entry_points,
                    } for k, v in self.files.items()
                },
                "classes": {
                    k: {
                        "name": v.name,
                        "file": v.file,
                        "lineno": v.lineno,
                        "bases": v.bases,
                        "methods": v.methods,
                        "attributes": v.attributes,
                        "orm_fields": v.orm_fields,
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
                        "unresolved_calls": v.unresolved_calls[:20],
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

    def write_triage_json(self, output_dir: str):
        """Write triage.json — machine-readable project health / navigation hints."""
        try:
            # Hot files by LOC
            hot_by_loc = [
                {"file": fi.path, "loc": fi.loc}
                for fi in sorted(self.files.values(), key=lambda x: x.loc, reverse=True)[:20]
            ]

            # Hub files by import in-degree
            import_edges = self._build_import_edges()
            in_degree: Dict[str, int] = defaultdict(int)
            for (_, dst), cnt in import_edges.items():
                in_degree[dst] += cnt
            hub_files = [
                {"file": f, "import_in_degree": cnt}
                for f, cnt in sorted(in_degree.items(), key=lambda x: -x[1])[:20]
            ]

            # All entry points
            entry_points = []
            for fi in self.files.values():
                for kind, name, lineno in fi.entry_points:
                    entry_points.append({
                        "kind": kind,
                        "function": name,
                        "file": fi.path,
                        "lineno": lineno,
                    })

            # Unresolved call count (across whole project)
            total_unresolved = sum(len(fn.unresolved_calls) for fn in self.functions.values())
            unresolved_sample = []
            seen_u: Set[str] = set()
            for fn in self.functions.values():
                for uc in fn.unresolved_calls[:5]:
                    if uc not in seen_u:
                        seen_u.add(uc)
                        unresolved_sample.append(uc)
                    if len(unresolved_sample) >= 30:
                        break
                if len(unresolved_sample) >= 30:
                    break

            triage = {
                "hot_files_by_loc": hot_by_loc,
                "hub_files_by_degree": hub_files,
                "entry_points": entry_points,
                "parse_errors": self.errors[:50],
                "unresolved_calls_count": total_unresolved,
                "unresolved_calls_sample": unresolved_sample,
                "stats": {
                    "files": len(self.files),
                    "classes": len(self.classes),
                    "functions": len(self.functions),
                    "total_loc": sum(fi.loc for fi in self.files.values()),
                },
            }

            out = os.path.join(output_dir, "triage.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump(triage, f, indent=2)
            print(f"  ✅ {out}")
        except Exception as e:
            print(f"  ⚠  Failed to generate triage.json: {e}")

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
        ep_keys = self._detect_entry_function_keys()
        ep_fns = [self.functions[k] for k in ep_keys if k in self.functions]
        # Also include name-heuristic entries not already captured
        entry_names = {"main", "run", "cli", "execute", "start", "app", "setup"}
        for fn in self.functions.values():
            if fn.name in entry_names and not fn.parent_class and fn not in ep_fns:
                ep_fns.append(fn)

        # File-level entry points (with kind labels)
        ep_by_file: Dict[str, List[Tuple[str, str, int]]] = defaultdict(list)
        for fi in self.files.values():
            for kind, name, lineno in fi.entry_points:
                ep_by_file[fi.path].append((kind, name, lineno))

        if ep_fns or ep_by_file:
            lines.append("## Entry points\n")
            shown: Set[str] = set()
            for fn in sorted(ep_fns, key=lambda f: (f.file, f.lineno)):
                key = f"{fn.file}:{fn.name}"
                if key in shown:
                    continue
                shown.add(key)
                lines.append(f"- `{fn.short_name}()` in `{fn.file}` (line {fn.lineno})")
            # Any file-level entry points not covered by function keys
            for fp, eps in sorted(ep_by_file.items()):
                for kind, name, lineno in eps:
                    key = f"{fp}:{name}"
                    if key not in shown:
                        shown.add(key)
                        lines.append(f"- `{name}` [{kind}] in `{fp}` (line {lineno})")
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

        # ── Key call relationships (AST-resolved only) ────────────────────────
        resolved_edges, unresolved_calls = self._build_callgraph_edges()

        cross_file_calls: List[Tuple[str, str, str]] = []
        seen_xf: Set[Tuple[str, str]] = set()
        for caller_key, callee_key in resolved_edges:
            caller_fn = self.functions[caller_key]
            callee_fn = self.functions[callee_key]
            if caller_fn.file != callee_fn.file:
                key = (caller_fn.short_name, callee_fn.short_name)
                if key not in seen_xf:
                    seen_xf.add(key)
                    cross_file_calls.append(
                        (caller_fn.short_name, callee_fn.short_name, callee_fn.file)
                    )

        if cross_file_calls:
            lines.append("## Cross-file call relationships (AST-resolved)\n")
            for caller, callee, callee_file in cross_file_calls[:40]:
                lines.append(f"- `{caller}` → `{callee}()` (in `{callee_file}`)")
            lines.append("")

        if unresolved_calls:
            unique_unresolved = sorted(set(unresolved_calls))
            lines.append("## Unresolved calls (may be external or dynamic)\n")
            lines.append(
                "> These call expressions could not be resolved to a known project "
                "function. They may be stdlib, third-party, or dynamic calls.\n"
            )
            for uc in unique_unresolved[:30]:
                lines.append(f"- `{uc}`")
            lines.append("")

        # ── Top 20 Navigation Index ───────────────────────────────────────────
        lines.append("## Top 20 navigation index\n")
        lines.append(
            "> Start reading here depending on what you are working on.\n"
            "> Files are ranked by import in-degree (hubs first), then by LOC.\n"
        )
        import_edges = self._build_import_edges()
        in_degree: Dict[str, int] = defaultdict(int)
        for (_, dst), cnt in import_edges.items():
            in_degree[dst] += cnt

        # Rank: hub score = in_degree * 3 + LOC/100 (arbitrary blend)
        def _nav_score(fi: "FileInfo") -> float:
            return in_degree.get(fi.path, 0) * 3.0 + fi.loc / 100.0

        nav_files = sorted(self.files.values(), key=_nav_score, reverse=True)[:20]
        for fi in nav_files:
            degree = in_degree.get(fi.path, 0)
            hint = ""
            if fi.entry_points:
                kinds = sorted({k for k, _, _ in fi.entry_points})
                hint = f" [entry: {', '.join(kinds)}]"
            elif degree >= 3:
                hint = " [hub]"
            lines.append(f"- `{fi.path}` — {fi.loc} LOC, imported by {degree} file(s){hint}")
        lines.append("")

        # ── Search hints ──────────────────────────────────────────────────────
        # Build keyword hints from function/class names grouped by package
        pkg_keywords: Dict[str, List[str]] = defaultdict(list)
        for fi in self.files.values():
            pkg = fi.package or fi.path
            for fkey in fi.functions:
                fn = self.functions.get(fkey)
                if fn and fn.name not in ("__init__", "__str__", "__repr__"):
                    pkg_keywords[pkg].append(fn.name)
            for ckey in fi.classes:
                cls = self.classes.get(ckey)
                if cls:
                    pkg_keywords[pkg].append(cls.name)

        if pkg_keywords:
            lines.append("## Search hints by package / area\n")
            lines.append(
                "> Use these keywords when grep-searching or asking the AI about a specific area.\n"
            )
            for pkg in sorted(pkg_keywords.keys()):
                kws = pkg_keywords[pkg]
                if not kws:
                    continue
                # Limit to 10 unique keywords per package
                unique_kws = list(dict.fromkeys(kws))[:10]
                lines.append(f"- **`{pkg}`**: `{'`, `'.join(unique_kws)}`")
            lines.append("")

        # ── Where to find more ────────────────────────────────────────────────
        lines.append("## Where to find more\n")
        lines.append(
            "| Artefact | Purpose |\n"
            "|----------|---------|\n"
            "| `mermaid_output/<target>/architecture.mmd` | File dependency graph (hub-highlighted) |\n"
            "| `mermaid_output/<target>/packages.mmd` | Package-level dependency graph |\n"
            "| `mermaid_output/<target>/classes.mmd` | Class hierarchy |\n"
            "| `mermaid_output/<target>/callgraph.mmd` | AST-resolved function call graph |\n"
            "| `mermaid_output/<target>/workflow.mmd` | Execution flow from real entry points |\n"
            "| `mermaid_output/<target>/erd.mmd` | ORM-aware entity-relationship diagram |\n"
            "| `mermaid_output/<target>/summary.md` | LOC stats + parse errors |\n"
            "| `mermaid_output/<target>/codebase_index.json` | Machine-readable full index |\n"
            "| `mermaid_output/<target>/triage.json` | Hot files, hubs, entry points, unresolved calls |\n"
            "| `AI_PROJECT_MEMORY.md` (repo root) | Curated change history + Decision Registry |\n"
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

        self.write_architecture(output_dir)
        self.write_package_graph(output_dir)
        self.write_classes(output_dir)
        self.write_callgraph(output_dir)
        self.write_workflow(output_dir)
        self.write_erd(output_dir)
        self.write_summary(output_dir)
        self.write_json_index(output_dir)
        self.write_triage_json(output_dir)
        self.write_ai_context_primer(output_dir)
