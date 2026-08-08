"""Admin dashboard data — repo activity, token usage, and agent/skill counts.

The scout-style dashboard in the admin UI needs three local facts:

- the latest commits of this repository (git log of the install tree),
- how many tokens each commit's work window consumed (from the Claude
  Code cost-tracker log at ~/.claude/metrics/costs.jsonl, filtered to
  this project's session transcripts), and
- how many agents and skills are installed for this machine.

Every source is optional: a pip-installed Claudey has no git repo, a
machine without the ECC cost tracker has no metrics file, and the USD/IDR
rate fetch may fail offline. Each lookup degrades to empty values instead
of raising, so the dashboard always renders.
"""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from .deepseek_billing import billing_payload

REPO_ROOT = Path(__file__).resolve().parents[3]
METRICS_PATH = Path(".claude/metrics/costs.jsonl")
MARKETPLACES_PATH = Path(".claude/plugins/marketplaces")

COMMIT_COUNT = 8
MAX_METRICS_BYTES = 5_000_000  # read only the recent tail of the cost log
RATE_URL = "https://open.er-api.com/v6/latest/USD"
RATE_TTL = timedelta(hours=6)
USD_IDR_FALLBACK = 18000.0  # seeded from a live fetch; used offline
MONTHLY_LIMIT_USD = 100.0

#: Cached exchange rate; refreshed at most every RATE_TTL.
_rate_cache: dict[str, datetime | float | None] = {
    "rate": None,
    "fetched_at": None,
}


def latest_commits(repo_root: Path, count: int = COMMIT_COUNT) -> list[dict[str, Any]]:
    """Return the newest commits as hash/short/subject/date_iso dicts.

    Returns an empty list when the directory is not a git repo, git is
    missing, or the log call fails for any other reason.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "-n",
                str(count),
                "--pretty=format:%H|%aI|%s",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return []
    if result.returncode != 0:
        return []
    commits: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        hash_, iso, subject = parts
        try:
            datetime.fromisoformat(iso)
        except ValueError:
            continue
        commits.append(
            {
                "hash": hash_,
                "short": hash_[:7],
                "subject": subject,
                "date_iso": iso,
            }
        )
    return commits


def cost_entries(home: Path, repo_root: Path) -> list[dict[str, Any]]:
    """Parse cost-tracker entries whose transcripts belong to this project.

    Claude Code names session transcripts
    ~/.claude/projects/<absolute-repo-path-with-dashes>/; matching on that
    prefix keeps other projects' usage out of the dashboard.
    """
    metrics = home / METRICS_PATH
    if not metrics.is_file():
        return []
    project_dir = str(repo_root).replace("/", "-")
    try:
        data = metrics.read_text(encoding="utf-8")
    except OSError:
        return []
    if len(data) > MAX_METRICS_BYTES:
        data = data[-MAX_METRICS_BYTES:]
    entries: list[dict[str, Any]] = []
    for line in data.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if project_dir not in entry.get("transcript_path", ""):
            continue
        timestamp = entry.get("timestamp")
        try:
            when = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except AttributeError, ValueError:
            continue
        tokens = entry.get("input_tokens", 0) + entry.get("output_tokens", 0)
        cost = float(entry.get("estimated_cost_usd", 0) or 0)
        entries.append({"timestamp": when, "tokens": tokens, "cost_usd": cost})
    return entries


def usd_to_idr() -> float:
    """USD→IDR rate, cached for RATE_TTL, falling back when offline."""
    now = datetime.now(UTC)
    rate = _rate_cache["rate"]
    fetched_at = _rate_cache["fetched_at"]
    if (
        isinstance(rate, float)
        and isinstance(fetched_at, datetime)
        and now - fetched_at < RATE_TTL
    ):
        return rate
    try:
        with httpx.Client(timeout=3) as client:
            response = client.get(RATE_URL)
            response.raise_for_status()
            rate = float(response.json()["rates"]["IDR"])
    except Exception:
        rate = USD_IDR_FALLBACK
    _rate_cache["rate"] = rate
    _rate_cache["fetched_at"] = now
    return rate


def agents_skills_counts(home: Path) -> dict[str, int]:
    """Count installed agents and skills, deduplicated by name.

    Agents live as <name>.md in ~/.claude/agents and each plugin
    marketplace's agents dir; skills as <name>/SKILL.md under ~/.claude/skills
    and the marketplaces. Marketplace mirrors for other tools (`.kiro`,
    `.cursor`, ...) share the same names, so the counts are unique names.
    """
    agents: set[str] = set()
    skills: set[str] = set()

    local_agents = home / ".claude/agents"
    if local_agents.is_dir():
        agents.update(path.stem for path in local_agents.glob("*.md"))
    local_skills = home / ".claude/skills"
    if local_skills.is_dir():
        skills.update(path.parent.name for path in local_skills.glob("*/SKILL.md"))

    marketplaces = home / MARKETPLACES_PATH
    if marketplaces.is_dir():
        for agents_dir in marketplaces.glob("*/agents"):
            if agents_dir.is_dir():
                agents.update(path.stem for path in agents_dir.glob("*.md"))
        for skills_dir in marketplaces.glob("*/skills"):
            if skills_dir.is_dir():
                skills.update(
                    path.parent.name for path in skills_dir.glob("*/SKILL.md")
                )

    return {"agents": len(agents), "skills": len(skills)}


def _commit_time(commit: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(commit["date_iso"])


def _usage_between(
    entries: list[dict[str, Any]], lower: datetime | None, upper: datetime
) -> tuple[int, float]:
    """Sum tokens/cost for entries in (lower, upper].

    `lower` is the next-older commit's time (work between two commits is
    attributed to the newer one); the newest commit's window runs to now.
    """
    tokens = 0
    cost = 0.0
    for entry in entries:
        when = entry["timestamp"]
        if (lower is None or when > lower) and when <= upper:
            tokens += entry["tokens"]
            cost += entry["cost_usd"]
    return tokens, cost


def monthly_spend_usd(home: Path | None = None) -> float:
    """Sum DeepSeek billing cost for days in the current calendar month."""
    home = home or Path.home()
    month_prefix = datetime.now(UTC).strftime("%Y-%m")
    days = billing_payload(home)["days"]
    return round(
        sum(day["cost_usd"] for day in days if day["date"].startswith(month_prefix)),
        6,
    )


def dashboard_payload(
    home: Path | None = None, repo_root: Path | None = None
) -> dict[str, Any]:
    """Assemble everything the scout dashboard renders."""
    home = home or Path.home()
    repo_root = repo_root or REPO_ROOT

    commits = latest_commits(repo_root)
    entries = cost_entries(home, repo_root)
    now = datetime.now(UTC)

    rows: list[dict[str, Any]] = []
    for index, commit in enumerate(commits):
        lower = _commit_time(commits[index + 1]) if index < len(commits) - 1 else None
        upper = now if index == 0 else _commit_time(commit)
        tokens, cost = _usage_between(entries, lower, upper)
        rows.append({**commit, "tokens": tokens, "cost_usd": round(cost, 6)})

    return {
        "commits": rows,
        "stats": agents_skills_counts(home),
        "usd_to_idr": usd_to_idr(),
        "monthly_spend_usd": monthly_spend_usd(home),
        "monthly_limit_usd": MONTHLY_LIMIT_USD,
    }
