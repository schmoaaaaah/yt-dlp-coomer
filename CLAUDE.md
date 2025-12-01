# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

yt-dlp-coomer is a yt-dlp plugin that adds support for downloading media from coomer.su/coomer.st (a site archiving Fansly/OnlyFans content). It follows the yt-dlp plugin architecture.

## Development Commands

```bash
# Install dependencies (uses uv for package management)
uv sync

# Run yt-dlp with the plugin loaded (PYTHONPATH must include repo root)
PYTHONPATH=. python -m yt_dlp <url>

# Build package
python -m build

# Example: download a single post
PYTHONPATH=. python -m yt_dlp "https://coomer.st/onlyfans/user/USERNAME/post/POST_ID"

# Example: download all posts from a user
PYTHONPATH=. python -m yt_dlp "https://coomer.st/onlyfans/user/USERNAME"
```

## Architecture

### Plugin Structure

The plugin follows yt-dlp's plugin system:
- **`yt_dlp_plugins/extractor/coomer.py`**: Single extractor file containing `CoomerIE` class
- yt-dlp auto-discovers plugins from the `yt_dlp_plugins` directory when `PYTHONPATH` includes the repo root

### CoomerIE Extractor

The `CoomerIE` class inherits from `InfoExtractor` and handles:
- URL pattern: `https://coomer.(su|st)/{platform}/user/{user}[/post/{post}]`
- Supported platforms: fansly, onlyfans
- Two modes: single post extraction or full user playlist

Key methods:
- `_real_extract()`: Main entry point that dispatches to post or playlist extraction
- `_build_api_url()`: Constructs API endpoints at `https://coomer.st/api/v1/`
- `_build_media_info()`: Builds yt-dlp info dict for each attachment
- `_fetch_user_info()`: Gets user profile data

### API Structure

The coomer.st API returns:
- Single post: `{post: {...}, attachments: [...], previews: [...], videos: [...]}`
- User posts list: Array of post objects
- User profile: `{service, name, id, ...}`

Media URLs are constructed as: `{attachment.server}/data{attachment.path}`

## Environment

- Python 3.11+ required
- Uses mise (mise.toml) for Python version management
- Virtual environment in `.venv/`
- Dependency: yt-dlp >= 2025.03.31

## VS Code Debugging

Pre-configured launch configurations in `.vscode/launch.json` for:
- Single post download
- Multi-attachment post download
- Full user download

## Publishing

GitHub Actions workflow (`.github/workflows/python-publish.yml`) publishes to PyPI on release.
