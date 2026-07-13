# Import three standard-library modules in one line:
#   os read environment variables (like GITHUB_TOKEN) and interact with the OS
#   re regular expressions, used to find/replace text between markers
#   sys access to interpreter things (args, exit codes); imported for later use
import os, re, sys

# 'requests' is a third-party library for making HTTP calls
import requests

# xml.etree.ElementTree is Python's built-in tool for reading XML documents.
# 'as ET' gives it a shorter nickname so we can type ET instead of the long name.
import xml.etree.ElementTree as ET

# Atom feeds tag their elements with this namespace prefix. Storing it in one
# variable keeps the code below shorter and easier to read.
ATOM = "{http://www.w3.org/2005/Atom}"

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
    events = requests.get(url, headers=headers).json()

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

        # Build the cell text: the action plus a clickable link to the repo.
        cell = f"{action} [{repo}](https://github.com/{repo})"

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

    # Download the feed. .text gives us the raw XML as a plain string.
    xml = requests.get(BLOG_FEED_URL).text

    # Parse that XML string into a tree of elements we can search through.
    root = ET.fromstring(xml)

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

        # Add the cell text: the post title as a clickable link.
        cells.append(f"[{title}]({link})")

    # Return the list of cells (empty list if there were no posts).
    return cells

# A function that combines the GitHub activity and blog posts into ONE Markdown
# table with two side-by-side columns.
def build_activity_table():

    # Get both columns as lists of cell strings.
    github = fetch_github()
    blog = fetch_blog()

    # If a column is empty, give it a single friendly placeholder cell so the
    # table never has a blank heading with nothing under it.
    if not github:
        github = ["_Quiet week 😴_"]
    if not blog:
        blog = ["_No posts yet_"]

    # The two columns may have different lengths, so figure out the taller one.
    height = max(len(github), len(blog))

    # Start with the header row and the '---' separator row Markdown requires.
    # ':--' left-aligns each column.
    lines = [
        "| ✨ What I've been up to | ✍️ From my blog |",
        "| :-- | :-- |",
    ]

    # Walk down the rows one at a time, pairing the left and right cells.
    for i in range(height):
        # Use the cell if it exists at this position, otherwise leave it blank.
        left = github[i] if i < len(github) else ""
        right = blog[i] if i < len(blog) else ""
        lines.append(f"| {left} | {right} |")

    # Join every line with a newline into one complete table string.
    return "\n".join(lines)


def main():
    content = open(README, encoding="utf-8").read()
    content = replace_chunk(content, "FEED", build_activity_table())
    open(README, "w", encoding="utf-8").write(content)
 
if __name__ == "__main__":
    main()
