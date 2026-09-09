#!/usr/bin/env python3
"""Interactively import a text file of songs into a YouTube Music playlist."""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Sequence


SEARCH_RESULT_LIMIT = 5


class UserError(Exception):
    """An expected error that should be shown without a traceback."""


@dataclass(frozen=True)
class Song:
    artist: str
    title: str
    line_number: int

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}"

    @property
    def search_query(self) -> str:
        return f"{self.artist} {self.title}"


@dataclass(frozen=True)
class Match:
    song: Song
    result: dict[str, Any]

    @property
    def video_id(self) -> str:
        return str(self.result["videoId"])


def parse_song_file(path: Path) -> list[Song]:
    """Read `Artist - Track` lines, ignoring blanks and comments."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise UserError(f"Songs file does not exist: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise UserError(f"Could not read songs file {path}: {exc}") from exc

    songs: list[Song] = []
    invalid: list[str] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        artist, separator, title = line.partition(" - ")
        if not separator or not artist.strip() or not title.strip():
            invalid.append(f"line {line_number}: {raw_line!r}")
            continue
        songs.append(Song(artist.strip(), title.strip(), line_number))

    if invalid:
        details = "\n  ".join(invalid)
        raise UserError(
            "Invalid song lines; expected 'Artist - Track':\n  " + details
        )
    if not songs:
        raise UserError(f"Songs file contains no songs: {path}")
    return songs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interactively create a YouTube Music playlist from a song list."
    )
    parser.add_argument("--songs", required=True, type=Path, metavar="PATH")
    parser.add_argument("--name", required=True, metavar="PLAYLIST_NAME")
    parser.add_argument("--description", default="", metavar="TEXT")
    parser.add_argument(
        "--privacy",
        type=str.upper,
        choices=("PRIVATE", "PUBLIC", "UNLISTED"),
        default="PRIVATE",
    )
    parser.add_argument(
        "--oauth",
        type=Path,
        default=Path(os.environ.get("YTMUSIC_OAUTH_FILE", "oauth.json")),
        metavar="PATH",
        help="OAuth token file (default: oauth.json or YTMUSIC_OAUTH_FILE)",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def authenticate(oauth_path: Path) -> Any:
    """Create an authenticated YTMusic client from ignored local credentials."""
    if not oauth_path.is_file():
        raise UserError(
            f"Authentication file not found: {oauth_path}\n"
            "Create it with `ytmusicapi oauth --file oauth.json`; see README.md."
        )

    client_id = os.environ.get("YTMUSIC_CLIENT_ID")
    client_secret = os.environ.get("YTMUSIC_CLIENT_SECRET")
    missing = [
        name
        for name, value in (
            ("YTMUSIC_CLIENT_ID", client_id),
            ("YTMUSIC_CLIENT_SECRET", client_secret),
        )
        if not value
    ]
    if missing:
        raise UserError(
            "Missing authentication environment variable(s): " + ", ".join(missing)
        )

    try:
        from ytmusicapi import OAuthCredentials, YTMusic
    except ImportError as exc:
        raise UserError(
            "ytmusicapi is not installed. Run `python3 -m pip install -r requirements.txt`."
        ) from exc

    try:
        credentials = OAuthCredentials(
            client_id=client_id, client_secret=client_secret
        )
        return YTMusic(str(oauth_path), oauth_credentials=credentials)
    except Exception as exc:
        raise UserError(f"YouTube Music authentication failed: {exc}") from exc


def search_song(ytmusic: Any, song: Song, limit: int = SEARCH_RESULT_LIMIT) -> list[dict[str, Any]]:
    """Return usable song search results for one input song."""
    results = ytmusic.search(song.search_query, filter="songs", limit=limit)
    return [result for result in results if result.get("videoId")][:limit]


def _names(value: Any) -> str:
    if isinstance(value, list):
        names = [
            str(item.get("name", "")) if isinstance(item, dict) else str(item)
            for item in value
        ]
        return ", ".join(name for name in names if name)
    return str(value or "")


def format_result(result: dict[str, Any]) -> str:
    title = str(result.get("title") or "Unknown title")
    artists = _names(result.get("artists")) or "Unknown artist"
    album_value = result.get("album")
    if isinstance(album_value, dict):
        album = str(album_value.get("name") or "")
    else:
        album = str(album_value or "")
    duration = str(result.get("duration") or "")
    extras = " - ".join(item for item in (album, duration) if item)
    return f"{title} - {artists}" + (f" - {extras}" if extras else "")


def _normalized(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).casefold()
    return " ".join(re.findall(r"[\w]+", ascii_value))


def likely_match_index(song: Song, results: Sequence[dict[str, Any]]) -> int:
    """Choose a practical default using title and artist text similarity."""
    target_title = _normalized(song.title)
    target_artist = _normalized(song.artist)

    def score(result: dict[str, Any]) -> float:
        title = _normalized(str(result.get("title") or ""))
        artists = _normalized(_names(result.get("artists")))
        title_score = SequenceMatcher(None, target_title, title).ratio()
        artist_score = SequenceMatcher(None, target_artist, artists).ratio()
        exact_bonus = 0.15 if target_title == title else 0.0
        return title_score * 0.65 + artist_score * 0.35 + exact_bonus

    return max(range(len(results)), key=lambda index: score(results[index]))


def choose_result(
    song: Song,
    results: Sequence[dict[str, Any]],
    input_fn: Callable[[str], str] = input,
) -> dict[str, Any] | None:
    """Show candidates and ask the user to select one or skip."""
    print(f"\nSearching for:\n{song.display_name}\n")
    for index, result in enumerate(results, start=1):
        print(f"[{index}] {format_result(result)}")

    default = likely_match_index(song, results) + 1
    while True:
        answer = input_fn(
            f"\nSelect [1-{len(results)}] (default {default}), s=skip: "
        ).strip().lower()
        if not answer:
            return results[default - 1]
        if answer == "s":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(results):
            return results[int(answer) - 1]
        print(f"Please enter 1-{len(results)}, press Enter, or enter s.")


def confirm(prompt: str, input_fn: Callable[[str], str] = input) -> bool:
    while True:
        answer = input_fn(f"{prompt} [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please enter y or n.")


def create_playlist(
    ytmusic: Any,
    name: str,
    description: str,
    privacy: str,
    matches: Sequence[Match],
) -> str:
    """Create an empty playlist, then add matched tracks in input order."""
    try:
        playlist_id = ytmusic.create_playlist(name, description, privacy)
    except Exception as exc:
        raise UserError(f"Playlist creation failed: {exc}") from exc

    if not isinstance(playlist_id, str) or not playlist_id:
        raise UserError(f"Playlist creation failed: unexpected response {playlist_id!r}")

    try:
        ytmusic.add_playlist_items(
            playlist_id,
            [match.video_id for match in matches],
            duplicates=True,
        )
    except Exception as exc:
        url = f"https://music.youtube.com/playlist?list={playlist_id}"
        raise UserError(
            f"Playlist was created, but adding tracks failed: {exc}\n"
            f"The empty or partial playlist may be available at: {url}"
        ) from exc
    return playlist_id


def run(args: argparse.Namespace) -> int:
    songs = parse_song_file(args.songs)
    ytmusic = authenticate(args.oauth)
    matches: list[Match] = []
    skipped: list[tuple[Song, str]] = []

    print(f"Loaded {len(songs)} song(s) from {args.songs}.")
    for song in songs:
        try:
            results = search_song(ytmusic, song)
        except Exception as exc:
            raise UserError(
                f"YouTube Music search failed for {song.display_name}: {exc}"
            ) from exc

        if not results:
            print(f"\nNo song results found for: {song.display_name}")
            skipped.append((song, "no results"))
            continue
        selected = choose_result(song, results)
        if selected is None:
            skipped.append((song, "skipped"))
        else:
            matches.append(Match(song, selected))

    print(f"\nMatched: {len(matches)}")
    print(f"Skipped: {len(skipped)}")
    if skipped:
        print("\nSkipped or unresolved:")
        for song, reason in skipped:
            print(f"- {song.display_name} ({reason})")

    if not matches:
        raise UserError("No tracks were matched; no playlist was created.")
    prompt = f'Create playlist "{args.name}" with {len(matches)} tracks?'
    if not confirm(prompt):
        print("Cancelled; no playlist was created.")
        return 0

    playlist_id = create_playlist(
        ytmusic, args.name, args.description, args.privacy, matches
    )
    print(
        "\nCreated playlist:\n"
        f"https://music.youtube.com/playlist?list={playlist_id}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except UserError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled; no further changes were made.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
