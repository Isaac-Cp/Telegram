import logging
import praw
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.enums import ConversionStage

logger = logging.getLogger(__name__)

from app.models.external_lead import ExternalLead

TARGET_SUBREDDITS = [
    "IPTV", "IPTVReviews", "FireStick", "CordCutters", "TiviMate", "AndroidTV", "Streaming"
]

BUYER_SEARCH_QUERIES = [
    "best iptv", "iptv buffering help", "tivimate help", "iptv recommendation",
    "cheap iptv", "iptv problem", "firestick iptv help"
]

class RedditLeadDiscovery:
    def __init__(self):
        self.settings = get_settings()
        self.reddit = None
        if self.settings.reddit_client_id and self.settings.reddit_client_secret:
            self.reddit = praw.Reddit(
                client_id=self.settings.reddit_client_id,
                client_secret=self.settings.reddit_client_secret,
                user_agent=self.settings.reddit_user_agent
            )

    async def discover_reddit_leads(self):
        """
        Elite Module 9: Reddit Lead Discovery Engine.
        Scrape IPTV complaints and help requests from Reddit.
        """
        if not self.reddit:
            logger.warning("Reddit API credentials not set. Skipping Reddit discovery.")
            return

        logger.info("Starting SLIE Elite Reddit Lead Discovery...")
        
        # 1. Scan specific subreddits for new posts
        for subreddit_name in TARGET_SUBREDDITS:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                for submission in subreddit.new(limit=25):
                    # Check if post is from last 24 hours
                    if (datetime.utcnow().timestamp() - submission.created_utc) > 86400:
                        continue
                    
                    content = f"{submission.title} {submission.selftext}"
                    await self._process_reddit_lead(submission, content)
                        
            except Exception as e:
                logger.error(f"Error scanning subreddit '{subreddit_name}': {e}")

        # 2. Perform keyword searches across all of Reddit (User recommendation)
        for query in BUYER_SEARCH_QUERIES:
            try:
                logger.info(f"Searching Reddit for buyer intent: {query}")
                for submission in self.reddit.subreddit("all").search(query, sort="new", time_filter="day", limit=25):
                    content = f"{submission.title} {submission.selftext}"
                    await self._process_reddit_lead(submission, content)
            except Exception as e:
                logger.error(f"Error searching Reddit for query '{query}': {e}")

    async def _process_reddit_lead(self, submission, content):
        """
        Elite Module 9: Store discovered Reddit leads.
        EXTRACT: post_title, post_text, username, timestamp.
        STORE: external_leads (id, source, username, content, timestamp).
        """
        with SessionLocal() as db:
            # Check if Reddit post already exists
            existing = db.execute(
                select(ExternalLead).where(
                    and_(
                        ExternalLead.source == "reddit",
                        ExternalLead.username == (submission.author.name if submission.author else "anon"),
                        ExternalLead.timestamp == datetime.fromtimestamp(submission.created_utc)
                    )
                )
            ).scalar_one_or_none()
            
            if existing:
                return

            # Store in external_leads table as per Module 9 requirements
            # content field includes both post_title and post_text
            full_content = f"TITLE: {submission.title}\nTEXT: {submission.selftext}"
            
            new_lead = ExternalLead(
                source="reddit",
                username=submission.author.name if submission.author else "anon",
                content=full_content,
                timestamp=datetime.fromtimestamp(submission.created_utc)
            )
            db.add(new_lead)
            db.commit()
            logger.info(f"New SLIE Elite Reddit lead stored: {new_lead.username}")

reddit_lead_discovery = RedditLeadDiscovery()
