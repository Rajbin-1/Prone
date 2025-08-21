
from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
import feedparser
from datetime import datetime
import yt_dlp
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# Globals to be used in the template
all_articles = []
interesting_articles = []
nepal_articles = []
all_videos = []
last_update = None

# Trusted news sources (you can reorder or change)
NEWS_FEEDS = {
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "Kantipur": "https://ekantipur.com/feed/",
    "Kathmandu Post": "https://kathmandupost.com/feed/",
    "The Himalayan Times": "https://thehimalayantimes.com/feed/",
    "NYT Education": "https://rss.nytimes.com/services/xml/rss/nyt/Education.xml",
    "NYT Science": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml"
}

# How many articles to pull per source (NYT intentionally smaller)
SOURCE_LIMITS = {
    "NYT Education": 3,
    "NYT Science": 3,
    "Kantipur": 10,
    "Kathmandu Post": 10,
    "The Himalayan Times": 8,
    "Al Jazeera": 8,
    "BBC World": 8
}

# Keywords to mark an article "interesting"
KEYWORDS = [
    # Education & Learning
    "education", "learning", "school", "university", "research", "study", "teaching", "curriculum",
    
    # Science & Technology
    "science", "technology", "innovation", "experiment", "discovery", "physics", "chemistry", "biology",
    "mathematics", "space", "astronomy", "robotics", "AI", "artificial intelligence", "engineering",
    "computer", "software", "hardware", "programming", "coding", "quantum", "nanotechnology",
    
    # Environment & Nature
    "environment", "climate", "sustainability", "conservation", "wildlife", "nature", "ecosystem",
    "ocean", "forest", "pollution", "green energy", "renewable", "earthquake", "volcano", "disaster",
    
    # Health & Medicine
    "health", "medicine", "disease", "wellness", "nutrition", "vaccine", "epidemic", "pandemic",
    
    # Society & Culture
    "culture", "society", "history", "civilization", "innovation", "arts", "music", "festival", 
    "tradition", "heritage", "archaeology",
    
    # Economy & Business
    "economy", "business", "finance", "startup", "market", "trade", "industry", "investment",
    
    # Fun / Interesting / Curiosity
    "fun", "curiosity", "amazing", "fact", "invention", "cool", "trick", "hack", "record", "achievement"
]


# Nepal-related keywords (used for the Nepal section)
NEPAL_KEYWORDS = [
    "nepal", "kathmandu", "pokhara", "lumbini", "everest", "nepali", "bagmati",
    "himalaya", "mountain", "gorkha", "bhaktapur", "patan", "chitwan", "janakpur",
    "terai", "hills", "constitution", "parliament", "politics", "government",
    "election", "democracy", "protest", "strike", "economy", "trade", "tourism",
    "culture", "festival", "dashain", "tihar", "holi", "religion", "buddhism",
    "hinduism", "monsoon", "earthquake", "flood", "landslide", "disaster",
    "education", "health", "hospital", "research", "school", "university",
    "technology", "innovation", "transport", "road", "airports", "infrastructure",
    "environment", "pollution", "climate", "wildlife", "conservation"
]

# YouTube topics; the fetch will collect across these until it has max_videos
VIDEO_TOPICS = [
    "educational news",
    "fun science experiments",
    "technology explained",
    "history documentary",
    "space exploration",
    "physics explained",
    "chemistry experiments",
    "biology discoveries",
    "environmental science",
    "innovations in technology",
    "mathematics tricks",
    "engineering marvels",
    "scientific breakthroughs",
    "artificial intelligence explained",
    "robotics projects"
]

VIDEOS_MAX = 10  # how many videos you want overall

def normalize_text(s):
    return (s or "").lower()

def is_interesting(article):
    text = normalize_text(article.get("title", "") + " " + article.get("summary", ""))
    return any(kw.lower() in text for kw in KEYWORDS)

def is_nepal_related(article):
    text = normalize_text(article.get("title", "") + " " + article.get("summary", ""))
    # Consider either keywords or known Nepal sources
    if any(kw in text for kw in NEPAL_KEYWORDS):
        return True
    if article.get("source") in ["Kantipur", "Kathmandu Post", "The Himalayan Times"]:
        return True
    return False

