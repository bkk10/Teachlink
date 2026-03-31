"""
Generate an auto feature document from Python code docstrings and tagged comments.

Usage:
    python scripts/generate-feature-docs.py
    python scripts/generate-feature-docs.py --output docs/AUTO_FEATURES.md
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List


TAGGED_COMMENT_RE = re.compile(r"^\s*#\s*(FEATURE|DOC|NOTE)\s*:\s*(.+)\s*$")


@dataclass
class MethodDoc:
    name: str
    doc: str


@dataclass
class ClassDoc:
    name: str
    doc: str
    methods: List[MethodDoc] = field(default_factory=list)


@dataclass
class FileDoc:
    path: Path
    module_doc: str
    tagged_comments: List[str]
    functions: List[MethodDoc]
    classes: List[ClassDoc]

    @property
    def has_content(self) -> bool:
        return bool(
            self.module_doc
            or self.tagged_comments
            or self.functions
            or self.classes
        )


def short_doc(doc: str) -> str:
    clean = (doc or "").strip().replace("\r\n", "\n")
    if not clean:
        return ""
    first_line = clean.split("\n", 1)[0].strip()
    return first_line


def extract_tagged_comments(source: str) -> List[str]:
    tags: List[str] = []
    for line in source.splitlines():
        match = TAGGED_COMMENT_RE.match(line)
        if match:
            tags.append(f"{match.group(1)}: {match.group(2).strip()}")
    return tags


def extract_file_docs(path: Path, include_private: bool = False) -> FileDoc:
    source = path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source)

    module_doc = short_doc(ast.get_docstring(tree) or "")
    tagged_comments = extract_tagged_comments(source)

    functions: List[MethodDoc] = []
    classes: List[ClassDoc] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not include_private and node.name.startswith("_"):
                continue
            doc = short_doc(ast.get_docstring(node) or "")
            if doc:
                functions.append(MethodDoc(name=node.name, doc=doc))
            continue

        if isinstance(node, ast.ClassDef):
            if not include_private and node.name.startswith("_"):
                continue
            class_doc = short_doc(ast.get_docstring(node) or "")
            class_item = ClassDoc(name=node.name, doc=class_doc, methods=[])
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not include_private and child.name.startswith("_"):
                        continue
                    method_doc = short_doc(ast.get_docstring(child) or "")
                    if method_doc:
                        class_item.methods.append(MethodDoc(name=child.name, doc=method_doc))
            if class_item.doc or class_item.methods:
                classes.append(class_item)

    return FileDoc(
        path=path,
        module_doc=module_doc,
        tagged_comments=tagged_comments,
        functions=functions,
        classes=classes,
    )


def iter_python_files(root: Path, source_dirs: Iterable[str]) -> Iterable[Path]:
    skip_parts = {"venv", "__pycache__", "migrations", ".git", ".claude", ".vscode"}
    for dir_name in source_dirs:
        base_dir = root / dir_name
        if not base_dir.exists():
            continue
        for path in base_dir.rglob("*.py"):
            if any(part in skip_parts for part in path.parts):
                continue
            yield path


def build_markdown(root: Path, docs: List[FileDoc], scanned_files: int) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines: List[str] = []
    lines.append("# Auto Feature Documentation")
    lines.append("")
    lines.append("Generated from Python module/class/function docstrings and tagged comments.")
    lines.append("")
    lines.append(f"- Generated: {generated_at}")
    lines.append(f"- Files scanned: {scanned_files}")
    lines.append(f"- Files with extracted feature docs: {len(docs)}")
    lines.append("")
    lines.append("## How To Improve This Output")
    lines.append("")
    lines.append("- Add meaningful docstrings to modules, views, services, and models.")
    lines.append("- Add tagged comments like `# FEATURE: ...` for key capabilities.")
    lines.append("- Re-run this script after code updates.")
    lines.append("")

    for item in docs:
        rel_path = item.path.relative_to(root).as_posix()
        lines.append(f"## `{rel_path}`")
        lines.append("")

        if item.module_doc:
            lines.append(f"**Module:** {item.module_doc}")
            lines.append("")

        if item.tagged_comments:
            lines.append("**Tagged Features**")
            lines.append("")
            for tag in item.tagged_comments:
                lines.append(f"- {tag}")
            lines.append("")

        if item.functions:
            lines.append("**Functions**")
            lines.append("")
            for fn in item.functions:
                lines.append(f"- `{fn.name}`: {fn.doc}")
            lines.append("")

        if item.classes:
            lines.append("**Classes**")
            lines.append("")
            for cls in item.classes:
                class_line = f"- `{cls.name}`"
                if cls.doc:
                    class_line += f": {cls.doc}"
                lines.append(class_line)
                for method in cls.methods:
                    lines.append(f"  - `{method.name}`: {method.doc}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate feature docs from code comments/docstrings.")
    parser.add_argument(
        "--output",
        default="docs/AUTO_FEATURES.md",
        help="Output markdown path (default: docs/AUTO_FEATURES.md)",
    )
    parser.add_argument(
        "--dirs",
        nargs="*",
        default=["dashboard", "analytics", "courses", "assessments", "users"],
        help="Source directories to scan",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private symbols starting with underscore",
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    root = script_path.parent.parent
    output_path = (root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scanned_files = 0
    extracted_docs: List[FileDoc] = []

    for file_path in sorted(iter_python_files(root, args.dirs)):
        scanned_files += 1
        try:
            file_doc = extract_file_docs(file_path, include_private=args.include_private)
        except SyntaxError:
            continue
        if file_doc.has_content:
            extracted_docs.append(file_doc)

    content = build_markdown(root, extracted_docs, scanned_files)
    output_path.write_text(content, encoding="utf-8")

    print(f"[feature-docs] Generated: {output_path}")
    print(f"[feature-docs] Files scanned: {scanned_files}")
    print(f"[feature-docs] Files documented: {len(extracted_docs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
