#!/usr/bin/env python3
"""3-way merge of the Flectra CORE package up to Odoo 19.

Trees (roots):
  OURS   = /Users/dean/code_env/flectra/flectra
  BASE   = /Users/dean/code_env/flectra/migration/staging/flectra18-base
  THEIRS = /Users/dean/code_env/flectra/migration/staging/flectra

Output merged tree:
  /Users/dean/code_env/flectra/migration/staging/flectra-merged

Categories per relative path:
  A present in OURS, BASE, THEIRS -> git merge-file --diff3
  B in OURS+BASE, not THEIRS      -> removed-upstream (copy OURS, flag)
  C in BASE+THEIRS, not OURS      -> took-upstream (flectra-deleted) copy THEIRS
  D in THEIRS only                -> new-in-19 (copy THEIRS)
  E in OURS only                  -> flectra-original (copy OURS)
  F in OURS+THEIRS, not BASE       -> added-both-review (2-way, copy OURS, flag)
"""
import os
import shutil
import subprocess
import json

OURS = "/Users/dean/code_env/flectra/flectra"
BASE = "/Users/dean/code_env/flectra/migration/staging/flectra18-base"
THEIRS = "/Users/dean/code_env/flectra/migration/staging/flectra"
MERGED = "/Users/dean/code_env/flectra/migration/staging/flectra-merged"

IGNORE_DIRS = {"__pycache__", ".git"}


def walk_rel(root):
    paths = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for f in filenames:
            if f.endswith(".pyc") or f.endswith(".pyo"):
                continue
            full = os.path.join(dirpath, f)
            paths.add(os.path.relpath(full, root))
    return paths


def ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def copy_file(src_root, rel, dst_root):
    src = os.path.join(src_root, rel)
    dst = os.path.join(dst_root, rel)
    ensure_parent(dst)
    shutil.copy2(src, dst)


def count_conflict_hunks(text):
    return text.count("<<<<<<<")


def is_binary(path):
    with open(path, "rb") as fh:
        chunk = fh.read(8192)
    return b"\x00" in chunk


def files_equal(a, b):
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def main():
    if os.path.exists(MERGED):
        shutil.rmtree(MERGED)
    os.makedirs(MERGED)

    ours = walk_rel(OURS)
    base = walk_rel(BASE)
    theirs = walk_rel(THEIRS)

    allpaths = ours | base | theirs

    records = {c: [] for c in "ABCDEFG"}
    conflicts = []  # (rel, hunks)
    binary_conflicts = []  # rel

    for rel in sorted(allpaths):
        in_o = rel in ours
        in_b = rel in base
        in_t = rel in theirs
        dst = os.path.join(MERGED, rel)

        if in_o and in_b and in_t:
            # Category A: 3-way merge
            o = os.path.join(OURS, rel)
            b = os.path.join(BASE, rel)
            t = os.path.join(THEIRS, rel)
            ensure_parent(dst)
            if is_binary(o) or is_binary(b) or is_binary(t):
                # git merge-file cannot merge binaries. Take THEIRS (Odoo 19);
                # only a real conflict if OURS and THEIRS differ.
                shutil.copy2(t, dst)
                bin_conflict = not files_equal(o, t)
                records["A"].append({
                    "rel": rel,
                    "conflicted": False,
                    "binary": True,
                    "binary_conflict": bin_conflict,
                    "hunks": 0,
                    "returncode": None,
                })
                if bin_conflict:
                    binary_conflicts.append(rel)
                continue
            proc = subprocess.run(
                ["git", "merge-file", "-p", "--diff3", o, b, t],
                capture_output=True,
            )
            merged_bytes = proc.stdout
            with open(dst, "wb") as fh:
                fh.write(merged_bytes)
            try:
                text = merged_bytes.decode("utf-8", "replace")
            except Exception:
                text = ""
            hunks = count_conflict_hunks(text)
            conflicted = hunks > 0
            records["A"].append({
                "rel": rel,
                "conflicted": conflicted,
                "binary": False,
                "hunks": hunks,
                "returncode": proc.returncode,
            })
            if conflicted:
                conflicts.append((rel, hunks))
        elif in_o and in_b and not in_t:
            # Category B: removed-upstream
            copy_file(OURS, rel, MERGED)
            records["B"].append(rel)
        elif in_b and in_t and not in_o:
            # Category C: took-upstream (flectra-deleted)
            copy_file(THEIRS, rel, MERGED)
            records["C"].append(rel)
        elif in_t and not in_b and not in_o:
            # Category D: new-in-19
            copy_file(THEIRS, rel, MERGED)
            records["D"].append(rel)
        elif in_o and not in_b and not in_t:
            # Category E: flectra-original
            copy_file(OURS, rel, MERGED)
            records["E"].append(rel)
        elif in_o and in_t and not in_b:
            # Category F: added-both-review (2-way, copy OURS)
            copy_file(OURS, rel, MERGED)
            records["F"].append(rel)
        elif in_b and not in_o and not in_t:
            # Category G: BASE only -> dropped by both flectra and odoo19. Do not copy.
            records["G"].append(rel)
        else:
            raise RuntimeError("unclassified: %s (o=%s b=%s t=%s)" % (rel, in_o, in_b, in_t))

    conflicts.sort(key=lambda x: x[1], reverse=True)

    summary = {
        "counts": {c: len(records[c]) for c in "ABCDEFG"},
        "A_clean": sum(1 for r in records["A"] if not r["conflicted"]),
        "A_conflicted": sum(1 for r in records["A"] if r["conflicted"]),
        "records": records,
        "conflicts": conflicts,
        "binary_conflicts": binary_conflicts,
    }
    with open("/Users/dean/code_env/flectra/migration/_merge_summary.json", "w") as fh:
        json.dump(summary, fh, indent=1)

    print("counts:", summary["counts"])
    print("A clean:", summary["A_clean"], "A conflicted:", summary["A_conflicted"])


if __name__ == "__main__":
    main()
