from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
import feedparser
from datetime import datetime
import yt_dlp

app = Flask(__name__)

# Global variables
all_articles = []
interesting_articles = []
all_videos = []
last_update = None

# Trusted news sources
NEWS_FEEDS = {
    "NYT Education": "https://rss.nytimes.com/services/xml/rss/nyt/Education.xml",
    "NYT Science": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
    "Kantipur": "https://ekantipur.com/feed/",
    "Kathmandu Post": "https://kathmandupost.com/feed/",
    "The Himalayan Times": "https://thehimalayantimes.com/feed/",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml"
}

# Keywords to filter interesting/educational/fun content
KEYWORDS = [
    "education", "science", "learning", "technology", "fun",
    "innovation", "Nepal", "War", "health", "dead", "strict"
]

# YouTube search topics
VIDEO_TOPICS = [
    "educational news", "fun science", "technology explained",
    "history documentary", "Nepal current affairs"
]

def is_interesting(article):
    text = (article["title"] + " " + article.get("summary", "")).lower()
    return any(kw.lower() in text for kw in KEYWORDS)

def fetch_news():
    global all_articles, interesting_articles, last_update
    all_articles = []
    interesting_articles = []

    # Article limits per source (NYT less prominent)
    SOURCE_LIMITS = {
        "NYT Education": 3,
        "NYT Science": 3,
        "Kantipur": 6,
        "Kathmandu Post": 6,
        "The Himalayan Times": 5,
        "Al Jazeera": 6,
        "BBC World": 6
    }

    for source, url in NEWS_FEEDS.items():
        feed = feedparser.parse(url)
        print(f"Fetching from: {source}, found {len(feed.entries)} entries")

        limit = SOURCE_LIMITS.get(source, 5)
        added_any = False

        for entry in feed.entries[:limit]:
            article = {
                "title": entry.title,
                "link": entry.link,
                "summary": getattr(entry, "summary", ""),
                "pub_date_str": getattr(entry, "published", ""),
                "source": source,
            }
            all_articles.append(article)

            # Check if article is interesting
            if is_interesting(article):
                interesting_articles.append(article)
                added_any = True

        # Fallback: If no article matched, add the first one anyway
        if not added_any and feed.entries:
            interesting_articles.append(all_articles[-1])

    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"News updated at {last_update}")

def fetch_videos():
    global all_videos
    all_videos = []
    max_videos = 10

    for topic in VIDEO_TOPICS:
        if len(all_videos) >= max_videos:
            break  # Stop when we reach 10 videos

        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_json': True,
            'default_search': 'ytsearch15',  # Search up to 15 results per topic
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(topic, download=False)
                if 'entries' in result:
                    for video in result['entries']:
                        if len(all_videos) >= max_videos:
                            break
                        video_info = {
                            "title": video.get('title', 'No title'),
                            "link": video.get('url', '#'),
                            "channel": video.get('uploader', 'Unknown channel'),
                            "pub_date_str": (
                                f"{video.get('upload_date', '')[:4]}-"
                                f"{video.get('upload_date', '')[4:6]}-"
                                f"{video.get('upload_date', '')[6:8]}"
                                if video.get('upload_date') else 'Unknown date'
                            )
                        }
                        all_videos.append(video_info)
        except Exception as e:
            print(f"Error fetching videos for topic '{topic}': {e}")
            continue

def update_all():
    fetch_news()
    fetch_videos()

# Schedule automatic updates every 6 hours
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_all, trigger="interval", hours=6)
scheduler.start()

# Initial fetch
update_all()

@app.route('/')
def index():
    error = None if interesting_articles else "No interesting articles right now."
    return render_template(
        "index.html",
        interesting_articles=interesting_articles,
        total_articles=len(interesting_articles),
        all_videos=all_videos,
        error=error,
        last_update=last_update,
        NEWS_FEEDS=NEWS_FEEDS,
        KEYWORDS=KEYWORDS,
        VIDEO_TOPICS=VIDEO_TOPICS
    )

if __name__ == "__main__":
    app.run(debug=True)
