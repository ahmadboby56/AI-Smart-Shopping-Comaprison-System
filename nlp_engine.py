import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
import re
import math

def get_sentiment_score(text):
    """Returns a sentiment polarity score between -1 and 1."""
    if not text: return 0
    return TextBlob(text).sentiment.polarity

def analyze_product_url(url, product_name, source, price, scraped_rating=None, scraped_reviews_count=None):
    """
    Fetches the product page, attempts to extract reviews/descriptions,
    runs NLP sentiment analysis via TextBlob, and generates a Trust Score.
    """
    if not url or url == '#' or source == 'Daraz (API)':
        return fallback_analysis(product_name, source, price, scraped_rating, scraped_reviews_count)

    try:
        # We use a very short timeout so the UI doesn't hang.
        # Stricter timeout (3s) and verify=False to avoid SSL delays
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0"
        }
        res = requests.get(url, headers=headers, timeout=3, verify=False)
        
        if res.status_code != 200:
            return fallback_analysis(product_name, source, price, scraped_rating, scraped_reviews_count)

        soup = BeautifulSoup(res.text, 'html.parser')
        
        possible_text = []
        # Target specific elements that likely contain product info/reviews
        review_elements = soup.find_all(['p', 'span', 'div'], class_=re.compile(r'review|comment|description|product-details|detail', re.I))
        for el in review_elements:
            text = el.get_text(separator=' ', strip=True)
            if 20 < len(text) < 1000: # Ignore very short or very long blocks
                possible_text.append(text)
                if len(possible_text) >= 15: break # Limit processing
                
        if not possible_text:
            return fallback_analysis(product_name, source, price, scraped_rating, scraped_reviews_count)

        combined_text = " ".join(possible_text)
        
        if len(combined_text) < 50:
            return fallback_analysis(product_name, source, price, scraped_rating, scraped_reviews_count)

        # --- Fast NLP Sentiment Analysis ---
        # Instead of blob.sentences (which is SLOW), analyze whole text or use simple splits
        blob = TextBlob(combined_text)
        avg_pol = blob.sentiment.polarity
        
        # Approximate sentence-level stats for the UI bars without using slow tokenizers
        # We use a simple split by common punctuation to simulate sentence analysis
        simulated_sentences = re.split(r'[.!?]+', combined_text[:2000])
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for s in simulated_sentences:
            if not s.strip(): continue
            s_pol = TextBlob(s).sentiment.polarity
            if s_pol > 0.1: positive_count += 1
            elif s_pol < -0.1: negative_count += 1
            else: neutral_count += 1
            
        total_s = positive_count + negative_count + neutral_count
        if total_s == 0: total_s = 1
        
        # 0.0 -> 70% trust
        trust_score = 70 + (avg_pol * 60)
        
        # Source reliability modifiers
        src_lower = source.lower()
        if 'daraz' in src_lower: trust_score += 5
        elif 'amazon' in src_lower: trust_score += 10
        elif 'ebay' in src_lower: trust_score += 5
        elif 'telemart' in src_lower: trust_score += 3
        
        # Add rating bonus if we have it
        if scraped_rating:
            try:
                trust_score += (float(scraped_rating) - 3.5) * 8
            except: pass
            
        trust_score = max(15, min(99, int(trust_score)))

        return {
            "success": True,
            "trust_score": trust_score,
            "positive_pct": int((positive_count / total_s) * 100),
            "negative_pct": int((negative_count / total_s) * 100),
            "neutral_pct": int((neutral_count / total_s) * 100),
            "analyzed_text_length": len(combined_text),
            "method": "Fast NLP Scraper"
        }

    except Exception as e:
        print(f"NLP Engine error on {url}: {e}")
        return fallback_analysis(product_name, source, price, scraped_rating, scraped_reviews_count)


def fallback_analysis(product_name, source, price, scraped_rating=None, scraped_reviews_count=None):
    """
    Fallback NLP analysis based on Title keywords, Source, and available Ratings.
    """
    blob = TextBlob(str(product_name))
    pol = blob.sentiment.polarity
    
    trust_score = 65 + (pol * 40)
    
    lower_name = str(product_name).lower()
    positive = 50
    negative = 10
    
    if 'copy' in lower_name or 'clone' in lower_name or 'fake' in lower_name or 'replica' in lower_name or 'master copy' in lower_name:
        trust_score -= 45 # Increased penalty from 30
        negative += 60
        positive -= 40
        
    if 'original' in lower_name or 'official' in lower_name or 'authentic' in lower_name:
        trust_score += 15
        positive += 20
        negative -= 5
        
    if source.lower() == 'daraz': trust_score += 5
    elif source.lower() == 'amazon': trust_score += 15
    elif source.lower() == 'ebay': trust_score += 5
    elif source.lower() == 'shophive': trust_score += 8
    
    # Factor in scraped ratings if available (Daraz/Amazon often have them)
    if scraped_rating:
        r = float(scraped_rating)
        # Rating is 0-5. If it's a 5 star, add 10 points. If 1 star, minus 20.
        trust_score += (r - 3.5) * 8
        positive += int((r - 3.0) * 10)
        negative -= int((r - 3.0) * 10)
        
    if scraped_reviews_count:
        count = int(scraped_reviews_count)
        trust_score += min(15, math.log10(count + 1) * 5)
    
    trust_score = max(5, min(99, int(trust_score)))
    positive = max(0, min(100, positive))
    negative = max(0, min(100 - positive, negative))
    neutral = max(0, 100 - positive - negative)

    return {
        "success": True,
        "trust_score": trust_score,
        "positive_pct": positive,
        "negative_pct": negative,
        "neutral_pct": neutral,
        "analyzed_text_length": len(str(product_name)),
        "method": "Title NLP & Heuristics"
    }

def analyze_reviews(reviews_list):
    """Legacy wrapper for simple lists of text"""
    if not reviews_list: return 0, "Neutral"
    scores = [get_sentiment_score(r) for r in reviews_list]
    avg_score = sum(scores) / len(scores)
    if avg_score > 0.2: label = "Highly Positive"
    elif avg_score > 0.05: label = "Positive"
    elif avg_score > -0.05: label = "Neutral"
    elif avg_score > -0.2: label = "Mixed"
    else: label = "Negative"
    return avg_score, label
