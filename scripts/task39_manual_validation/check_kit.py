"""Read-only checks for Task 39 relative links, UI route references and blank matrix results."""

import ast
import re
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    kit = root / "docs/learnlens/task-39-manual-validation"
    docs = sorted(kit.glob("*.md")) + [kit.parent / "task-39-manual-validation-kit.md"]
    errors = []
    links = 0
    route_checks = 0
    app = (root / "src-main/frontend/src/App.tsx").read_text(encoding="utf-8")
    routes = re.findall(r'<Route\s+path="([^"]+)"', app)
    route_patterns = [
        re.compile("^" + re.sub(r":[A-Za-z]+", "[^/]+", route) + "$")
        for route in routes
        if route != "*"
    ]
    for doc in docs:
        if not doc.exists():
            errors.append(f"Missing {doc.relative_to(root)}")
            continue
        content = doc.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if target.startswith(("http://", "https://", "#")):
                continue
            target = target.split("#", 1)[0]
            links += 1
            if not (doc.parent / target).resolve().exists():
                errors.append(f"{doc.name}: broken relative link {target}")
        # Deliberately excludes prose wildcards, API URLs and intentional not-found paths.
        for route in re.findall(
            r"`(/(?:student|educator|assessor|admin|login|escalations)(?:/[^` ]*)?)`",
            content,
        ):
            if "..." in route:
                continue
            path = route.split("?", 1)[0]
            route_checks += 1
            if not any(pattern.fullmatch(path) for pattern in route_patterns):
                errors.append(f"{doc.name}: unknown UI route {route}")
    rows = []
    for line in (kit / "role-matrix.md").read_text(encoding="utf-8").splitlines():
        if re.match(r"\| [GSEAD]\d{2};", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows.append(cells[0].split(";", 1)[0])
            if len(cells) != 6 or cells[-2:] != ["", ""]:
                errors.append(
                    f"Matrix result/evidence not blank or invalid columns: {cells[0]}"
                )
    if len(rows) != len(set(rows)) or not rows:
        errors.append("Missing or duplicate matrix case IDs")
    for script in Path(__file__).parent.glob("*.py"):
        ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    for error in errors:
        print(error)
    print(
        f"Checked {len(docs)} documents, {links} relative links, {route_checks} UI route references, {len(rows)} blank cases and helper syntax; errors={len(errors)}"
    )
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
