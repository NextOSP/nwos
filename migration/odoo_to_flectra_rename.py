#!/usr/bin/env python3
"""Odoo -> Flectra core rename tool.

Recursively copies a source tree to a destination tree, applying Flectra's
conservative rename conventions to TEXT file contents. Binary/other files are
copied unchanged. Idempotent: re-running produces the same result.

Rename rules (deliberately conservative -- a separate branding pass handles
URLs / branding strings / comments later):

  * Python namespace imports (word-boundary):
      `from odoo`   -> `from flectra`
      `import odoo`  -> `import flectra`
  * Dotted namespace roots only:
      `odoo.<root>`  -> `flectra.<root>`   for a fixed allow-list of roots.
    This intentionally does NOT touch `odoo.com`, `odoo.sh`, `www.odoo.*`.
  * Config / bin conventions:
      `.odoorc`    -> `.flectrarc`
      `odoo.conf`  -> `flectra.conf`
      `odoo-bin`   -> `flectra-bin`

No blind global `odoo` -> `flectra` replacement is performed.
"""

import argparse
import os
import re
import shutil
import sys

# Extensions treated as text (contents rewritten). Extensionless files are
# sniffed for binary content and treated as text when they look textual.
TEXT_EXTENSIONS = {
    ".py", ".xml", ".js", ".csv", ".cfg", ".txt", ".rst", ".md",
    ".po", ".pot", ".conf",
}

# Namespace roots that are genuinely part of the odoo python package and must
# be renamed. URL-ish suffixes (com, sh, ...) are deliberately absent.
NAMESPACE_ROOTS = [
    "addons", "api", "fields", "models", "orm", "tools", "http",
    "exceptions", "osv", "service", "modules", "release", "sql_db",
    "netsvc", "cli", "conf", "tests", "upgrade", "upgrade_code",
    "loglevels", "logging", "init", "_monkeypatches", "microkernel",
    "sql", "technical",
]

# `from odoo` / `import odoo` at a word boundary. The trailing lookahead keeps
# us from matching e.g. `import odoofoo` while still allowing `import odoo`,
# `import odoo.x`, `import odoo,` `from odoo import ...`, etc.
_IMPORT_RE = re.compile(r"\b(from|import)\s+odoo\b")

# `odoo.<root>` where <root> is one of the known package roots, at a word
# boundary on both sides so `myodoo.api` or `odoo.command` are left alone.
_DOTTED_RE = re.compile(
    r"\bodoo\.(" + "|".join(re.escape(r) for r in NAMESPACE_ROOTS) + r")\b"
)


def transform_text(text):
    """Apply the rename rules to a text blob and return the new text."""
    text = _IMPORT_RE.sub(lambda m: "%s flectra" % m.group(1), text)
    text = _DOTTED_RE.sub(lambda m: "flectra.%s" % m.group(1), text)
    # Config / bin conventions.
    text = text.replace(".odoorc", ".flectrarc")
    text = text.replace("odoo.conf", "flectra.conf")
    text = text.replace("odoo-bin", "flectra-bin")
    return text


def looks_binary(path):
    """Heuristic: a NUL byte in the first 8KB means binary."""
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def is_text_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTENSIONS:
        return True
    if ext == "":
        return not looks_binary(path)
    return False


def process_tree(src, dst):
    files_copied = 0
    files_modified = 0

    for root, dirs, files in os.walk(src):
        # Skip caches and VCS noise; keep the copy clean and idempotent.
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        rel = os.path.relpath(root, src)
        dst_root = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(dst_root, exist_ok=True)

        for name in files:
            src_path = os.path.join(root, name)
            if os.path.islink(src_path):
                # Preserve symlinks as-is.
                dst_path = os.path.join(dst_root, name)
                if os.path.lexists(dst_path):
                    os.remove(dst_path)
                os.symlink(os.readlink(src_path), dst_path)
                files_copied += 1
                continue

            dst_path = os.path.join(dst_root, name)

            if is_text_file(src_path):
                with open(src_path, "r", encoding="utf-8", errors="surrogateescape") as fh:
                    original = fh.read()
                transformed = transform_text(original)
                with open(dst_path, "w", encoding="utf-8", errors="surrogateescape") as fh:
                    fh.write(transformed)
                shutil.copymode(src_path, dst_path)
                files_copied += 1
                if transformed != original:
                    files_modified += 1
            else:
                shutil.copy2(src_path, dst_path)
                files_copied += 1

    return files_copied, files_modified


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rename an Odoo tree to Flectra conventions.")
    parser.add_argument("--src", required=True, help="Source tree (read-only).")
    parser.add_argument("--dst", required=True, help="Destination tree.")
    args = parser.parse_args(argv)

    src = os.path.abspath(args.src)
    dst = os.path.abspath(args.dst)

    if not os.path.isdir(src):
        parser.error("source is not a directory: %s" % src)
    if os.path.abspath(dst).startswith(src + os.sep):
        parser.error("destination must not live inside the source tree")

    os.makedirs(dst, exist_ok=True)
    copied, modified = process_tree(src, dst)
    print("Files copied:   %d" % copied)
    print("Files modified: %d" % modified)
    return 0


if __name__ == "__main__":
    sys.exit(main())
