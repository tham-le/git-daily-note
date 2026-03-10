# gitlab-daily-note

Auto-generate Obsidian daily notes from your GitLab MRs, issues, and todos.

## Setup

1. Install and authenticate [`glab`](https://gitlab.com/gitlab-org/cli)
2. Run `python gitlab_daily_note.py --init` to generate a `.daily-note.json` config
3. Edit the config to match your setup
4. Run `python gitlab_daily_note.py`

## Usage

```
python gitlab_daily_note.py              # Generate today's note
python gitlab_daily_note.py --team       # Include team MRs to review
python gitlab_daily_note.py --stdout     # Print to stdout instead of saving
python gitlab_daily_note.py --no-morning # Skip morning focus file
```
