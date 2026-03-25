#!/usr/bin/env python3
"""
gitlab_recap.py - Generate a recap of a team member's GitLab contributions

Fetches MRs and issues for a given user over a time period.

Usage:
    python gitlab_recap.py @Olimarmite                # Last 6 months
    python gitlab_recap.py @Olimarmite --months 12    # Last 12 months
    python gitlab_recap.py @Olimarmite --stdout       # Print to stdout
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from pathlib import Path


def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error: {' '.join(cmd)}", file=sys.stderr)
        print(f"  {e.stderr}", file=sys.stderr)
        return None


def fetch_user(username):
    """Look up a GitLab user by username"""
    output = run_command(["glab", "api", f"users?username={username}"])
    if not output:
        return None
    data = json.loads(output)
    if not isinstance(data, list) or not data:
        return None
    return data[0]


def fetch_all_mrs(user_id, since, until):
    """Fetch all MRs (any state) for a user in the period, paginated"""
    all_mrs = {}
    for state in ["merged", "opened", "closed"]:
        page = 1
        while True:
            output = run_command(
                [
                    "glab",
                    "api",
                    f"merge_requests?author_id={user_id}&state={state}&scope=all"
                    f"&updated_after={since}&updated_before={until}"
                    f"&per_page=100&page={page}",
                ]
            )
            if not output:
                break
            data = json.loads(output)
            if not isinstance(data, list) or not data:
                break
            for mr in data:
                if isinstance(mr, dict):
                    all_mrs[mr["id"]] = mr
            if len(data) < 100:
                break
            page += 1

    return list(all_mrs.values())


def get_repo_short_name(item):
    ref = item.get("references", {}).get("full", "")
    parts = ref.split("/")
    if len(parts) >= 2:
        return re.sub(r"[!#]\d+$", "", parts[-1])
    return "unknown"


def group_by_repo(items):
    groups = defaultdict(list)
    for item in items:
        groups[get_repo_short_name(item)].append(item)
    return dict(sorted(groups.items()))


def format_mr(mr):
    iid = mr["iid"]
    url = mr["web_url"]
    title = mr["title"]
    merged_at = mr.get("merged_at")
    date_str = ""
    if merged_at:
        date_str = f" ({merged_at[:10]})"
    return f"- [!{iid}]({url}): {title}{date_str}"


def generate_recap(user, mrs, since_date, until_date):
    name = user.get("name", user["username"])
    username = user["username"]

    # Categorize
    merged = sorted(
        [mr for mr in mrs if mr.get("state") == "merged" and mr.get("merged_at")],
        key=lambda m: m["merged_at"],
    )
    opened = [mr for mr in mrs if mr.get("state") == "opened"]
    closed = [mr for mr in mrs if mr.get("state") == "closed"]

    # Group merged by month
    merged_by_month = defaultdict(list)
    for mr in merged:
        month_key = mr["merged_at"][:7]  # YYYY-MM
        merged_by_month[month_key].append(mr)

    # Repos touched
    repos = set(get_repo_short_name(mr) for mr in merged)

    period = f"{since_date.strftime('%B %Y')} — {until_date.strftime('%B %Y')}"

    lines = [
        f"# {name} (@{username}) — Recap",
        f"*{period}*",
        "",
        "## Summary",
        f"- {len(merged)} MRs merged | {len(opened)} MRs open | {len(closed)} MRs closed",
        f"- {len(repos)} repos: {', '.join(sorted(repos))}",
        "",
    ]

    # Merged by month (chronological)
    if merged:
        lines.append(f"## Shipped ({len(merged)} MRs merged)")
        lines.append("")
        for month_key in sorted(merged_by_month.keys()):
            month_mrs = merged_by_month[month_key]
            month_label = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
            lines.append(f"### {month_label} ({len(month_mrs)} MRs)")
            groups = group_by_repo(month_mrs)
            for repo, repo_mrs in groups.items():
                lines.append(f"**{repo}:**")
                for mr in repo_mrs:
                    lines.append(format_mr(mr))
            lines.append("")

    # Still open
    if opened:
        lines.append(f"## Still Open ({len(opened)} MRs)")
        groups = group_by_repo(opened)
        for repo, repo_mrs in groups.items():
            lines.append(f"**{repo}:**")
            for mr in repo_mrs:
                lines.append(format_mr(mr))
        lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a recap of a team member's GitLab contributions"
    )
    parser.add_argument(
        "user",
        help="GitLab username (with or without @)",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="Number of months to look back (default: 6)",
    )
    parser.add_argument("--stdout", action="store_true", help="Print to stdout")
    args = parser.parse_args()

    username = args.user.lstrip("@")

    # Look up user
    print(f"Looking up @{username}...", file=sys.stderr)
    user = fetch_user(username)
    if not user:
        print(f"User @{username} not found", file=sys.stderr)
        sys.exit(1)
    print(f"Found: {user['name']} (ID: {user['id']})", file=sys.stderr)

    # Date range
    now = datetime.now(timezone.utc)
    since_date = now - relativedelta(months=args.months)
    since = since_date.strftime("%Y-%m-01T00:00:00Z")
    until = now.strftime("%Y-%m-%dT23:59:59Z")

    # Fetch MRs
    print(f"Fetching MRs from {since[:10]} to {until[:10]}...", file=sys.stderr)
    mrs = fetch_all_mrs(user["id"], since, until)
    print(f"  {len(mrs)} MRs total", file=sys.stderr)

    # Generate
    content = generate_recap(user, mrs, since_date, now)

    if args.stdout:
        print(content)
    else:
        filename = f"recap-{username}-{now.strftime('%Y-%m-%d')}.md"
        filepath = Path(filename)
        filepath.write_text(content)
        print(f"✓ Saved to {filepath}", file=sys.stderr)


if __name__ == "__main__":
    main()
