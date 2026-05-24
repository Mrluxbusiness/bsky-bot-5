#!/usr/bin/env python3
"""
Single-Account Bluesky Movie Bot
- posted_movies.json repo-তেই থাকে (Gist নেই)
- দিনে ৩ বার post: morning / noon / evening
- mycinebd.com clickable link
- Movie title hashtag include করে
- App Password required
"""

import os, re, json, random, requests
from datetime import datetime, timezone
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
BSKY_HANDLE  = os.environ.get("BSKY_HANDLE")
BSKY_PASS    = os.environ.get("BSKY_APP_PASSWORD")

for name, val in [("TMDB_API_KEY", TMDB_API_KEY),
                   ("BSKY_HANDLE",  BSKY_HANDLE),
                   ("BSKY_APP_PASSWORD", BSKY_PASS)]:
    if not val:
        print(f"ERROR: {name} missing!"); exit(1)

TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_IMAGE  = "https://image.tmdb.org/t/p/w500"
BSKY_API    = "https://bsky.social/xrpc"
POSTED_FILE = Path("posted_movies.json")
MAX_HISTORY = 900
SITE_URL    = "https://mycinebd.com"
SITE_LABEL  = "mycinebd.com"   # exact string that appears in post text

# ── posted_movies.json ─────────────────────────────────────────────────────────
def load_posted_ids() -> set:
    if POSTED_FILE.exists():
        try:
            ids = set(json.loads(POSTED_FILE.read_text()).get("posted_ids", []))
            print(f"Loaded {len(ids)} posted IDs"); return ids
        except Exception as e:
            print(f"Read error: {e}")
    return set()

def save_posted_ids(posted_ids: set):
    id_list = list(posted_ids)[-MAX_HISTORY:]
    POSTED_FILE.write_text(json.dumps({"posted_ids": id_list}, indent=2))
    print(f"Saved {len(id_list)} IDs")

# ── TMDB ───────────────────────────────────────────────────────────────────────
TMDB_SOURCES = [
    ("trending/movie/week",  {"language": "en-US"}),
    ("trending/movie/day",   {"language": "en-US"}),
    ("movie/top_rated",      {"language": "en-US", "page": random.randint(1, 12)}),
    ("movie/now_playing",    {"language": "en-US"}),
    ("movie/popular",        {"language": "en-US", "page": random.randint(1, 8)}),
    ("discover/movie",       {"language": "en-US", "sort_by": "vote_average.desc",
                              "vote_count.gte": 500, "vote_average.gte": 7.5,
                              "page": random.randint(1, 15)}),
    ("discover/movie",       {"language": "en-US", "sort_by": "popularity.desc",
                              "vote_count.gte": 300, "page": random.randint(1, 10)}),
    ("movie/upcoming",       {"language": "en-US"}),
]

