#!/usr/bin/env python3
"""Inventory a codebase mechanically so Claude can comprehend it.

This is Phase A of the /scan-codebase pipeline, and it deliberately stops where
judgment begins. It counts, parses declared metadata, and asks git who wrote
what. It does NOT decide what any of that means -- no skill inference, no
proficiency assessment, no resume prose. That is Phase B, and Claude does it by
reading the code, per the "Claude IS the parser" rule in CLAUDE.md.

The line is: anything two people would compute identically belongs here;
anything requiring an opinion does not. Counting `def test_` is measurement.
Concluding "advanced pytest" is comprehension.

Usage:
    python3 tools/scan_codebase.py path/to/repo
    python3 tools/scan_codebase.py path/to/portfolio --all
    python3 tools/scan_codebase.py path/to/repo --author "Jane Doe" --author jdoe
    python3 tools/scan_codebase.py path/to/portfolio --all --out scan.json
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Directories that hold code nobody wrote here. Scanning them inflates every
# count by an order of magnitude and buries the actual work.
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".venv", "venv", "env", "site-packages",
    "dist", "build", ".terraform", ".next", ".nuxt", "vendor", "target",
    ".idea", ".vscode", "coverage", "htmlcov", ".tox", "eggs", ".eggs",
}

# Extension -> language label. Anything unlisted is counted under "other" so the
# totals stay honest rather than silently dropping files.
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java",
    ".c": "C", ".h": "C/C++ header", ".cpp": "C++", ".cc": "C++",
    ".cs": "C#", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala", ".sh": "Shell",
    ".ps1": "PowerShell", ".sql": "SQL", ".r": "R", ".m": "MATLAB/Objective-C",
    ".asm": "Assembly", ".s": "Assembly",
    ".tf": "Terraform", ".tfvars": "Terraform",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".vue": "Vue", ".svelte": "Svelte",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".toml": "TOML",
    ".md": "Markdown", ".rst": "reStructuredText",
}

# Files whose presence says something concrete about how a project is built.
# Reported as found/not found; interpreting them is Claude's job.
SIGNAL_FILES = {
    "Dockerfile": "containerized",
    "docker-compose.yml": "multi-service compose",
    "Procfile": "Heroku/Foreman process definition",
    "manage.py": "Django project",
    "pytest.ini": "pytest configured",
    "tox.ini": "tox configured",
    ".pre-commit-config.yaml": "pre-commit hooks",
    "Makefile": "make-driven build",
    "serverless.yml": "Serverless Framework",
    "requirements.txt": "Python dependencies (pip)",
    "pyproject.toml": "Python packaging",
    "package.json": "Node package",
    "go.mod": "Go module",
    "Cargo.toml": "Rust crate",
    "Gemfile": "Ruby bundle",
}

# Heuristic test-symbol patterns. Counting only -- a match is a candidate test,
# not a verified one, and the report labels it as approximate for that reason.
TEST_PATTERNS = {
    "Python": re.compile(r"^\s*(?:async\s+)?def\s+test_\w*", re.M),
    "JavaScript": re.compile(r"^\s*(?:it|test)\s*\(", re.M),
    "TypeScript": re.compile(r"^\s*(?:it|test)\s*\(", re.M),
    "Go": re.compile(r"^\s*func\s+Test\w+", re.M),
    "Java": re.compile(r"@Test\b", re.M),
}

MAX_FILE_BYTES = 2_000_000  # skip anything larger; it is data, not source
README_CHARS = 1500


def is_test_path(path: Path) -> bool:
    """Whether a path looks like test code, by the conventions people use."""
    parts = {p.lower() for p in path.parts}
    if parts & {"test", "tests", "testing", "spec", "specs", "__tests__"}:
        return True
    stem = path.stem.lower()
    return (
        stem.startswith("test_")
        or stem.endswith("_test")
        or ".test" in path.name.lower()
        or ".spec" in path.name.lower()
    )


def walk_source(root: Path):
    """Yield every source file under root, skipping vendored and build trees."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if SKIP_DIRS & set(path.parts):
            continue
        if path.name.startswith(".") and path.suffix not in LANGUAGES:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def read_text(path: Path) -> str | None:
    """Read a file as text, or return None if it is binary or unreadable."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def git(root: Path, *args: str) -> str | None:
    """Run a git command in root, returning stdout or None if it fails."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def scan_git(root: Path, authors_wanted: list[str] | None) -> dict:
    """Collect commit counts, authorship, and the active date range.

    Authorship is the single most useful fact about a portfolio repo -- it is
    the difference between "built this" and "has this on disk" -- and it is the
    one thing no amount of reading the code will tell you.
    """
    if git(root, "rev-parse", "--git-dir") is None:
        # No git history is not a verdict on the project. Plenty of real work
        # never gets `git init`, and treating these as "not a project" would
        # silently drop it. The only thing missing is the authorship record.
        return {
            "is_repo": False,
            "authorship": "unestablished-no-git",
            "note": (
                "no git history, so authorship cannot be verified from the "
                "repository. This says nothing about whether the project is "
                "real or who built it -- ask the user."
            ),
        }

    log = git(root, "log", "--pretty=format:%an|%aI")
    if not log:
        return {
            "is_repo": True,
            "commits": 0,
            "authorship": "unestablished-no-commits",
            "note": "git initialized but no commits; ask the user about authorship",
        }

    authors, dates = Counter(), []
    for line in log.splitlines():
        name, _, iso = line.partition("|")
        authors[name.strip()] += 1
        if iso:
            dates.append(iso[:10])

    info = {
        "is_repo": True,
        "commits": sum(authors.values()),
        "authors": [
            {"name": name, "commits": count}
            for name, count in authors.most_common()
        ],
        "first_commit": min(dates) if dates else None,
        "last_commit": max(dates) if dates else None,
        "branch": git(root, "rev-parse", "--abbrev-ref", "HEAD"),
    }

    if authors_wanted:
        # Matched against every supplied identity because one person routinely
        # commits under several -- a full name on one machine, a GitHub handle
        # on another. Checking only one silently reports 0 commits for work
        # they entirely wrote, which reads as "not theirs".
        wanted = [a.lower() for a in authors_wanted]
        matched = sum(
            count for name, count in authors.items()
            if any(a in name.lower() for a in wanted)
        )
        info["author_filter"] = authors_wanted
        info["author_commits"] = matched
        info["author_share"] = (
            round(matched / info["commits"], 3) if info["commits"] else 0.0
        )
        info["authorship"] = "verified" if matched else "unmatched"
        if matched == 0:
            info["author_warning"] = (
                "none of the supplied identities match any committer; confirm "
                "authorship with the user before recording anything from this repo"
            )
    else:
        info["authorship"] = "unchecked-no-author-supplied"
    return info


