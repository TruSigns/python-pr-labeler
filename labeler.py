"""
PR auto-labeler for GitHub Actions.

Reads the PR event payload GitHub provides, fetches the list of changed
files from the GitHub API, matches them against label-rules.yml, and
applies the resulting labels to the PR.

Fails loudly on any missing config, bad auth, or API error rather than
silently skipping labeling.
"""

import fnmatch
import json
import os
import sys

import requests
import yaml

GITHUB_API = "https://api.github.com"


def load_event_payload(event_path: str) -> dict:
    """Read the event JSON GitHub Actions writes for this workflow run."""
    if not event_path or not os.path.isfile(event_path):
        raise RuntimeError(
            f"GITHUB_EVENT_PATH not found or invalid: {event_path!r}. "
            "This script must run inside a GitHub Actions pull_request event."
        )
    with open(event_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_pr_number(event: dict) -> int:
    try:
        return event["pull_request"]["number"]
    except KeyError as exc:
        raise RuntimeError(
            "Event payload has no pull_request.number — "
            "was this triggered by a pull_request event?"
        ) from exc


def load_rules(rules_path: str) -> dict:
    if not os.path.isfile(rules_path):
        raise RuntimeError(f"Label rules file not found: {rules_path}")
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "rules" not in data:
        raise RuntimeError(f"Label rules file missing top-level 'rules' key: {rules_path}")
    return data["rules"]


def get_changed_files(repo: str, pr_number: int, token: str) -> list[str]:
    """Fetch all changed file paths for a PR, following pagination."""
    files = []
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"
        resp = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            params={"per_page": 100, "page": page},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"GitHub API error fetching PR files ({resp.status_code}): {resp.text}"
            )
        batch = resp.json()
        if not batch:
            break
        files.extend(item["filename"] for item in batch)
        if len(batch) < 100:
            break
        page += 1
    return files


def match_labels(changed_files: list[str], rules: dict) -> set[str]:
    matched = set()
    for label, patterns in rules.items():
        for path in changed_files:
            if any(fnmatch.fnmatch(path, pattern) for pattern in patterns):
                matched.add(label)
                break
    return matched


def apply_labels(repo: str, pr_number: int, token: str, labels: set[str]) -> None:
    if not labels:
        print("No labels matched — nothing to apply.")
        return
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/labels"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"labels": sorted(labels)},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"GitHub API error applying labels ({resp.status_code}): {resp.text}"
        )
    print(f"Applied labels: {sorted(labels)}")


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set — cannot authenticate to the GitHub API.")

    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is not set (expected 'owner/name').")

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event = load_event_payload(event_path)
    pr_number = get_pr_number(event)

    rules_path = os.environ.get("LABEL_RULES_PATH", "label-rules.yml")
    rules = load_rules(rules_path)

    changed_files = get_changed_files(repo, pr_number, token)
    print(f"Changed files ({len(changed_files)}): {changed_files}")

    labels = match_labels(changed_files, rules)
    apply_labels(repo, pr_number, token, labels)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)