def fetch_news():
    """
    Fetch RSS feeds, obey SOURCE_LIMITS, deduplicate, build:
      - all_articles
      - interesting_articles (filtered by KEYWORDS, with fallback)
      - nepal_articles (from all_articles)
    """
    global all_articles, interesting_articles, nepal_articles, last_update

    logging.info("Starting fetch_news()")
    all_articles = []
    interesting_articles = []
    nepal_articles = []

    seen_links = set()
    seen_titles = set()

    for source, url in NEWS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            logging.warning(f"Failed to parse feed {source}: {e}")
            continue

        entries = getattr(feed, "entries", []) or []
        limit = SOURCE_LIMITS.get(source, 5)

        added_from_source = 0
        for entry in entries:
            if added_from_source >= limit:
                break

            # Many feeds have link/title/summary/published - use safe getattr
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            pub_date = getattr(entry, "published", "") or getattr(entry, "updated", "")

            # Deduplicate by link or title
            key = link.strip() or title.strip()
            if not key:
                continue
            if key in seen_links or title.strip() in seen_titles:
                continue

            article = {
                "title": title.strip(),
                "link": link.strip(),
                "summary": summary.strip(),
                "pub_date_str": pub_date,
                "source": source,
            }

            all_articles.append(article)
            seen_links.add(key)
            seen_titles.add(title.strip())
            added_from_source += 1

            # If matches interesting keywords, add
            if is_interesting(article):
                interesting_articles.append(article)

        # Fallback: if this source ended up with zero "interesting" entries,
        # ensure at least the first available article from that source appears in interesting_articles
        # (so each source remains visible in the highlights)
        if not any(a["source"] == source for a in interesting_articles):
            # find first article from all_articles with this source
            for a in all_articles:
                if a["source"] == source:
                    interesting_articles.append(a)
                    break

    # Build nepal_articles from all_articles (not only interesting ones)
    nepal_articles = [a for a in all_articles if is_nepal_related(a)]

    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"fetch_news() completed: total all_articles={len(all_articles)}, interesting={len(interesting_articles)}, nepal={len(nepal_articles)}")

def fetch_videos():
    """
    Fetch YouTube videos using yt_dlp.
    Keep collecting across topics until we have VIDEOS_MAX videos,
    but stay bounded to avoid infinite loops.
    """
    global all_videos
    all_videos = []
    seen_video_ids = set()

    logging.info("Starting fetch_videos()")
    # We'll perform up to MAX_CYCLES over the topic list (increase if needed)
    MAX_CYCLES = 3
    cycle = 0

    while len(all_videos) < VIDEOS_MAX and cycle < MAX_CYCLES:
        cycle += 1
        for topic in VIDEO_TOPICS:
            if len(all_videos) >= VIDEOS_MAX:
                break

            # request a reasonable number of candidate results per topic
            # increase the search size slowly across cycles
            search_size = 20 * cycle  # 20, 40, 60 across cycles
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "force_json": True,
                "default_search": f"ytsearch{search_size}",
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(topic, download=False)
            except Exception as e:
                logging.warning(f"yt_dlp error for topic '{topic}': {e}")
                continue

            entries = result.get("entries") if isinstance(result, dict) else None
            if not entries:
                continue

            for video in entries:
                if len(all_videos) >= VIDEOS_MAX:
                    break
                # video may be a dict or object-like
                vid_id = video.get("id") or video.get("url") or video.get("webpage_url") or video.get("url")
                if not vid_id:
                    continue
                if vid_id in seen_video_ids:
                    continue

                title = video.get("title", "No title")
                uploader = video.get("uploader") or video.get("uploader_id") or "Unknown channel"
                upload_date = video.get("upload_date", "") or ""
                if upload_date and len(upload_date) >= 8:
                    pub_date_str = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                else:
                    pub_date_str = "Unknown date"

                link = video.get("url") or video.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}"

                video_info = {
                    "id": vid_id,
                    "title": title,
                    "link": link,
                    "channel": uploader,
                    "pub_date_str": pub_date_str,
                }

                all_videos.append(video_info)
                seen_video_ids.add(vid_id)

            # if after parsing entries we already have enough, break early
            if len(all_videos) >= VIDEOS_MAX:
                break

    logging.info(f"fetch_videos() completed: collected {len(all_videos)} videos")

def update_all():
    """
    Fetch both news and videos. Called on schedule.
    """
    try:
        fetch_news()
    except Exception as e:
        logging.exception(f"Error in fetch_news(): {e}")

    try:
        fetch_videos()
    except Exception as e:
        logging.exception(f"Error in fetch_videos(): {e}")

# Scheduler: update every 6 hours
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_all, trigger="interval", hours=6)
scheduler.start()

# Initial fetch at startup (non-blocking-ish; may take a few seconds)
update_all()

@app.route("/")
def index():
    error = None if interesting_articles else "No interesting articles right now."
    # Pass everything the template might want
    return render_template(
        "index.html",
        interesting_articles=interesting_articles,
        all_articles=all_articles,
        nepal_articles=nepal_articles,
        all_videos=all_videos,
        total_articles=len(interesting_articles),
        error=error,
        last_update=last_update,
        NEWS_FEEDS=NEWS_FEEDS,
        KEYWORDS=KEYWORDS,
        VIDEO_TOPICS=VIDEO_TOPICS
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # default 5000 locally
    app.run(host="0.0.0.0", port=port)