def parse_dependencies(root: Path) -> dict:
    """Collect declared dependency names from standard manifests.

    Names only, unresolved and uninterpreted. A dependency being declared does
    not mean it is used meaningfully, which is exactly the judgment this script
    refuses to make.
    """
    deps: dict[str, list[str]] = {}

    req = root / "requirements.txt"
    if req.is_file():
        text = read_text(req) or ""
        names = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            names.append(re.split(r"[<>=!~\[; ]", line)[0].strip())
        if names:
            deps["requirements.txt"] = sorted({n for n in names if n})

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = read_text(pyproject) or ""
        # Deliberately regex rather than a TOML parse: this needs to work on a
        # malformed or partially-written file, and only the names are wanted.
        # Scoped to dependency arrays specifically -- matching every quoted
        # string in the file also collects console-script names and classifiers.
        names = []
        for block in re.findall(
            r'(?:^|\n)\s*(?:\w[\w.\-]*\s*=\s*)?\[?[^\n]*'
            r'dependencies\s*=\s*\[(.*?)\]', text, re.S | re.I
        ):
            names += re.findall(r'"([A-Za-z0-9_.\-]+)[^"]*"', block)
        if names:
            deps["pyproject.toml"] = sorted(set(names))

    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(read_text(pkg) or "{}")
            names = sorted({
                *data.get("dependencies", {}),
                *data.get("devDependencies", {}),
            })
            if names:
                deps["package.json"] = names
        except (json.JSONDecodeError, AttributeError):
            pass

    for manifest, pattern in (
        ("go.mod", r"^\s+([\w./\-]+)\s+v"),
        ("Cargo.toml", r'^\s*([A-Za-z0-9_\-]+)\s*='),
    ):
        path = root / manifest
        if path.is_file():
            found = re.findall(pattern, read_text(path) or "", re.M)
            if found:
                deps[manifest] = sorted(set(found))

    return deps


