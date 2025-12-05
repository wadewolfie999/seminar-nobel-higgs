import argparse
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


def run_command(command: List[str]) -> str:
    return subprocess.check_output(command, text=True)


def parse_commits(limit: int) -> List[Dict[str, object]]:
    format_str = "%H%x1f%ad%x1f%s"
    log_output = run_command([
        "git",
        "log",
        f"-n{limit}",
        "--date=short",
        f"--pretty=format:{format_str}",
        "--name-only",
    ])

    commits = []
    current: Dict[str, object] = {}

    for line in log_output.splitlines():
        if "\x1f" in line:
            if current:
                commits.append(current)
            parts = line.split("\x1f")
            current = {
                "hash": parts[0],
                "date": parts[1],
                "message": parts[2],
                "files": [],
            }
        elif line.strip():
            current.setdefault("files", []).append(line.strip())

    if current:
        commits.append(current)

    return commits


def derive_section(files: List[str]) -> str:
    if not files:
        return "General / Metadata"

    top_levels = {path.split("/", 1)[0] for path in files}
    if len(top_levels) == 1:
        return top_levels.pop()

    return "Mixed components"


def first_diff_snippet(commit_hash: str, max_lines: int = 14) -> str:
    show_output = run_command([
        "git",
        "show",
        commit_hash,
        "-U3",
        "--no-color",
    ])

    snippet_lines: List[str] = []
    capture = False

    for line in show_output.splitlines():
        if line.startswith("diff --git"):
            if capture and snippet_lines:
                break
            capture = True

        if capture:
            snippet_lines.append(line)
            if len(snippet_lines) >= max_lines:
                break

    return "\n".join(snippet_lines) if snippet_lines else "(No diff available)"


def group_commits(commits: List[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    for commit in commits:
        files = commit.get("files", [])  # type: ignore[arg-type]
        section = derive_section(files)
        grouped[section].append(commit)

    return grouped


def render_plain(grouped: Dict[str, List[Dict[str, object]]]) -> str:
    lines: List[str] = []

    for section, commits in grouped.items():
        lines.append(f"Section: {section}")
        for commit in commits:
            message = commit["message"]
            commit_hash = commit["hash"]
            intention = message.rstrip(".")
            snippet = first_diff_snippet(commit_hash)

            lines.append(f"  Subtask: {message}")
            lines.append(f"    Intention: {intention}")
            lines.append("    Code Changes Snippet:")
            for snippet_line in snippet.splitlines():
                lines.append(f"      {snippet_line}")
            lines.append(f"    Commit Message: {commit_hash} {message}")
            lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_markdown(grouped: Dict[str, List[Dict[str, object]]]) -> str:
    lines: List[str] = []

    for section, commits in grouped.items():
        lines.append(f"## Section: {section}")
        lines.append("")
        for commit in commits:
            message = commit["message"]
            commit_hash = commit["hash"]
            intention = message.rstrip(".")
            snippet = first_diff_snippet(commit_hash)

            lines.append(f"- **Subtask:** {message}")
            lines.append(f"  - **Intention:** {intention}")
            lines.append("  - **Code Changes Snippet:**")
            lines.append("    ```")
            lines.extend([f"    {line}" for line in snippet.splitlines()])
            lines.append("    ```")
            lines.append(f"  - **Commit Message:** `{commit_hash}` {message}")
            lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate structured commit summaries.")
    parser.add_argument("--limit", type=int, default=15, help="Number of recent commits to summarize.")
    parser.add_argument("--plain", type=Path, default=Path("notes/commit_summary.txt"), help="Path for the plain-text output.")
    parser.add_argument("--markdown", type=Path, default=Path("notes/commit_summary.md"), help="Path for the Markdown output.")

    args = parser.parse_args()

    commits = parse_commits(args.limit)
    grouped = group_commits(commits)

    plain_output = render_plain(grouped)
    markdown_output = render_markdown(grouped)

    args.plain.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)

    args.plain.write_text(plain_output)
    args.markdown.write_text(markdown_output)

    print(f"Wrote plain-text summary to {args.plain}")
    print(f"Wrote Markdown summary to {args.markdown}")


if __name__ == "__main__":
    main()
