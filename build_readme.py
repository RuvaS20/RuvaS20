# Import three standard-library modules in one line:
#   os read environment variables (like GITHUB_TOKEN) and interact with the OS
#   re regular expressions, used to find/replace text between markers
#   sys access to interpreter things (args, exit codes); imported for later use
import os, re, sys

# 'requests' is a third-party library for making HTTP calls
import requests

# 'base64' encodes the Spotify Client ID and Secret into the single scrambled
# string Spotify's login endpoint expects. It's built into Python.
import base64

# xml.etree.ElementTree is Python's built-in tool for reading XML documents.
# 'as ET' gives it a shorter nickname so we can type ET instead of the long name.
import xml.etree.ElementTree as ET

# parsedate_to_datetime turns an RSS-style date string (like
# "Tue, 07 Jul 2026 20:01:22 GMT") into a Python datetime we can reformat.
from email.utils import parsedate_to_datetime
# datetime lets us parse GitHub/Atom-style dates (like "2026-05-03T20:01:22Z").
from datetime import datetime

# Atom feeds tag their elements with this namespace prefix. Storing it in one
# variable keeps the code below shorter and easier to read.
ATOM = "{http://www.w3.org/2005/Atom}"

# A small helper that turns any of the date formats we might encounter into a
# tidy "DD/MM" string (e.g. "26/07"). Returns "" if there's no date.
def format_date(raw):
    # No date given? Return an empty string so nothing is shown.
    if not raw:
        return ""
    try:
        # RSS feeds use dates like "Tue, 07 Jul 2026 20:01:22 GMT".
        # parsedate_to_datetime understands that format.
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            # GitHub and Atom use dates like "2026-05-03T20:01:22Z", where the
            # first 10 characters ("2026-05-03") are the date. strptime reads them.
            dt = datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            # Some other unexpected format — give up and show nothing.
            return ""
    # strftime reformats the datetime as day/month, e.g. "26/07".
    return dt.strftime("%d/%m")

# My GitHub handle. It gets slotted into the API URL below.
GITHUB_USERNAME = "RuvaS20"

# The RSS feed URL for my blog. RSS is a machine-readable list of recent posts.
BLOG_FEED_URL   = "https://ruvawrites.pages.dev/rss.xml"

# The name of the file we will read from and write back to.
README = "README.md"

# A helper function that swaps out a section of text delimited by HTML comment
# markers. 'content' is the whole README text, 'marker' is the label (e.g. GITHUB),
# and 'chunk' is the new text to insert between the START and END markers.
def replace_chunk(content, marker, chunk):
    # find <!-- MARKER:START --> ... <!-- MARKER:END --> and rewrite the middle
    # re.compile builds a reusable regular-expression object.
    pattern = re.compile(
        # rf"..." is a raw f-string: 'f' lets us inject {marker}, 'r' stops Python
        # from treating backslashes specially. '.*?' means "match any characters,
        # as few as possible" — the text sitting between the two markers.
        rf"<!-- {marker}:START -->.*?<!-- {marker}:END -->",

        # re.DOTALL makes '.' also match newline characters, so the pattern can
        # span multiple lines (the block between markers is usually multi-line).
        re.DOTALL,
    )

    # Build the replacement text: the START marker, a newline, the new chunk,
    # another newline, then the END marker. This keeps the markers in place.
    replacement = f"<!-- {marker}:START -->\n{chunk}\n<!-- {marker}:END -->"

    # pattern.sub(replacement, content) returns a NEW string where every match of
    # the pattern in 'content' is replaced by 'replacement'.
    return pattern.sub(replacement, content)