def scan_repo(root: Path, author: str | list[str] | None = None) -> dict:
    """Produce the full mechanical inventory for one repository."""
    root = root.resolve()
    if isinstance(author, str):
        author = [author]

    languages: dict[str, dict[str, int]] = {}
    test_files = test_symbols = 0
    total_files = total_lines = 0
    largest: list[tuple[int, str]] = []

    for path in walk_source(root):
        lang = LANGUAGES.get(path.suffix.lower(), "other")
        text = read_text(path)
        if text is None:
            continue

        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        blank = sum(1 for line in text.splitlines() if not line.strip())

        entry = languages.setdefault(lang, {"files": 0, "lines": 0, "blank": 0})
        entry["files"] += 1
        entry["lines"] += lines
        entry["blank"] += blank

        total_files += 1
        total_lines += lines
        largest.append((lines, str(path.relative_to(root)).replace("\\", "/")))

        if is_test_path(path):
            test_files += 1
            pattern = TEST_PATTERNS.get(lang)
            if pattern:
                test_symbols += len(pattern.findall(text))

    largest.sort(reverse=True)

    code_lines = sum(
        v["lines"] for k, v in languages.items()
        if k not in {"JSON", "YAML", "Markdown", "TOML", "reStructuredText", "other"}
    )

    signals = {
        name: desc for name, desc in SIGNAL_FILES.items()
        if (root / name).is_file()
    }
    if (root / ".github" / "workflows").is_dir():
        workflows = list((root / ".github" / "workflows").glob("*.y*ml"))
        if workflows:
            signals["GitHub Actions"] = f"{len(workflows)} workflow file(s)"

    readme = None
    for candidate in ("README.md", "README.rst", "README.txt", "README"):
        path = root / candidate
        if path.is_file():
            text = read_text(path)
            if text:
                readme = text[:README_CHARS]
                break

    top_level = sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith(".")
    )

    return {
        "name": root.name,
        "path": str(root),
        "totals": {
            "files": total_files,
            "lines": total_lines,
            "code_lines": code_lines,
            "test_files": test_files,
            "test_symbols_approx": test_symbols,
        },
        "languages": dict(sorted(
            languages.items(), key=lambda kv: kv[1]["lines"], reverse=True
        )),
        "largest_files": [
            {"lines": n, "path": p} for n, p in largest[:15]
        ],
        "top_level_dirs": top_level,
        "signal_files": signals,
        "dependencies": parse_dependencies(root),
        "git": scan_git(root, author),
        "readme_excerpt": readme,
    }


def collect_authors(repos: list[dict]) -> list[dict]:
    """Roll every committer seen across all repos into one roster.

    One person commits under several identities -- a full name, a bare first
    name, a hosting handle -- and no scan can tell which of them are the same
    human. Presenting the whole roster and asking is the only reliable way to
    resolve it, and getting it wrong in either direction is expensive: unclaimed
    identities lose real work, over-claimed ones attribute someone else's.
    """
    totals: Counter = Counter()
    appearances: dict[str, list[str]] = {}
    for repo in repos:
        for author in repo.get("git", {}).get("authors", []):
            name = author["name"]
            totals[name] += author["commits"]
            appearances.setdefault(name, []).append(repo["name"])
    return [
        {"name": name, "commits": count, "repos": sorted(appearances[name])}
        for name, count in totals.most_common()
    ]


def find_repos(parent: Path) -> list[Path]:
    """Return every immediate subdirectory of parent, git-tracked or not.

    Deliberately does not require a .git directory. A project without one is
    still a project -- it just has no authorship record -- and filtering on git
    would quietly drop real work from the scan.
    """
    repos = []
    for child in sorted(parent.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIRS:
            continue
        if child.name.startswith("."):
            continue
        repos.append(child)
    return repos


def main():
    parser = argparse.ArgumentParser(
        description="Mechanically inventory a codebase for profile building"
    )
    parser.add_argument("path", help="Repository, or parent directory with --all")
    parser.add_argument(
        "--all", action="store_true",
        help="Treat path as a parent directory and scan each subdirectory",
    )
    parser.add_argument(
        "--author", action="append", metavar="NAME",
        help="Attribute commits to this author (substring match on git author "
             "name). Repeatable -- pass every identity the person commits "
             "under, e.g. --author 'Jane Doe' --author jdoe",
    )
    parser.add_argument("--out", help="Write JSON here instead of stdout")
    args = parser.parse_args()

    root = Path(args.path).expanduser()
    if not root.is_dir():
        print(f"Error: {root} is not a directory.", file=sys.stderr)
        sys.exit(1)

    if args.all:
        targets = find_repos(root)
        if not targets:
            print(f"Error: no subdirectories to scan in {root}.", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [root]

    repos, errors = [], []
    for target in targets:
        try:
            repos.append(scan_repo(target, args.author))
        except OSError as e:
            errors.append({"path": str(target), "error": str(e)})

    result = {
        "status": "scanned",
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "root": str(root.resolve()),
        "repo_count": len(repos),
        "without_git_history": sorted(
            r["name"] for r in repos if not r["git"].get("is_repo")
        ),
        # Every committer seen anywhere in the scan. The caller must show this
        # to the person and ask which identities are theirs before attributing
        # anything -- see collect_authors().
        "all_authors": collect_authors(repos),
        "errors": errors,
        # Stated in the output itself so it travels with the data: a consumer
        # reading this file alone still learns that nothing here is a judgment.
        "note": (
            "Mechanical counts only. Nothing here is a skill claim, a proficiency "
            "assessment, or resume content. Read the code to determine what was "
            "actually built before writing anything into profile.json. Confirm "
            "which entries in all_authors are the person before attributing any "
            "work; a directory in without_git_history is still a real project, "
            "it just has no authorship record to check."
        ),
        "repos": repos,
    }

    text = json.dumps(result, indent=2)
    if args.out:
        # Create the parent rather than failing after the scan: a large --all
        # run takes real time, and losing it to a missing directory is a bad
        # trade for a check that costs nothing.
        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(json.dumps({
            "status": "scanned",
            "repo_count": len(repos),
            "out": args.out,
        }, indent=2))
    else:
        print(text)


if __name__ == "__main__":
    main()
