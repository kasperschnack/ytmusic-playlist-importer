# YouTube Music Playlist Importer

A small Python CLI that reads `Artist - Track` lines from a text file, lets you
interactively choose the right YouTube Music search result, and creates a playlist
with the selected tracks in the original order.

## Requirements and installation

- macOS or Linux
- Python 3.10 or newer
- A YouTube Music/Google account
- Google OAuth credentials for the YouTube Data API

```bash
git clone https://github.com/kasperschnack/ytmusic-playlist-importer.git
cd ytmusic-playlist-importer
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Authentication

Current versions of `ytmusicapi` require both an OAuth token file and the Google
OAuth client credentials that created it. This follows the
[official ytmusicapi OAuth documentation](https://ytmusicapi.readthedocs.io/en/stable/setup/oauth.html).

1. In Google Cloud Console, create or select a project.
2. Enable the **YouTube Data API v3**.
3. Configure the OAuth consent screen. If the app is in testing mode, add your
   Google account as a test user.
4. Create an **OAuth client ID** with application type
   **TVs and Limited Input devices**.
5. From this repository, create the token file. The command prompts for the
   client ID and secret, then starts Google's device authorization flow:

   ```bash
   ytmusicapi oauth --file oauth.json
   ```

6. Export the same client ID and secret before running the importer:

   ```bash
   export YTMUSIC_CLIENT_ID='your-client-id'
   export YTMUSIC_CLIENT_SECRET='your-client-secret'
   ```

The importer expects `oauth.json` in the current directory by default. Use
`--oauth /secure/path/oauth.json` or set `YTMUSIC_OAUTH_FILE` to use another
location.

Never commit or share `oauth.json`, the client secret, shell environment files,
or access/refresh tokens. This repository's `.gitignore` excludes common secret
files, but keep credentials outside the repository when practical. Consider
loading environment variables through your shell's secure local configuration;
do not paste secrets into issue reports or screenshots.

## Song file format

Put one song on each line, separated with ` - `:

```text
Depeche Mode - Stories of Old
Fontaines D.C. - Roman Holiday
Nick Cave & The Bad Seeds - Push the Sky Away
```

Blank lines and lines whose first non-whitespace character is `#` are ignored.
No CSV syntax or quoting is needed. See [`example-songs.txt`](example-songs.txt)
for a complete example.

## Usage

```bash
python3 create_playlist.py \
  --songs example-songs.txt \
  --name "Reeform Herrehold" \
  --privacy PRIVATE
```

Options:

```text
--songs PATH                 Input text file (required)
--name PLAYLIST_NAME         New playlist name (required)
--description TEXT           Playlist description (default: empty)
--privacy PRIVATE|PUBLIC|UNLISTED
                             Playlist visibility (default: PRIVATE)
--oauth PATH                 OAuth token file (default: oauth.json)
```

For each input line the tool searches YouTube Music with the `songs` filter and
shows up to five candidates, including title, artist, album, and duration when
available:

```text
Searching for:
Depeche Mode - Stories of Old

[1] Stories of Old - Depeche Mode - Some Great Reward - 3:13
[2] Stories of Old (Live) - Depeche Mode - Live in Berlin - 4:02

Select [1-2] (default 1), s=skip:
```

Press Enter for the suggested text match, enter a result number, or enter `s` to
skip the song. The first API result is not accepted automatically. After all
songs have been reviewed, the tool lists skipped songs and asks for confirmation
before creating anything.

Example completion:

```text
Matched: 14
Skipped: 1

Create playlist "Reeform Herrehold" with 14 tracks? [Y/n]

Created playlist:
https://music.youtube.com/playlist?list=...
```

## Local validation

The parser, CLI arguments, matching default, and playlist API isolation are tested
without calling YouTube Music:

```bash
python3 -m compileall -q create_playlist.py tests
python3 -m unittest discover -s tests -v
```

Live searching and playlist creation require your own authenticated account and
are intentionally not exercised by the test suite.
