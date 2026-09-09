import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import create_playlist


class ParseSongFileTests(unittest.TestCase):
    def write_temp(self, content: str) -> Path:
        temp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        with temp:
            temp.write(content)
        self.addCleanup(Path(temp.name).unlink)
        return Path(temp.name)

    def test_parses_songs_and_ignores_comments_and_blanks(self) -> None:
        path = self.write_temp(
            "# comment\n\nDepeche Mode - Stories of Old\nHvalfugl - Mørket Er Blåt\n"
        )
        songs = create_playlist.parse_song_file(path)
        self.assertEqual(
            [(song.artist, song.title) for song in songs],
            [
                ("Depeche Mode", "Stories of Old"),
                ("Hvalfugl", "Mørket Er Blåt"),
            ],
        )

    def test_preserves_dashes_inside_title(self) -> None:
        path = self.write_temp("Artist - A Song - Live\n")
        song = create_playlist.parse_song_file(path)[0]
        self.assertEqual(song.title, "A Song - Live")

    def test_reports_invalid_line_number(self) -> None:
        path = self.write_temp("Artist - Good\nnot valid\n")
        with self.assertRaisesRegex(create_playlist.UserError, "line 2"):
            create_playlist.parse_song_file(path)


class CliTests(unittest.TestCase):
    def test_required_and_default_arguments(self) -> None:
        args = create_playlist.parse_args(
            ["--songs", "songs.txt", "--name", "My Playlist"]
        )
        self.assertEqual(args.songs, Path("songs.txt"))
        self.assertEqual(args.name, "My Playlist")
        self.assertEqual(args.description, "")
        self.assertEqual(args.privacy, "PRIVATE")
        self.assertEqual(args.oauth, Path("oauth.json"))

    def test_privacy_is_case_insensitive(self) -> None:
        args = create_playlist.parse_args(
            ["--songs", "songs.txt", "--name", "List", "--privacy", "unlisted"]
        )
        self.assertEqual(args.privacy, "UNLISTED")


class MatchingTests(unittest.TestCase):
    def test_best_text_match_is_default(self) -> None:
        song = create_playlist.Song("Depeche Mode", "Stories of Old", 1)
        results = [
            {"title": "Stories (Live)", "artists": [{"name": "Other"}], "videoId": "a"},
            {"title": "Stories of Old", "artists": [{"name": "Depeche Mode"}], "videoId": "b"},
        ]
        self.assertEqual(create_playlist.likely_match_index(song, results), 1)
        with patch("builtins.print"):
            selected = create_playlist.choose_result(song, results, input_fn=lambda _: "")
        self.assertEqual(selected["videoId"], "b")

    def test_create_playlist_preserves_order(self) -> None:
        api = Mock()
        api.create_playlist.return_value = "PL123"
        song = create_playlist.Song("Artist", "Title", 1)
        matches = [
            create_playlist.Match(song, {"videoId": "first"}),
            create_playlist.Match(song, {"videoId": "second"}),
        ]
        playlist_id = create_playlist.create_playlist(
            api, "List", "Description", "PRIVATE", matches
        )
        self.assertEqual(playlist_id, "PL123")
        api.add_playlist_items.assert_called_once_with(
            "PL123", ["first", "second"], duplicates=True
        )


if __name__ == "__main__":
    unittest.main()
