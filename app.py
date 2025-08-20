from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
import feedparser
from datetime import datetime


app = Flask(__name__)

# Global variables to store news
featured_articles = []
feed_articles = {}
all_videos = []
last_update = None

# List of news feeds
NEWS_FEEDS = {
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "The Kathmandu Post": "https://kathmandupost.com/rss"
}

def fetch_news():
    global featured_articles, feed_articles, all_videos, last_update
    featured_articles = []
    feed_articles = {}
    all_videos = []

    for source_name, url in NEWS_FEEDS.items():
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:5]:  # limit articles per source
            article = {
                "title": entry.title,
                "link": entry.link,
                "summary": getattr(entry, "summary", ""),
                "pub_date_str": getattr(entry, "published", ""),
                "source": source_name,
                "is_video": "video" in getattr(entry, "tags", [{}])[0].get("term", "").lower() if hasattr(entry, "tags") else False
            }
            articles.append(article)
            # Optional: pick first article as featured
            if len(featured_articles) < 3:
                featured_articles.append(article)
        feed_articles[source_name] = articles
        all_videos.extend([a for a in articles if a["is_video"]])
    
    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"News updated at {last_update}")

# Schedule automatic updates every 6 hours
scheduler = BackgroundScheduler()
scheduler.add_job(func=fetch_news, trigger="interval", hours=6)
scheduler.start()

# Initial fetch
fetch_news()


@app.route('/')
def index():
    total_articles = sum(len(v) for v in feed_articles.values())
    error = None if total_articles > 0 else "No articles available at the moment."
    
    last_fetch_time = datetime.now()  # put this BEFORE render_template

    return render_template(
        "index.html",
        featured_articles=featured_articles,
        feed_articles=feed_articles,
        all_videos=all_videos,
        total_articles=total_articles,
        error=error,
        last_update=last_update,       # comma added
        last_fetch_time=last_fetch_time
    )

if __name__ == "__main__":
    app.run(debug=True)
