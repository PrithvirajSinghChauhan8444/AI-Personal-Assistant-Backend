"""Local YouTube MCP Server offering transcript extraction, video metadata, and search."""

import json
import re
import sys
from typing import Any, Dict, List

from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

from base import SimpleMCPServer


def extract_video_id(url_or_id: str) -> str:
    """Extracts the 11-character YouTube video ID from various URL formats or raw ID."""
    url_or_id = url_or_id.strip()
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:shorts\/)([0-9A-Za-z_-]{11})",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    if len(url_or_id) == 11 and re.match(r"^[0-9A-Za-z_-]{11}$", url_or_id):
        return url_or_id
    return url_or_id


def format_seconds(seconds: float) -> str:
    """Formats seconds into MM:SS or HH:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def handle_get_transcript(args: Dict[str, Any]) -> str:
    """Fetches full transcript text from YouTube captions."""
    raw_target = args.get("url_or_id", "")
    video_id = extract_video_id(raw_target)
    languages = args.get("languages", ["en"])
    include_timestamps = args.get("include_timestamps", False)

    if not video_id:
        return "Error: A valid YouTube URL or video ID is required."

    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=languages)
        
        # Access transcript snippet items
        lines = []
        for snippet in transcript:
            text = snippet.text.replace("\n", " ").strip()
            if not text:
                continue
            if include_timestamps:
                ts = format_seconds(snippet.start)
                lines.append(f"[{ts}] {text}")
            else:
                lines.append(text)

        if include_timestamps:
            return "\n".join(lines)
        return " ".join(lines)

    except Exception as e:
        return f"Failed to retrieve transcript for video {video_id}: {e}"


def handle_get_video_info(args: Dict[str, Any]) -> str:
    """Fetches video metadata including title, channel, duration, and thumbnail."""
    raw_target = args.get("url_or_id", "")
    video_id = extract_video_id(raw_target)
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return f"Could not fetch information for {url}"

            title = info.get("title", "Unknown Title")
            channel = info.get("uploader", info.get("channel", "Unknown Channel"))
            duration_secs = info.get("duration", 0)
            duration_str = format_seconds(duration_secs) if duration_secs else "N/A"
            views = info.get("view_count", "N/A")
            description = (info.get("description") or "")[:500]

            res = (
                f"Title: {title}\n"
                f"Channel: {channel}\n"
                f"Duration: {duration_str}\n"
                f"Views: {views}\n"
                f"URL: {url}\n\n"
                f"Description Summary:\n{description}"
            )
            return res
    except Exception as e:
        return f"Error retrieving video info: {e}"


def handle_search_videos(args: Dict[str, Any]) -> str:
    """Searches YouTube for videos matching a query."""
    query = args.get("query", "").strip()
    max_results = min(int(args.get("max_results", 5)), 10)

    if not query:
        return "Error: query parameter cannot be empty."

    search_target = f"ytsearch{max_results}:{query}"
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(search_target, download=False)
            entries = res.get("entries", [])
            if not entries:
                return f"No YouTube videos found matching {query!r}."

            lines = [f"Found {len(entries)} video(s) for query {query!r}:\n"]
            for idx, entry in enumerate(entries, 1):
                title = entry.get("title", "Untitled")
                vid_id = entry.get("id", "")
                channel = entry.get("uploader", entry.get("channel", "Unknown"))
                url = f"https://www.youtube.com/watch?v={vid_id}"
                lines.append(f"{idx}. {title} by {channel}\n   URL: {url}")

            return "\n\n".join(lines)
    except Exception as e:
        return f"Error searching YouTube: {e}"


def main():
    server = SimpleMCPServer("youtube-mcp", "1.0.0")

    server.register_tool(
        name="get_transcript",
        description="Fetches the full spoken transcript of a YouTube video given its URL or ID.",
        input_schema={
            "type": "object",
            "properties": {
                "url_or_id": {"type": "string", "description": "YouTube video URL (e.g. https://www.youtube.com/watch?v=...) or 11-char ID"},
                "include_timestamps": {"type": "boolean", "description": "Whether to prepend timestamps (e.g. [02:15]) to transcript lines", "default": False},
                "languages": {"type": "array", "items": {"type": "string"}, "description": "List of language codes to try in preference order (default: ['en'])", "default": ["en"]},
            },
            "required": ["url_or_id"],
        },
        handler=handle_get_transcript,
    )

    server.register_tool(
        name="get_video_info",
        description="Retrieves metadata for a YouTube video: title, channel, duration, view count, and description.",
        input_schema={
            "type": "object",
            "properties": {
                "url_or_id": {"type": "string", "description": "YouTube video URL or 11-char ID"},
            },
            "required": ["url_or_id"],
        },
        handler=handle_get_video_info,
    )

    server.register_tool(
        name="search_videos",
        description="Searches YouTube for videos matching a query keyword and returns titles, channels, and URLs.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or topic"},
                "max_results": {"type": "integer", "description": "Maximum videos to return (1-10, default: 5)", "default": 5},
            },
            "required": ["query"],
        },
        handler=handle_search_videos,
    )

    server.run()


if __name__ == "__main__":
    main()