# A function that fetches my recent public GitHub activity and returns it as a
# LIST of cell strings (one per activity), ready to become the left column of the
# combined table.
def fetch_github():

    # Build the GitHub API endpoint URL for this user's public events. The f-string
    # substitutes GITHUB_USERNAME into the {GITHUB_USERNAME} placeholder.
    url = f"https://api.github.com/users/{GITHUB_USERNAME}/events/public"

    # Read an optional GitHub token from the environment. os.environ.get returns
    # None if GITHUB_TOKEN is not set (instead of crashing). A token raises the
    # API rate limit and allows more requests.
    token = os.environ.get("GITHUB_TOKEN")

    # If a token exists, build an auth header dict; otherwise use an empty dict.
    headers = {}
    if token:
        headers = {"Authorization": f"token {token}"}

    # Send the HTTP GET request with those headers, then .json() parses the JSON
    # response body into Python objects (here, a list of event dictionaries).
    # If GitHub errors or returns a non-JSON body, return an empty list instead
    # of crashing so the rest of the README still builds.
    try:
        response = requests.get(url, headers=headers, timeout=15)
        # raise_for_status turns an HTTP error (like a 403 rate-limit) into an
        # exception, so a valid-JSON *error* body never reaches the loop below.
        response.raise_for_status()
        events = response.json()
    except (requests.RequestException, ValueError) as error:
        # Print why it failed (shows up in the Actions log) and carry on.
        print(f"GitHub fetch failed: {error}")
        return []

    # Prepare two containers: 'cells' collects the text for each cell, 'seen'
    # remembers cells we've already added so we don't repeat them.
    cells, seen = [], set()

    # Loop over each event returned by the API.
    for event in events:
        # Unpack two values at once: the repository name and the event type.
        repo, eventType = event["repo"]["name"], event["type"]

        # Depending on the event type, choose a short human-readable action word.
        # Each branch checks 'eventType' and, if it matches, sets 'action'.
        if eventType == "PushEvent":
            action = "⬆️ Pushed to"
        elif eventType == "WatchEvent":
            action = "⭐ Starred"
        elif eventType == "PullRequestEvent":
            action = "🔀 PR on"
        elif eventType == "CreateEvent":
            action = "✨ Created"
        else:
            # For any other event type, skip to the next loop iteration.
            continue

        # Grab the date this event happened. 'created_at' looks like
        # "2026-05-03T12:34:56Z", so format_date trims it to "2026-05-03".
        date = format_date(event["created_at"])

        # Build the cell text: the action, a clickable repo link, then the date.
        cell = f"{action} [{repo}](https://github.com/{repo}) — {date}"

        # If we've already recorded this exact cell, skip it (avoids duplicates).
        if cell in seen:
            continue

        # Remember this cell so we don't add it again later.
        seen.add(cell)
        # Add it to our list of cells.
        cells.append(cell)

        # Stop once we have 5 cells — that's enough for the README.
        if len(cells) >= 5:
            break

    # Return the list of cells (empty list if there was no activity).
    return cells

