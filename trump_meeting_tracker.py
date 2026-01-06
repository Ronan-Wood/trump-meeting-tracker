#!/usr/bin/env python3
"""
Trump Meetings Tracker - Enhanced Version
Searches for Trump meetings using NewsAPI + RSS feeds, identifies companies/industries, sends email reports
"""

import os
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re

# News APIs
from newsapi import NewsApiClient
import feedparser
from bs4 import BeautifulSoup

# Email
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


class TrumpMeetingsTracker:
    def __init__(self, db_path='trump_meetings.db', config_path='data_sources_config.json'):
        self.db_path = db_path
        self.config_path = config_path
        self.config = self.load_config()
        self.init_database()
        
        # Initialize NewsAPI client
        self.newsapi_key = os.environ.get('NEWS_API_KEY')
        if self.newsapi_key:
            self.newsapi = NewsApiClient(api_key=self.newsapi_key)
        else:
            self.newsapi = None
            print("⚠️ NEWS_API_KEY not set - NewsAPI searches will be skipped")
        
    def load_config(self):
        """Load configuration from JSON file"""
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create meetings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                location TEXT,
                meeting_type TEXT,
                source_url TEXT,
                source_publication TEXT,
                date_added TEXT NOT NULL,
                notes TEXT,
                UNIQUE(date, location, source_url)
            )
        ''')
        
        # Create attendees table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                name TEXT NOT NULL,
                title TEXT,
                company TEXT,
                primary_industry TEXT,
                secondary_industries TEXT,
                confidence_level TEXT,
                confidence_reasons TEXT,
                requires_review BOOLEAN,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def search_all_sources(self, days_back=7) -> List[Dict]:
        """
        Search all sources for Trump meetings
        Returns list of meeting dictionaries
        """
        all_meetings = []
        
        print(f"🔍 Searching for meetings from last {days_back} days...")
        print()
        
        # 1. Search NewsAPI
        if self.newsapi:
            newsapi_results = self.search_newsapi(days_back)
            print(f"  📰 NewsAPI: Found {len(newsapi_results)} articles")
            all_meetings.extend(newsapi_results)
        
        # 2. Search RSS Feeds
        rss_results = self.search_rss_feeds(days_back)
        print(f"  📡 RSS Feeds: Found {len(rss_results)} articles")
        all_meetings.extend(rss_results)
        
        print()
        print(f"✅ Total articles found: {len(all_meetings)}")
        
        # Parse articles for meeting information
        meetings = []
        for article in all_meetings:
            parsed_meetings = self.parse_article_for_meetings(article)
            for meeting in parsed_meetings:
                if not self.is_duplicate_meeting(meeting):
                    meetings.append(meeting)
        
        print(f"✅ Extracted {len(meetings)} unique meetings")
        
        return meetings
    
    def search_newsapi(self, days_back=7) -> List[Dict]:
        """Search NewsAPI for Trump meeting articles"""
        if not self.newsapi:
            return []
        
        articles = []
        from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Search queries optimized for meetings
        queries = [
            'Trump meets CEO',
            'Trump hosts business leaders',
            'Trump meeting executives',
            'Mar-a-Lago meeting',
            'White House CEO',
            'Business Roundtable Trump'
        ]
        
        for query in queries:
            try:
                response = self.newsapi.get_everything(
                    q=query,
                    from_param=from_date,
                    language='en',
                    sort_by='publishedAt',
                    page_size=20
                )
                
                if response['status'] == 'ok':
                    for article in response['articles']:
                        articles.append({
                            'title': article['title'],
                            'description': article.get('description', ''),
                            'url': article['url'],
                            'source': article['source']['name'],
                            'published_at': article['publishedAt'],
                            'content': article.get('content', '')
                        })
            except Exception as e:
                print(f"  ⚠️ Error searching NewsAPI for '{query}': {str(e)}")
        
        # Remove duplicates by URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article['url'] not in seen_urls:
                seen_urls.add(article['url'])
                unique_articles.append(article)
        
        return unique_articles
    
    def search_rss_feeds(self, days_back=7) -> List[Dict]:
        """Search RSS feeds for Trump meeting articles"""
        feeds = [
            'https://www.whitehouse.gov/feed/',
            'https://www.reuters.com/rssFeed/businessNews',
            'https://feeds.bloomberg.com/politics/news.rss',
            'https://www.cnbc.com/id/10001147/device/rss/rss.html',
            'https://www.politico.com/rss/politics08.xml',
            'https://www.axios.com/feeds/feed.rss'
        ]
        
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        keywords = ['trump', 'meeting', 'meets', 'hosted', 'ceo', 'executive', 'mar-a-lago', 'white house']
        
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries:
                    # Check if published recently
                    if hasattr(entry, 'published_parsed'):
                        pub_date = datetime(*entry.published_parsed[:6])
                        if pub_date < cutoff_date:
                            continue
                    
                    # Check if relevant keywords present
                    text = f"{entry.title} {entry.get('summary', '')}".lower()
                    if any(kw in text for kw in keywords):
                        articles.append({
                            'title': entry.title,
                            'description': entry.get('summary', ''),
                            'url': entry.link,
                            'source': feed.feed.get('title', 'RSS Feed'),
                            'published_at': entry.get('published', ''),
                            'content': entry.get('summary', '')
                        })
            except Exception as e:
                print(f"  ⚠️ Error parsing RSS feed {feed_url}: {str(e)}")
        
        return articles
    
    def parse_article_for_meetings(self, article: Dict) -> List[Dict]:
        """
        Parse article to extract meeting information
        Returns list of meeting dictionaries
        """
        meetings = []
        
        # Combine all text
        text = f"{article['title']} {article['description']} {article.get('content', '')}"
        
        # Check if it's actually about Trump meetings
        if not self.is_trump_meeting_article(text):
            return []
        
        # Extract date
        meeting_date = self.extract_meeting_date(text, article.get('published_at'))
        
        # Extract location
        location = self.extract_location(text)
        
        # Extract attendees (name, title, company)
        attendees = self.extract_attendees(text)
        
        if not attendees:
            return []
        
        # Create meeting object
        meeting = {
            'date': meeting_date,
            'location': location,
            'type': 'Business Meeting',
            'source_url': article['url'],
            'source_publication': article['source'],
            'notes': article['title'][:200],
            'attendees': []
        }
        
        # Process each attendee
        for att in attendees:
            # Classify company industry
            industry_info = self.classify_company_industry(att['company'])
            
            # Determine confidence level based on how company was found
            if att.get('found_in_article', True):
                # Company explicitly mentioned in article
                base_confidence = 'high'
            else:
                # Company found via dynamic lookup
                base_confidence = att.get('confidence', 'medium')
            
            # Adjust confidence based on industry classification
            if industry_info['confidence'] == 'low':
                # Unknown company reduces confidence
                final_confidence = 'low'
            else:
                final_confidence = base_confidence
            
            confidence_reasons = [f"Extracted from article: {article['source']}"]
            if not att.get('found_in_article', True):
                confidence_reasons.append("Company identified via dynamic web search")
            
            attendee_data = {
                'name': att['name'],
                'title': att['title'],
                'company': att['company'],
                'primary_industry': industry_info['primary_industry'],
                'secondary_industries': industry_info.get('secondary_industries', []),
                'confidence_level': final_confidence,
                'confidence_reasons': confidence_reasons,
                'requires_review': final_confidence == 'low'
            }
            
            meeting['attendees'].append(attendee_data)
        
        meetings.append(meeting)
        
        return meetings
    
    def is_trump_meeting_article(self, text: str) -> bool:
        """Check if article is about Trump meetings"""
        text_lower = text.lower()

        # Must mention Trump
        if 'trump' not in text_lower:
            return False

        # Must have meeting indicators WITH Trump
        meeting_patterns = [
            'trump meet', 'trump met', 'trump host', 'trump welcomed',
            'meeting with trump', 'met with trump', 'hosted by trump'
        ]
        if not any(pattern in text_lower for pattern in meeting_patterns):
            return False

        # Should mention business/executives (CEO, not just "president" which could be foreign leaders)
        business_words = ['ceo', 'chief executive', 'chairman', 'chief', 'business leader', 'executive', 'company']
        if not any(word in text_lower for word in business_words):
            return False

        # Exclude articles primarily about foreign leaders or politics
        political_keywords = [
            'ukraine', 'russia', 'venezuela', 'maduro', 'macron', 'zelensky', 'iran',
            'foreign leader', 'prime minister', 'nato', 'invasion', 'military'
        ]
        # Count political keywords
        political_count = sum(1 for kw in political_keywords if kw in text_lower)
        # If more than 2 political keywords, likely not a business meeting
        if political_count > 2:
            return False

        return True
    
    def extract_meeting_date(self, text: str, published_date: str = None) -> str:
        """Extract meeting date from text"""
        # Look for explicit dates
        date_patterns = [
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        # Fall back to published date
        if published_date:
            try:
                dt = datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                return dt.strftime('%B %d, %Y')
            except:
                pass
        
        # Default to today
        return datetime.now().strftime('%B %d, %Y')
    
    def extract_location(self, text: str) -> str:
        """Extract meeting location from text"""
        locations = {
            'Mar-a-Lago': ['mar-a-lago', 'mar a lago'],
            'White House, DC': ['white house'],
            'Trump Tower, NY': ['trump tower'],
            'Bedminster, NJ': ['bedminster']
        }
        
        text_lower = text.lower()
        for location, keywords in locations.items():
            if any(kw in text_lower for kw in keywords):
                return location
        
        return 'Location TBD'
    
    def extract_attendees(self, text: str) -> List[Dict]:
        """
        Extract attendee names, titles, and companies from text
        Returns list of {name, title, company}
        """
        attendees = []
        
        # Pattern 1: Name, Title of Company
        # Example: "Andy Jassy, CEO of Amazon"
        # Only accept CEO/Chairman/Chief titles, NOT "President" which is often foreign leaders
        pattern1 = r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),\s+(CEO|Chairman|Chief\s+Executive|Chief\s+Operating\s+Officer|CFO|COO|Chief\s+Financial\s+Officer)\s+(?:of\s+|at\s+)([A-Z][A-Za-z0-9\s&\.]+?)(?:\.|,|\s+(?:said|told|announced|met|joined|attended))'
        matches1 = re.findall(pattern1, text)

        for match in matches1:
            name, title, company = match
            company = company.strip()

            # Skip if company looks like a country or government entity
            if self.is_government_or_country(company):
                continue

            # Clean up company name
            company = re.sub(r'\s+Inc\.?|\s+Corp\.?|\s+LLC|\s+Ltd\.?', '', company)

            attendees.append({
                'name': name.strip(),
                'title': title.strip(),
                'company': company.strip(),
                'found_in_article': True
            })
        
        # Pattern 2: Company CEO Name
        # Example: "Amazon CEO Andy Jassy"
        # Only accept CEO/Chairman, NOT "President"
        pattern2 = r'([A-Z][A-Za-z0-9\s&\.]+?)\s+(CEO|Chairman|Chief\s+Executive)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        matches2 = re.findall(pattern2, text)

        for match in matches2:
            company, title, name = match
            company = company.strip()
            name_str = name.strip()

            # Skip Trump
            if 'Trump' in name_str:
                continue

            # Skip if company looks like a country or government entity
            if self.is_government_or_country(company):
                continue

            company = re.sub(r'\s+Inc\.?|\s+Corp\.?|\s+LLC|\s+Ltd\.?', '', company)

            # Avoid duplicates
            if not any(a['name'] == name_str for a in attendees):
                attendees.append({
                    'name': name_str,
                    'title': title.strip(),
                    'company': company.strip(),
                    'found_in_article': True
                })
        
        # Pattern 3: Just names with titles (no company) - DISABLED to save API calls
        # We focus on Pattern 1 and 2 which explicitly mention companies
        # This avoids making too many NewsAPI requests for names that aren't business leaders
        
        return attendees
    
    def is_government_or_country(self, company_name: str) -> bool:
        """Check if the 'company' is actually a government entity or country"""
        company_lower = company_name.lower().strip()

        # List of government/political keywords
        government_keywords = [
            'national assembly', 'government', 'ministry', 'parliament', 'congress',
            'senate', 'administration', 'department of', 'agency', 'commission',
            'federal', 'state department', 'white house', 'embassy', 'consulate',
            'republic', 'kingdom', 'federation', 'union', 'nation', 'country',
            'military', 'army', 'navy', 'defense', 'homeland security',
            'foreign affairs', 'state', 'democratic', 'republic of',
            'united states', 'european union', 'nato', 'un ', 'u.n.'
        ]

        # Countries and regions
        countries = [
            'venezuela', 'france', 'ukraine', 'russia', 'iran', 'mexico', 'colombia',
            'denmark', 'greenland', 'china', 'israel', 'syria', 'iraq', 'afghanistan'
        ]

        # Check if it matches any government keywords or countries
        for keyword in government_keywords + countries:
            if keyword in company_lower:
                return True

        # Check if it's too generic (single word entities that aren't companies)
        if len(company_lower.split()) == 1 and company_lower in ['danish', 'venezuelan', 'colombian', 'mexican', 'iranian', 'french']:
            return True

        return False

    def looks_like_person_name(self, name: str) -> bool:
        """Check if a string looks like an actual person's name"""
        parts = name.split()
        
        # Must be 2-3 words
        if len(parts) < 2 or len(parts) > 3:
            return False
        
        # Each part should be capitalized and reasonable length
        for part in parts:
            if not part[0].isupper():
                return False
            if len(part) < 2:  # No single letter names
                return False
            if len(part) > 15:  # Too long to be a name
                return False
        
        # Reject common non-name patterns
        non_name_words = {
            'president', 'ceo', 'chairman', 'chief', 'executive', 'officer',
            'company', 'corporation', 'inc', 'llc', 'ltd', 'business',
            'administration', 'department', 'agency', 'house', 'senate',
            'heritage', 'foundation', 'project', 'act', 'services', 'education',
            'disabilities', 'human', 'armed', 'vocational', 'aptitude', 'battery',
            'head', 'start', 'reproductive', 'freedom', 'health', 'resources',
            'secretary', 'robert', 'alive', 'abortion', 'survivors', 'medicaid',
            'homeland', 'security', 'border', 'protection', 'customs', 'enforcement',
            'national', 'weather', 'service', 'fair', 'labor', 'standards',
            'supreme', 'court', 'civil', 'war', 'white', 'donald', 'trump'
        }

        if any(part.lower() in non_name_words for part in parts):
            return False

        return True
    
    def appears_near_meeting_context(self, name: str, text: str) -> bool:
        """Check if name appears near meeting-related words"""
        # Find position of name
        pos = text.find(name)
        if pos == -1:
            return False

        # Check 100 chars before and after
        context = text[max(0, pos-100):min(len(text), pos+100)].lower()

        meeting_words = ['met', 'meeting', 'hosted', 'spoke', 'discussed', 'attended', 'joined']
        return any(word in context for word in meeting_words)

    def appears_near_business_context(self, name: str, text: str) -> bool:
        """Check if name appears near business-related words (CEO, company, etc.)"""
        # Find position of name
        pos = text.find(name)
        if pos == -1:
            return False

        # Check 100 chars before and after
        context = text[max(0, pos-100):min(len(text), pos+100)].lower()

        business_words = ['ceo', 'chief executive', 'president', 'chairman', 'company',
                         'corporation', 'executive', 'founder', 'co-founder', 'business']
        return any(word in context for word in business_words)
    
    def lookup_person_company_dynamic(self, person_name: str, article_context: str = "") -> Optional[Dict]:
        """
        Dynamically look up a person's company using web search
        Returns: {'company': str, 'title': str, 'confidence': str}
        """
        # Skip lookups if we don't have NewsAPI (rate limiting protection)
        if not self.newsapi:
            return None

        print(f"    🔍 Looking up: {person_name}")
        
        # First, check if we can infer from article context
        # Look for patterns like "person_name, who is/was CEO of Company"
        patterns = [
            f"{re.escape(person_name)}[^.]*?(?:CEO|President|Chairman|Chief Executive)[^.]*?(?:of|at)\\s+([A-Z][A-Za-z0-9]+(?:\\s+[A-Z][A-Za-z0-9]+)?)",
            f"([A-Z][A-Za-z0-9]+(?:\\s+[A-Z][A-Za-z0-9]+)?)\\s+(?:CEO|President|Chairman)\\s+{re.escape(person_name)}"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, article_context, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # Clean up
                company = re.sub(r'\s+Inc\.?|\s+Corp\.?|\s+LLC|\s+Ltd\.?', '', company)
                company = company.split(',')[0].split('.')[0].strip()
                
                # Validate it looks like a company name
                if len(company.split()) <= 3 and not any(word.lower() in ['the', 'and', 'for'] for word in company.split()):
                    print(f"    ✓ Found in context: {company}")
                    return {
                        'company': company,
                        'title': 'CEO',
                        'confidence': 'medium'
                    }
        
        # If NewsAPI is available, search for the person
        if self.newsapi:
            try:
                # Search for recent articles about this person + CEO
                search_results = self.newsapi.get_everything(
                    q=f'"{person_name}" CEO',
                    language='en',
                    sort_by='relevancy',
                    page_size=3
                )
                
                if search_results['status'] == 'ok' and search_results['articles']:
                    # Look through articles for company mentions
                    for article in search_results['articles']:
                        article_text = f"{article.get('title', '')} {article.get('description', '')} {article.get('content', '')}"
                        
                        # Look for clear company patterns
                        patterns = [
                            f"{re.escape(person_name)}[^.]*?(?:CEO|President|Chairman)[^.]*?(?:of|at)\\s+([A-Z][A-Za-z0-9]+(?:\\s+[A-Z][A-Za-z0-9]+)?)",
                            f"([A-Z][A-Za-z0-9]+(?:\\s+[A-Z][A-Za-z0-9]+)?)\\s+(?:CEO|President|Chairman)\\s+{re.escape(person_name)}"
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, article_text, re.IGNORECASE)
                            if match:
                                company = match.group(1).strip()
                                # Clean and validate
                                company = re.sub(r'\s+Inc\.?|\s+Corp\.?|\s+LLC|\s+Ltd\.?', '', company)
                                company = company.split(',')[0].split('.')[0].strip()
                                
                                # Check if it's a valid company name (not too long, not common words)
                                if (2 <= len(company) <= 30 and 
                                    len(company.split()) <= 3 and
                                    company[0].isupper()):
                                    
                                    print(f"    ✓ Found via web search: {company}")
                                    return {
                                        'company': company,
                                        'title': 'CEO',
                                        'confidence': 'medium'
                                    }
            except Exception as e:
                print(f"    ⚠️ Error in web search: {str(e)}")
        
        print(f"    ✗ Could not find company for {person_name}")
        return None
    
    def classify_company_industry(self, company_name: str) -> Dict:
        """
        Classify company into industry categories using config
        """
        company_lower = company_name.lower()
        
        # Check against known companies in config
        for industry_cat in self.config['industry_categories']:
            if 'related_companies' in industry_cat:
                for known_company in industry_cat['related_companies']:
                    # Fuzzy matching
                    if (known_company.lower() in company_lower or 
                        company_lower in known_company.lower() or
                        self.fuzzy_match(known_company.lower(), company_lower)):
                        return {
                            'primary_industry': industry_cat['name'],
                            'secondary_industries': [],
                            'confidence': 'high'
                        }
            
            # Check against keywords
            if 'keywords' in industry_cat:
                for keyword in industry_cat['keywords']:
                    if keyword.lower() in company_lower:
                        return {
                            'primary_industry': industry_cat['name'],
                            'secondary_industries': [],
                            'confidence': 'medium'
                        }
        
        # If no match found
        return {
            'primary_industry': 'Other',
            'secondary_industries': [],
            'confidence': 'low'
        }
    
    def fuzzy_match(self, str1: str, str2: str) -> bool:
        """Simple fuzzy string matching"""
        # Check if significant portion of one string is in the other
        if len(str1) < 4 or len(str2) < 4:
            return False
        
        # Check for common core (at least 4 chars)
        for i in range(len(str1) - 3):
            substr = str1[i:i+4]
            if substr in str2:
                return True
        
        return False
    
    def is_duplicate_meeting(self, meeting_data: Dict) -> bool:
        """Check if meeting already exists in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM meetings 
            WHERE date = ? AND location = ? AND source_url = ?
        ''', (meeting_data.get('date'), meeting_data.get('location'), meeting_data.get('source_url')))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def save_meeting(self, meeting_data: Dict) -> int:
        """Save meeting to database, return meeting_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO meetings (date, location, meeting_type, source_url, 
                                    source_publication, date_added, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                meeting_data.get('date'),
                meeting_data.get('location'),
                meeting_data.get('type'),
                meeting_data.get('source_url'),
                meeting_data.get('source_publication'),
                datetime.now().isoformat(),
                meeting_data.get('notes')
            ))
            
            meeting_id = cursor.lastrowid
            
            # Save attendees
            for attendee in meeting_data.get('attendees', []):
                cursor.execute('''
                    INSERT INTO attendees (meeting_id, name, title, company, 
                                         primary_industry, secondary_industries,
                                         confidence_level, confidence_reasons, requires_review)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    meeting_id,
                    attendee['name'],
                    attendee.get('title'),
                    attendee.get('company'),
                    attendee.get('primary_industry'),
                    json.dumps(attendee.get('secondary_industries', [])),
                    attendee.get('confidence_level'),
                    json.dumps(attendee.get('confidence_reasons', [])),
                    attendee.get('requires_review', False)
                ))
            
            conn.commit()
        except sqlite3.IntegrityError:
            # Duplicate - skip
            conn.close()
            return -1
        except Exception as e:
            print(f"  ⚠️ Error saving meeting: {str(e)}")
            conn.close()
            return -1
        
        conn.close()
        return meeting_id
    
    def get_new_meetings(self, since_date: str) -> List[Dict]:
        """Get meetings added since a specific date"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM meetings 
            WHERE date_added >= ?
            ORDER BY date DESC
        ''', (since_date,))
        
        meetings = []
        for meeting_row in cursor.fetchall():
            meeting = dict(meeting_row)
            
            # Get attendees for this meeting
            cursor.execute('''
                SELECT * FROM attendees WHERE meeting_id = ?
            ''', (meeting['id'],))
            
            attendees = []
            for att_row in cursor.fetchall():
                attendee = dict(att_row)
                try:
                    attendee['secondary_industries'] = json.loads(attendee['secondary_industries'])
                    attendee['confidence_reasons'] = json.loads(attendee['confidence_reasons'])
                except:
                    attendee['secondary_industries'] = []
                    attendee['confidence_reasons'] = []
                attendees.append(attendee)
            
            meeting['attendees'] = attendees
            meetings.append(meeting)
        
        conn.close()
        return meetings
    
    def generate_email_html(self, meetings: List[Dict]) -> str:
        """Generate HTML email from meetings data"""
        if not meetings:
            return """
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Trump Meetings Update</h2>
                <p>No new meetings found this period.</p>
            </body>
            </html>
            """
        
        # Categorize by priority
        high_priority = []
        medium_priority = []
        low_priority = []
        
        priority_industries = [
            '3PL', 'Asian 3PL', 'Agriculture', 'Automotive', 'Building Materials',
            'Data Center', 'E-Commerce', 'Asian E-Commerce', 'Food & Beverage',
            'Fulfillment & Packaging', 'Life Sciences', 'Manufacturing',
            'Powered Land', 'Retail', 'Wholesaler', 'Cold Storage'
        ]
        
        for meeting in meetings:
            meeting_priority = 'low'
            for attendee in meeting['attendees']:
                industry = attendee.get('primary_industry', 'Other')
                confidence = attendee.get('confidence_level', 'low')
                
                if industry in priority_industries:
                    if confidence == 'high':
                        meeting_priority = 'high'
                        break
                    elif confidence == 'medium' and meeting_priority != 'high':
                        meeting_priority = 'medium'
            
            if meeting_priority == 'high':
                high_priority.append(meeting)
            elif meeting_priority == 'medium':
                medium_priority.append(meeting)
            else:
                low_priority.append(meeting)
        
        # Build HTML
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #2c3e50; margin-top: 30px; }}
                .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .high-priority {{ background-color: #fee; border-left: 4px solid #c00; padding: 15px; margin: 15px 0; border-radius: 3px; }}
                .medium-priority {{ background-color: #ffc; border-left: 4px solid #f90; padding: 15px; margin: 15px 0; border-radius: 3px; }}
                .low-priority {{ background-color: #f5f5f5; border-left: 4px solid #999; padding: 15px; margin: 15px 0; border-radius: 3px; }}
                .meeting-date {{ font-weight: bold; color: #2c3e50; font-size: 1.1em; margin-bottom: 10px; }}
                .attendee {{ margin: 10px 0; padding: 10px; background-color: white; border-radius: 3px; }}
                .company {{ color: #0066cc; font-weight: bold; }}
                .industry {{ color: #27ae60; font-weight: 600; }}
                .confidence {{ font-size: 0.9em; font-style: italic; }}
                .confidence.high {{ color: #27ae60; }}
                .confidence.medium {{ color: #f39c12; }}
                .confidence.low {{ color: #e74c3c; }}
                .source {{ font-size: 0.85em; margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd; }}
                .source a {{ color: #3498db; text-decoration: none; }}
                .source a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>🇺🇸 Trump Meetings Update</h1>
            <div class="summary">
                <strong>📊 Report Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>
                <strong>📅 Period:</strong> Last 7 days<br>
                <strong>📢 New Meetings Found:</strong> {len(meetings)}<br>
                <strong>🔴 High Priority:</strong> {len(high_priority)} | 
                <strong>⚠️ Medium Priority:</strong> {len(medium_priority)} | 
                <strong>ℹ️ Other:</strong> {len(low_priority)}
            </div>
        """
        
        if high_priority:
            html += "<h2>🔴 HIGH PRIORITY - Your Industries</h2>"
            for meeting in high_priority:
                html += self.format_meeting_html(meeting, 'high-priority')
        
        if medium_priority:
            html += "<h2>⚠️ MEDIUM PRIORITY</h2>"
            for meeting in medium_priority:
                html += self.format_meeting_html(meeting, 'medium-priority')
        
        if low_priority:
            html += "<h2>ℹ️ OTHER MEETINGS</h2>"
            for meeting in low_priority:
                html += self.format_meeting_html(meeting, 'low-priority')
        
        html += """
            <div style="margin-top: 40px; padding-top: 20px; border-top: 2px solid #ddd; font-size: 0.9em; color: #7f8c8d;">
                <p><strong>About This Report:</strong></p>
                <ul>
                    <li>Automated tracking of Trump's meetings with business leaders</li>
                    <li>Sources: NewsAPI + RSS feeds from major news outlets</li>
                    <li>Industries classified based on company information</li>
                    <li>Confidence levels indicate certainty of company/industry match</li>
                    <li>⚠️ Review meetings with "low confidence" manually</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def format_meeting_html(self, meeting: Dict, css_class: str) -> str:
        """Format a single meeting as HTML"""
        html = f'<div class="{css_class}">'
        html += f'<div class="meeting-date">📅 {meeting["date"]} - {meeting.get("location", "Location TBD")}</div>'
        
        for attendee in meeting['attendees']:
            confidence_class = attendee.get('confidence_level', 'low')
            confidence_flag = ""
            if attendee.get('confidence_level') == 'low':
                confidence_flag = " ⚠️"
            elif attendee.get('confidence_level') == 'medium':
                confidence_flag = " ⚡"
            
            html += f'''
            <div class="attendee">
                <strong>👤 {attendee["name"]}</strong> - {attendee.get("title", "Executive")}{confidence_flag}<br>
                <span class="company">{attendee.get("company", "Unknown Company")}</span><br>
                <span class="industry">Industry: {attendee.get("primary_industry", "Unknown")}</span><br>
                <span class="confidence {confidence_class}">Confidence: {attendee.get("confidence_level", "unknown").upper()}</span>
            </div>
            '''
        
        if meeting.get('notes'):
            html += f'<div style="margin-top:10px; font-size:0.9em; color:#666;"><strong>Context:</strong> {meeting["notes"]}</div>'
        
        if meeting.get('source_url'):
            html += f'<div class="source">📰 Source: <a href="{meeting["source_url"]}">{meeting.get("source_publication", "View Article")}</a></div>'
        
        html += '</div>'
        return html
    
    def send_email(self, recipients: List[str], subject: str, html_content: str):
        """Send email using SendGrid"""
        sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
        sender_email = os.environ.get('SENDER_EMAIL', 'alerts@trumptracker.com')
        
        if not sendgrid_api_key:
            print("❌ ERROR: SENDGRID_API_KEY environment variable not set")
            print("   Set it in GitHub Secrets or your environment")
            return False
        
        try:
            sg = SendGridAPIClient(sendgrid_api_key)
            
            message = Mail(
                from_email=sender_email,
                to_emails=recipients,
                subject=subject,
                html_content=html_content
            )
            
            response = sg.send(message)
            
            if response.status_code == 202:
                print(f"✅ Email sent successfully to {len(recipients)} recipient(s)")
                return True
            else:
                print(f"⚠️ Email sent with status code: {response.status_code}")
                return True
                
        except Exception as e:
            print(f"❌ Error sending email: {str(e)}")
            return False
    
    def run(self, days_back=7):
        """Main execution function"""
        print("=" * 60)
        print("TRUMP MEETINGS TRACKER - ENHANCED VERSION")
        print("=" * 60)
        print()
        
        # Search for meetings
        meetings = self.search_all_sources(days_back)
        
        # Save new meetings
        saved_count = 0
        for meeting in meetings:
            meeting_id = self.save_meeting(meeting)
            if meeting_id > 0:
                saved_count += 1
        
        print()
        print(f"💾 Saved {saved_count} new meeting(s) to database")
        
        # Get meetings from last run
        since_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        recent_meetings = self.get_new_meetings(since_date)
        
        print(f"📊 Total meetings in database from last {days_back} days: {len(recent_meetings)}")
        print()
        
        # Generate and send email
        if recent_meetings:
            html_content = self.generate_email_html(recent_meetings)
            
            # Get recipients from environment variable
            recipients_str = os.environ.get('EMAIL_RECIPIENTS', '')
            recipients = [email.strip() for email in recipients_str.split(',') if email.strip()]
            
            if recipients:
                subject = f"Trump Meetings Update - {len(recent_meetings)} Meeting(s) ({datetime.now().strftime('%b %d, %Y')})"
                self.send_email(recipients, subject, html_content)
            else:
                print("⚠️ No email recipients configured. Set EMAIL_RECIPIENTS environment variable.")
                print("\n📧 Generated email saved for preview")
                
                # Save email to file for preview
                with open('email_preview.html', 'w') as f:
                    f.write(html_content)
                print("   Saved to: email_preview.html")
        else:
            print("ℹ️ No meetings found for the specified period")
        
        print()
        print("=" * 60)
        print("DONE")
        print("=" * 60)
    
    def add_test_meeting(self, name: str, title: str, company: str, date: str = None):
        """Helper method to add a test meeting manually"""
        if date is None:
            date = datetime.now().strftime('%B %d, %Y')
        
        meeting_data = {
            'date': date,
            'location': 'Mar-a-Lago, FL',
            'type': 'Business Meeting',
            'source_url': f'https://example.com/test-{name.replace(" ", "-").lower()}',
            'source_publication': 'Test Source',
            'notes': 'Test meeting entry',
            'attendees': [{
                'name': name,
                'title': title,
                'company': company,
                'confidence_level': 'high',
                'confidence_reasons': ['Test entry'],
                'requires_review': False
            }]
        }
        
        # Classify industry
        industry_info = self.classify_company_industry(company)
        meeting_data['attendees'][0].update(industry_info)
        
        meeting_id = self.save_meeting(meeting_data)
        if meeting_id > 0:
            print(f"✅ Added test meeting: {name} ({company}) - Meeting ID: {meeting_id}")
        return meeting_id


def main():
    """Entry point for script"""
    tracker = TrumpMeetingsTracker()
    
    # Check if we should add test data
    if os.environ.get('ADD_TEST_DATA') == 'true':
        print("📝 Adding test meetings...")
        tracker.add_test_meeting("Andy Jassy", "CEO", "Amazon", "January 3, 2026")
        tracker.add_test_meeting("Doug McMillon", "CEO", "Walmart", "January 4, 2026")
        tracker.add_test_meeting("Mary Barra", "CEO", "GM", "January 5, 2026")
        print()
    
    # Default: search last 7 days
    days_back = int(os.environ.get('DAYS_BACK', '7'))
    tracker.run(days_back=days_back)


if __name__ == "__main__":
    main()