def fetch_one_movie(posted_ids: set) -> dict | None:
    sources = TMDB_SOURCES.copy()
    random.shuffle(sources)
    candidates = []
    for endpoint, params in sources:
        if len(candidates) >= 20: break
        p = {**params, "api_key": TMDB_API_KEY}
        try:
            r = requests.get(f"{TMDB_BASE}/{endpoint}", params=p, timeout=15)
            r.raise_for_status()
            for m in r.json().get("results", []):
                if m.get("poster_path") and m["id"] not in posted_ids:
                    if not any(c["id"] == m["id"] for c in candidates):
                        candidates.append(m)
        except Exception as e:
            print(f"TMDB error ({endpoint}): {e}")
    if not candidates: return None
    stub = random.choice(candidates)
    try:
        r = requests.get(f"{TMDB_BASE}/movie/{stub['id']}",
                         params={"api_key": TMDB_API_KEY, "append_to_response": "keywords"},
                         timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Detail fetch failed: {e}"); return None

# ── Time slot ──────────────────────────────────────────────────────────────────
def get_time_slot() -> str:
    hour = datetime.now(timezone.utc).hour
    if 5 <= hour < 12:    return "morning"
    elif 12 <= hour < 17: return "noon"
    else:                 return "evening"

# ── Templates ──────────────────────────────────────────────────────────────────
# {site} = "Watch Movies 🎬 mycinebd.com"  (mycinebd.com clickable হবে)
MORNING_TEMPLATES = [
    "Start your day with a great film 🎬\n\n{title} ({year}) — {hook}\n\nRated {rating}/10 | {genre}\n\n{tags}\n\n{site}",
    "Good morning film lovers! 🌅\n\nToday's pick: {title} ({year})\n\n{hook}\n\n{rating}/10 {genre} — seriously underrated.\n\n{tags}\n\n{site}",
    "Morning recommendation 🎥\n\n{title} ({year})\n{hook}\n\nA {genre} sitting at {rating}/10.\n\n{tags}\n\n{site}",
    "Waking up thinking about {title} ({year}).\n\n{hook}\n\nOne of the best {genre} films in recent memory. {rating}/10.\n\n{tags}\n\n{site}",
    "Your morning movie pick:\n\n🎬 {title} ({year})\n⭐ {rating}/10\n🎭 {genre}\n\n{hook}\n\n{tags}\n\n{site}",
]

NOON_TEMPLATES = [
    "Midday watchlist addition 📋\n\n{title} ({year}) — {hook}\n\nSolid {rating}/10 {genre} that more people need to see.\n\n{tags}\n\n{site}",
    "Not enough people talk about {title} ({year}).\n\n{hook}\n\nA {rating}/10 {genre} flying under the radar.\n\n{tags}\n\n{site}",
    "Add this to your list right now — {title} ({year}).\n\n{hook}\n\nRated {rating}/10. One of the better {genre} films out there.\n\n{tags}\n\n{site}",
    "Lunchtime watchlist update 🍿\n\n{title} ({year})\n{hook}\n\n{genre} | {rating}/10\n\n{tags}\n\n{site}",
    "Been recommending {title} to everyone lately.\n\n{hook}\n\nA {rating}/10 {genre} that absolutely delivers.\n\n{tags}\n\n{site}",
    "If you're in the mood for {genre}, {title} ({year}) should be your next watch.\n\n{hook}\n\n{rating}/10 — and that feels low.\n\n{tags}\n\n{site}",
]

EVENING_TEMPLATES = [
    "Perfect film for tonight 🌙\n\n{title} ({year}) — {hook}\n\n{genre} | {rating}/10\n\nTrust me on this one.\n\n{tags}\n\n{site}",
    "Evening pick 🎬\n\n{title} ({year}) holds up perfectly.\n\n{hook}\n\n{rating}/10 {genre}.\n\n{tags}\n\n{site}",
    "Can't stop thinking about {title}.\n\n{hook}\n\nThis {genre} film hit differently. {rating}/10.\n\n{tags}\n\n{site}",
    "Tonight's recommendation:\n\n🎬 {title} ({year})\n⭐ {rating}/10\n🎭 {genre}\n\n{hook}\n\nYou won't regret it.\n\n{tags}\n\n{site}",
    "The ending of {title} alone is worth the watch.\n\n{hook}\n\nA {genre} that earns its {rating}/10.\n\n{tags}\n\n{site}",
    "Wrapping up the day with {title} ({year}).\n\n{hook}\n\nA {rating}/10 {genre} that deserves more attention.\n\n{tags}\n\n{site}",
]

SLOT_TEMPLATES = {
    "morning": MORNING_TEMPLATES,
    "noon":    NOON_TEMPLATES,
    "evening": EVENING_TEMPLATES,
}

# ── Hashtags ───────────────────────────────────────────────────────────────────
GENRE_HASHTAGS = {
    "Action":          ["#Action", "#ActionMovies"],
    "Adventure":       ["#Adventure", "#MustWatch"],
    "Animation":       ["#Animation", "#AnimatedFilm"],
    "Comedy":          ["#Comedy", "#ComedyMovies"],
    "Crime":           ["#Crime", "#CrimeThriller"],
    "Drama":           ["#Drama", "#FilmDrama"],
    "Fantasy":         ["#Fantasy", "#FantasyFilm"],
    "Horror":          ["#Horror", "#HorrorMovies"],
    "Mystery":         ["#Mystery", "#MysteryFilm"],
    "Romance":         ["#Romance", "#RomanceFilm"],
    "Science Fiction": ["#SciFi", "#ScienceFiction"],
    "Thriller":        ["#Thriller", "#ThrillerMovies"],
    "War":             ["#WarFilm", "#War"],
    "Western":         ["#Western", "#WesternFilm"],
    "Documentary":     ["#Documentary", "#DocuFilm"],
    "Family":          ["#FamilyMovie", "#ForEveryone"],
}
GENERAL_HASHTAGS = [
    "#Movies", "#Film", "#Cinema", "#MustWatch", "#Filmlovers",
    "#NowWatching", "#FilmBuff", "#MovieNight", "#Cinephile",
    "#FilmReview", "#WatchList", "#MovieRecommendation",
]

def title_to_hashtag(title: str) -> str:
    """'The Dark Knight' → '#TheDarkKnight'"""
    # alphanumeric + space only, title-case words, join
    clean = re.sub(r"[^a-zA-Z0-9\s]", "", title)
    tag   = "".join(w.capitalize() for w in clean.split())
    return f"#{tag}" if tag else ""

def pick_hashtags(genres: list, title: str) -> str:
    tags = []

    # Movie title hashtag (first)
    movie_tag = title_to_hashtag(title)
    if movie_tag:
        tags.append(movie_tag)

    # Genre-specific tags
    for g in genres[:2]:
        if g in GENRE_HASHTAGS:
            tags.append(random.choice(GENRE_HASHTAGS[g]))

    # General tags
    tags += random.sample(GENERAL_HASHTAGS, 2)

    # Deduplicate, max 5 tags
    seen = list(dict.fromkeys(tags))
    return " ".join(seen[:5])

def make_hook(overview: str) -> str:
    if not overview:
        return "This one is hard to describe without spoiling it."
    sentences = [s.strip() for s in overview.split(". ") if s.strip()]
    hook = sentences[0]
    if len(sentences) > 1 and len(hook) < 60:
        hook += ". " + sentences[1]
    if not hook.endswith("."): hook += "."
    return (hook[:120] + "...") if len(hook) > 120 else hook

def generate_post(movie: dict, slot: str) -> str:
    title  = movie.get("title", "Unknown")
    year   = (movie.get("release_date") or "")[:4]
    rating = round(movie.get("vote_average", 0), 1)
    genres = [g["name"] for g in movie.get("genres", [])[:3]]
    genre  = genres[0] if genres else "Film"
    hook   = make_hook(movie.get("overview") or "")
    tags   = pick_hashtags(genres, title)
    site   = f"Watch Movies 🎬 {SITE_LABEL}"

    template = random.choice(SLOT_TEMPLATES.get(slot, NOON_TEMPLATES))
    post = template.format(title=title, year=year, rating=rating,
                           genre=genre, hook=hook, tags=tags, site=site)
    if len(post) > 300:
        short_hook = hook[:max(20, len(hook) - (len(post) - 295))] + "..."
        post = template.format(title=title, year=year, rating=rating,
                               genre=genre, hook=short_hook, tags=tags, site=site)
    return post[:300]

# ── Bluesky facets ─────────────────────────────────────────────────────────────
def byte_pos(text: str, char_idx: int) -> int:
    return len(text[:char_idx].encode("utf-8"))

def build_facets(text: str) -> list:
    facets = []

    # 1. Hashtag facets
    for m in re.finditer(r"#(\w+)", text):
        s = byte_pos(text, m.start())
        e = byte_pos(text, m.end())
        facets.append({
            "index":    {"byteStart": s, "byteEnd": e},
            "features": [{"$type": "app.bsky.richtext.facet#tag",
                          "tag":    m.group(1)}],
        })

    # 2. mycinebd.com — clickable link facet
    idx = text.find(SITE_LABEL)
    if idx != -1:
        s = byte_pos(text, idx)
        e = byte_pos(text, idx + len(SITE_LABEL))
        facets.append({
            "index":    {"byteStart": s, "byteEnd": e},
            "features": [{"$type": "app.bsky.richtext.facet#link",
                          "uri":   SITE_URL}],
        })

    return facets

# ── Bluesky API ────────────────────────────────────────────────────────────────
def bsky_login() -> dict:
    r = requests.post(f"{BSKY_API}/com.atproto.server.createSession",
                      json={"identifier": BSKY_HANDLE, "password": BSKY_PASS}, timeout=15)
    r.raise_for_status()
    return r.json()

def bsky_upload_blob(session: dict, image_bytes: bytes) -> dict:
    r = requests.post(f"{BSKY_API}/com.atproto.repo.uploadBlob",
                      headers={"Authorization": f"Bearer {session['accessJwt']}",
                               "Content-Type": "image/jpeg"},
                      data=image_bytes, timeout=30)
    r.raise_for_status()
    return r.json()["blob"]

def bsky_post(session: dict, text: str, blob=None, alt_text: str = "") -> str:
    record = {"$type":     "app.bsky.feed.post",
              "text":      text,
              "createdAt": datetime.now(timezone.utc).isoformat()}
    facets = build_facets(text)
    if facets:  record["facets"] = facets
    if blob:
        record["embed"] = {"$type":  "app.bsky.embed.images",
                           "images": [{"image": blob, "alt": alt_text}]}
    r = requests.post(f"{BSKY_API}/com.atproto.repo.createRecord",
                      headers={"Authorization": f"Bearer {session['accessJwt']}"},
                      json={"repo":       session["did"],
                            "collection": "app.bsky.feed.post",
                            "record":     record},
                      timeout=15)
    r.raise_for_status()
    return r.json()["uri"]

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    slot = get_time_slot()
    print(f"Slot    : {slot}")
    print(f"Account : {BSKY_HANDLE}")

    posted_ids = load_posted_ids()

    movie = fetch_one_movie(posted_ids)
    if not movie:
        print("No unseen movie found!"); exit(1)

    title     = movie.get("title", "Unknown")
    post_text = generate_post(movie, slot)

    print(f"\nMovie : {title} (ID: {movie['id']})")
    print(f"Post  ({len(post_text)} chars):\n{'─'*50}\n{post_text}\n{'─'*50}\n")

    # Show facets for debug
    facets = build_facets(post_text)
    print(f"Facets: {len(facets)} total")
    for f in facets:
        ftype = f["features"][0]["$type"].split("#")[-1]
        val   = f["features"][0].get("tag") or f["features"][0].get("uri", "")
        s, e  = f["index"]["byteStart"], f["index"]["byteEnd"]
        print(f"  [{ftype}] bytes {s}-{e} → {val}")

    session = bsky_login()
    print("\nLogin OK")

    blob = None
    if movie.get("poster_path"):
        try:
            img_r = requests.get(f"{TMDB_IMAGE}{movie['poster_path']}", timeout=20)
            if img_r.ok:
                blob = bsky_upload_blob(session, img_r.content)
                print("Poster uploaded.")
        except Exception as e:
            print(f"Poster skip: {e}")

    uri = bsky_post(session, post_text, blob=blob, alt_text=f"Movie poster for {title}")
    print(f"Posted  : {uri}")

    posted_ids.add(movie["id"])
    save_posted_ids(posted_ids)
    print("Done ✓")

if __name__ == "__main__":
    main()
