# Authentication setup

This guide configures Google OAuth for the playlist importer. Complete it once
before running `create_playlist.py`.

The importer needs three values at runtime:

- `oauth.json`, containing your OAuth access and refresh tokens
- `YTMUSIC_CLIENT_ID`, containing the Google OAuth client ID that created the token
- `YTMUSIC_CLIENT_SECRET`, containing the matching OAuth client secret

The client ID and secret must be the same ones used when `oauth.json` was
generated. Modern versions of `ytmusicapi` require all three.

## 1. Install the project

Clone the repository and install its dependency in a virtual environment:

```bash
git clone https://github.com/kasperschnack/ytmusic-playlist-importer.git
cd ytmusic-playlist-importer
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Keep the virtual environment active for the remaining terminal steps. Confirm
that the authentication command is available:

```bash
ytmusicapi --version
ytmusicapi oauth --help
```

## 2. Create a Google Cloud project

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Use the project selector at the top of the page.
3. Select **New project**.
4. Give the project a recognizable name, such as
   `YouTube Music Playlist Importer`.
5. Select **Create**, then make sure the new project is selected.

Using a separate project for this personal tool makes its credentials and access
easy to identify and revoke later.

## 3. Enable the YouTube Data API

1. Open the
   [YouTube Data API v3 library page](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
   while the new project is selected.
2. Select **Enable**.
3. Wait until the API's overview page appears.

If Google reports `BadOAuthClient` or `invalid_client` later, first confirm that
this API is enabled in the same project as the OAuth client.

## 4. Configure the OAuth consent screen

Google may label this part of the console **Google Auth Platform**. The exact
navigation wording can change, but the configuration needs the following:

1. Open **Google Auth Platform** for the selected project.
2. Under **Branding**, enter an app name, support email, and developer contact
   email, then save.
3. Under **Audience**, select:
   - **External** for a normal personal Google account; or
   - **Internal** only when the tool will be used inside your Google Workspace
     organization and that option is available.
4. If the publishing status is **Testing**, add the Google account whose YouTube
   Music library will receive the playlist under **Test users**.
5. Under **Data Access**, add the YouTube scope
   `https://www.googleapis.com/auth/youtube` if the console asks you to configure
   scopes. This is the scope used to manage the account's YouTube data.

For personal use, the app can remain in Testing and does not normally need to be
submitted for public verification. Google currently limits External apps in
Testing to named test users, and their authorizations may expire after seven
days. If the token stops refreshing after that period, repeat step 6.

## 5. Create the correct OAuth client

1. Open **Google Auth Platform > Clients**.
2. Select **Create client**.
3. For **Application type**, select **TVs and Limited Input devices**.
4. Give it a name such as `ytmusic-playlist-importer`.
5. Select **Create**.
6. Copy the displayed **Client ID** and **Client secret** to a temporary secure
   location. You need both in the next two steps.

The application type matters. A Web or Desktop client will not work with the
device authorization flow used by `ytmusicapi`.

## 6. Generate `oauth.json`

From the repository directory, with the virtual environment active, run:

```bash
ytmusicapi oauth --file oauth.json
```

The command will:

1. Prompt for the Google YouTube Data API client ID. Paste the client ID from
   step 5.
2. Prompt for the client secret. Paste the matching client secret.
3. Print a Google device authorization URL and user code.
4. Open the URL in a browser, or copy it into a browser yourself.
5. Sign in with the account added as a test user in step 4.
6. Enter the displayed user code if Google does not fill it in automatically.
7. Review the requested YouTube permission and select **Allow**.
8. Return to the terminal and press Enter when the command asks you to finish.

After a successful flow, verify that the token file exists and is ignored by
Git:

```bash
test -s oauth.json && echo "oauth.json created"
git check-ignore -v oauth.json
chmod 600 oauth.json
```

`git check-ignore` should print the matching `.gitignore` rule. Do not manually
edit `oauth.json`; it contains a refresh token and is maintained by `ytmusicapi`.

## 7. Set the client environment variables

The importer deliberately does not store the client credentials in its source
code. Export the same values used in step 6 into the current shell:

```bash
export YTMUSIC_CLIENT_ID='paste-your-client-id-here'
export YTMUSIC_CLIENT_SECRET='paste-your-client-secret-here'
```

Values exported this way last only until that terminal session ends. For repeated
use, load them from a secure local secret manager or a shell configuration file
that only your user can read. Do not put real values in this repository.

If you keep `oauth.json` somewhere else, pass its path explicitly:

```bash
export YTMUSIC_OAUTH_FILE='/secure/path/oauth.json'
```

You can instead provide that path to each importer run with
`--oauth /secure/path/oauth.json`.

## 8. Run the importer

With the virtual environment active and the environment variables set:

```bash
python3 create_playlist.py \
  --songs example-songs.txt \
  --name "Reeform Herrehold" \
  --privacy PRIVATE
```

Successful authentication lets the searches begin. Review each candidate and
then answer `n` at the final confirmation if you only want to check searching
without creating a playlist.

## Troubleshooting

### `Authentication file not found`

Run step 6 from the repository directory, or specify the correct file with
`--oauth` or `YTMUSIC_OAUTH_FILE`.

### `Missing authentication environment variable(s)`

Repeat step 7 in the current terminal. Both variables are required.

### `invalid_client` or `BadOAuthClient`

Confirm that the YouTube Data API is enabled and that the OAuth client type is
**TVs and Limited Input devices**. Do not use a Web or Desktop client.

### `UnauthorizedOAuthClient` or token refresh fails

The client ID/secret do not match the client that created the token, the access
was revoked, or a Testing authorization expired. Preserve the old file and create
a new token using the current credentials:

```bash
mv oauth.json oauth.json.old
ytmusicapi oauth --file oauth.json
chmod 600 oauth.json
```

Delete `oauth.json.old` securely after the replacement works.

### `access_denied`

Make sure the account used in the browser is listed under **Audience > Test
users**, then repeat the device authorization flow and select **Allow**.

### `org_internal`

The project is restricted to a Google Workspace organization. Use an account
inside that organization, or change the app audience to External if your
organization permits it.

### Google shows an unverified-app warning

For an External app in Testing, confirm that you created the project yourself,
that the URL is a Google authorization page, and that you signed in as a listed
test user before proceeding. Do not proceed for a project or consent screen you
do not recognize.

## Protect and revoke access

- Never commit `oauth.json`, client secrets, `.env` files, access tokens, or
  refresh tokens.
- Do not paste credentials or the contents of `oauth.json` into issues, chat,
  logs, or screenshots.
- Restrict local token-file permissions with `chmod 600 oauth.json`.
- Before every commit, check staged files with `git diff --cached`.
- To revoke the tool, remove its access from your
  [Google Account connections](https://myaccount.google.com/connections) and
  delete the local token file.

## Official references

- [`ytmusicapi` OAuth setup](https://ytmusicapi.readthedocs.io/en/stable/setup/oauth.html)
- [`ytmusicapi` authenticated usage](https://ytmusicapi.readthedocs.io/en/stable/usage.html)
- [Google OAuth for TV and limited-input devices](https://developers.google.com/youtube/v3/guides/auth/devices)
- [Google OAuth app audience and test users](https://support.google.com/cloud/answer/15549945)