# A function that reads my blog's feed and returns the latest posts as a
# LIST of cell strings (one per post), ready to become the right column of the
# combined table.
def fetch_blog():

    # If no feed URL was set at the top of the file, there is nothing to fetch,
    # so return an empty list right away.
    if not BLOG_FEED_URL:
        return []

    # Download the feed and parse it into a tree we can search through. If the
    # feed is unreachable or returns something that isn't valid XML (e.g. an
    # error page during a deploy), return an empty list instead of crashing.
    try:
        response = requests.get(BLOG_FEED_URL, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except (requests.RequestException, ET.ParseError) as error:
        # Print why it failed (shows up in the Actions log) and carry on.
        print(f"Blog fetch failed: {error}")
        return []

    # Feeds come in two common formats: RSS uses <item> tags, Atom uses <entry>
    # tags. Try to find RSS <item> tags first; if there are none, fall back to
    # Atom <entry> tags. (The ATOM prefix marks Atom-namespaced tags.)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//" + ATOM + "entry")

    # This list will collect one cell string per post.
    cells = []

    # Loop over the first 5 posts only ([:5] "slices" the list to its first 5).
    for item in items[:5]:

        # Get the post's title. RSS uses a plain <title>; if that's missing,
        # try the Atom-namespaced <title> instead.
        title = item.findtext("title")
        if not title:
            title = item.findtext(ATOM + "title")

        # Get the post's link. In RSS the URL is the text inside <link>.
        link = item.findtext("link")

        # Atom feeds store the URL differently: in an 'href' attribute on the
        # <link> tag, not as text. So if we didn't get a link above, look there.
        if not link:
            linkElement = item.find(ATOM + "link")
            # If the <link> tag exists, read its 'href'; otherwise use "#".
            if linkElement is not None:
                link = linkElement.get("href")
            else:
                link = "#"

        # Get the post's publish date. RSS uses <pubDate>; Atom uses <published>
        # (or <updated> as a fallback). format_date tidies whichever we find.
        rawDate = item.findtext("pubDate")
        if not rawDate:
            rawDate = item.findtext(ATOM + "published")
        if not rawDate:
            rawDate = item.findtext(ATOM + "updated")
        date = format_date(rawDate)

        # Add the cell text: the post title as a clickable link, then the date.
        cells.append(f"[{title}]({link}) — {date}")

    # Return the list of cells (empty list if there were no posts).
    return cells

# A function that combines the GitHub activity and blog posts into ONE Markdown
# table with two side-by-side columns.
def build_activity_table():

    # Get all three columns as lists of cell strings.
    github = fetch_github()
    blog = fetch_blog()
    spotify = fetch_spotify()

    # If a column is empty, give it a single friendly placeholder cell so the
    # table never has a blank heading with nothing under it.
    if not github:
        github = ["_Quiet week 😴_"]
    if not blog:
        blog = ["_No posts yet_"]
    if not spotify:
        spotify = ["_Nothing on repeat_"]

    # The three columns may have different lengths, so figure out the tallest.
    height = max(len(github), len(blog), len(spotify))

    # Start with the header row and the '---' separator row Markdown requires.
    # ':--' left-aligns each column.
    lines = [
        "| ruvacodes | ruvawrites | ruvalistens |",
        "| :-- | :-- | :-- |",
    ]

    # Walk down the rows one at a time, pairing the cell from each column.
    for i in range(height):
        # Use the cell if it exists at this position, otherwise leave it blank.
        left = github[i] if i < len(github) else ""
        middle = blog[i] if i < len(blog) else ""
        right = spotify[i] if i < len(spotify) else ""
        lines.append(f"| {left} | {middle} | {right} |")

    # Join every line with a newline into one complete table string.
    return "\n".join(lines)

# A function that fetches my top Spotify tracks and returns them as a
# LIST of cell strings (one per track), ready to become a column of the table.
def fetch_spotify():

    # Read the three Spotify secrets from the environment (set as repo Secrets).
    cid     = os.environ.get("SPOTIFY_CLIENT_ID")
    secret  = os.environ.get("SPOTIFY_CLIENT_SECRET")
    refresh = os.environ.get("SPOTIFY_REFRESH_TOKEN")

    # If any secret is missing, Spotify isn't set up yet — return an empty list.
    if not (cid and secret and refresh):
        return []

    # Spotify wants the Client ID and Secret combined as "id:secret" and then
    # Base64-encoded. .encode() -> bytes, b64encode -> bytes, .decode() -> string.
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()

    # Trade the long-lived refresh token for a short-lived access token, and ask
    # Spotify for my top 5 tracks. Both calls talk to the network, so wrap them:
    # if a request fails or returns a non-JSON body (a transient Spotify hiccup),
    # catch it and return an empty list so the rest of the README still builds.
    # (JSONDecodeError is a kind of ValueError, so catching ValueError covers it.)
    try:
        # Trade the refresh token for a short-lived access token. timeout stops
        # the workflow hanging forever if Spotify never answers; raise_for_status
        # turns an HTTP error into a caught exception.
        tokenResp = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "refresh_token", "refresh_token": refresh},
            timeout=15,
        )
        tokenResp.raise_for_status()

        # .get avoids a crash if the login failed (e.g. an expired refresh token).
        accessToken = tokenResp.json().get("access_token")
        if not accessToken:
            return []

        # Ask Spotify for my top 5 tracks over roughly the last 4 weeks
        # ("short_term"). The access token proves it's me.
        tracksResp = requests.get(
            "https://api.spotify.com/v1/me/top/tracks",
            headers={"Authorization": f"Bearer {accessToken}"},
            params={"time_range": "short_term", "limit": 5},
            timeout=15,
        )
        tracksResp.raise_for_status()
        result = tracksResp.json()
    except (requests.RequestException, ValueError) as error:
        # Print why it failed (shows up in the Actions log) and carry on.
        print(f"Spotify fetch failed: {error}")
        return []

    # Build one cell per track: "Song by Artist" linked to its Spotify page.
    # Use .get with fallbacks so a track missing a field never crashes the loop.
    cells = []
    for track in result.get("items", []):
        name = track.get("name", "Unknown")
        artists = track.get("artists", [])
        artist = artists[0].get("name", "Unknown") if artists else "Unknown"
        url = track.get("external_urls", {}).get("spotify", "#")
        cells.append(f"[{name} by {artist}]({url})")

    # Return the list of cells (empty list if nothing came back).
    return cells


def main():
    content = open(README, encoding="utf-8").read()
    content = replace_chunk(content, "FEED", build_activity_table())
    open(README, "w", encoding="utf-8").write(content)
 
if __name__ == "__main__":
    main()
