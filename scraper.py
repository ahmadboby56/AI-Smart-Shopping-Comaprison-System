from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
import re
import requests
import concurrent.futures
import threading
from apify_client import ApifyClient
import undetected_chromedriver as uc
import cloudscraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import os
import logging
import json
from urllib.parse import urljoin

# Setup Logging
SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRAPER_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, 'scraper.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Global threading lock to prevent multiple concurrent undetected-chromedriver instances from crashing the system
selenium_lock = threading.Lock()

# User Agent list for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1"
]

def get_random_ua():
    return random.choice(USER_AGENTS)

# Global Semaphore for regular Selenium instances - increased to 4 for better parallelism
selenium_semaphore = threading.Semaphore(4)


# Lock specifically for Undetected Chromedriver initialization to prevent WinError 6
uc_init_lock = threading.RLock()

# Global Session for Requests (Persistent TCP/SSL handshake)
_scraper_session = None
session_lock = threading.Lock()

def get_session():
    """Get or create a global cloudscraper session for persistent connections."""
    global _scraper_session
    if _scraper_session is None:
        with session_lock:
            if _scraper_session is None:
                _scraper_session = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True
                    }
                )
                # Increase connection pool sizes to prevent bottleneck
                adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
                _scraper_session.mount('http://', adapter)
                _scraper_session.mount('https://', adapter)
    return _scraper_session

# ==============================
# DRIVER SETUP (Selenium fallback)
# ==============================
def get_driver(strategy='eager', use_uc=False, images=True):
    options = Options()
    import os
    proxy = os.environ.get('SCRAPER_PROXY') or os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY') or os.environ.get('http_proxy') or os.environ.get('https_proxy')
    if proxy:
        options.add_argument(f"--proxy-server={proxy}")
        logging.info(f"Using proxy for Selenium driver: {proxy}")
        
    if not use_uc:
        options.add_argument("--headless=new")
    
    # Fundamental Speed Optimizations
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Minimalistic UI for faster rendering
    options.add_argument("--window-size=1920,1080")
    if not images:
        options.add_argument("--blink-settings=imagesEnabled=false")
    
    # Advanced Anti-Detection
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Note: experimental options are removed as they conflict with undetected_chromedriver
    options.add_argument(f"user-agent={get_random_ua()}")
    
    if use_uc:
        with uc_init_lock:
            try:
                driver = uc.Chrome(options=options, headless=True, version_main=151)
                driver.set_page_load_timeout(45)
                return driver
            except OSError as e:
                if "183" in str(e):
                    # Nuclear option: wipe entire cache and retry once
                    import shutil
                    cache_dir = os.path.join(os.environ.get('APPDATA', ''), 'undetected_chromedriver')
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    logging.warning("Cleared UC cache due to WinError 183, retrying...")
                    try:
                        driver = uc.Chrome(options=options, headless=True, version_main=151)
                        driver.set_page_load_timeout(45)
                        return driver
                    except Exception as e2:
                        logging.error(f"UC Driver retry failed: {e2}")
                        return None
                logging.error(f"UC Driver OS Error: {e}")
                return None
            except Exception as e:
                logging.error(f"UC Driver Error: {e}")
                return None
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    # Using a random port to prevent clashing when multiple drivers start (User's fix optimized for threads)
    port = random.randint(9222, 9322)
    options.add_argument(f"--remote-debugging-port={port}")
        
    # Add a slightly more modern chrome version to UA
    driver = webdriver.Chrome(options=options)
    
    # Set timeouts to prevent hanging - 40s balance
    driver.set_page_load_timeout(40) 
    driver.set_script_timeout(40)
    
    # Hide WebDriver flag
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
      "source": """
        Object.defineProperty(navigator, 'webdriver', {
          get: () => undefined
        })
      """
    })
    return driver

def safe_quit(driver):
    """Safely quit driver with WinError 6 protection."""
    if not driver: return
    try:
        driver.quit()
    except Exception as e:
        # WinError 6 handle invalid is common on Windows during cleanup; we can ignore it
        if "handle is invalid" not in str(e).lower():
            logging.warning(f"Error during driver quit: {e}")

# ==============================
# DATA EXTRACTION HELPERS
# ==============================
def clean_price(price_text):
    if not price_text: return 0
    # Strip currency prefixes FIRST to prevent "Rs." period from being kept as decimal
    text = str(price_text).strip()
    text = re.sub(r'^(Rs\.?|PKR|USD|\$)\s*', '', text, flags=re.IGNORECASE)
    # Remove everything except digits and dot
    cleaned = re.sub(r'[^\d.]', '', text)
    # If multiple dots, keep only the last one
    if cleaned.count('.') > 1:
        parts = cleaned.split('.')
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    
    try:
        val = float(cleaned) if (cleaned and cleaned != ".") else 0
        return val
    except:
        return 0

def clean_title(title, limit=120):
    if not title: return ""
    # Remove HTML tags if any leaked
    title = re.sub(r'<[^>]+>', '', str(title))
    # Remove excessive whitespace and newlines
    title = " ".join(title.split())
    # Truncate
    if len(title) > limit:
        title = title[:limit-3] + "..."
    return title.strip()

def get_image_url(item, base_url=""):
    """Universal image extraction logic."""
    img = item.find("img")
    if not img:
        return "https://via.placeholder.com/200"

    # Known placeholders to skip
    placeholders = ["placeholder", "loading", "animation_large", "blank.gif", "dot.gif", "empty.png"]
    
    # Try preferred attributes first
    # Amazon often uses data-a-dynamic-image
    for attr in ["data-a-dynamic-image", "data-src", "data-original", "data-lazy-src", "lazyload-src", "srcset", "src"]:
        val = img.get(attr)
        if val and not val.startswith("data:image"):
            # Ensure it's a URL/path and not just a density number (like "1")
            if not any(val.startswith(p) for p in ["http", "//", "/", "data:"]) and len(val) < 10:
                continue
                
            # Check if it's a known placeholder
            if any(p in val.lower() for p in placeholders):
                continue
                
            # Handle data-a-dynamic-image: it's a JSON-like string {"url": [w,h], ...}
            if attr == "data-a-dynamic-image":
                try:
                    # Clean the string for json.loads if needed (Amazon uses double quotes usually)
                    # Example: {"https://m.media-amazon.com/images/I/71...L._AC_UY218_.jpg":[218,218],...}
                    img_data = json.loads(val)
                    if img_data:
                        # Get the one with the largest resolution or just some value
                        val = list(img_data.keys())[0]
                except:
                    pass

            # Handle srcset: picking the highest res if available
            if attr == "srcset" and "," in val:
                parts = [p.strip() for p in val.split(",")]
                val = parts[-1].split(" ")[0]
            elif " " in val:
                val = val.split(" ")[0]
            
            # Handle protocol-less
            if val.startswith("//"):
                val = "https:" + val
            elif val.startswith("http://"):
                val = val.replace("http://", "https://")
            
            # Handle relative paths: if base_url and it looks like a path
            if base_url and val.startswith("/") and not val.startswith("//"):
                val = urljoin(base_url, val)
            
            # Protocol check for final URL
            if val.startswith("//"):
                val = "https:" + val
            
            # Convert .avif to .jpg (browsers on older Windows/MacOS might not support AVIF)
            if ".avif" in val:
                val = val.replace(".avif", ".jpg")
            
            # Upgrade Daraz/Alibaba thumbnails to larger sizes safely
            # Example: _200x200q80.jpg -> _400x400q80.jpg
            if "daraz" in val or "slatic.net" in val or "alicdn.com" in val:
                val = val.replace("_200x200q80", "_400x400q80")
                val = val.replace("_170x170", "_400x400")
                val = val.replace("_188x188", "_400x400")
                
            return val

    # Final fallback to src if we skipped placeholders but found nothing else
    val = img.get("src")
    if val and not val.startswith("data:image"):
        if val.startswith("//"): val = "https:" + val
        if base_url and val.startswith("/") and not val.startswith("//"): 
            val = urljoin(base_url, val)
        return val

    return "https://via.placeholder.com/200?text=No+Image"

# ==============================
# DARAZ API via Apify
# ==============================
def scrape_daraz_api(query):
    try:
        client = ApifyClient("YOUR_APIFY_TOKEN")
        run = client.actor("shahidirfan/daraz-pk-scraper").call(run_input={"searchQuery": query})
        products = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            price_val = clean_price(item.get("price", "0"))
            products.append({
                "name": item.get("title") or "No Name",
                "price": price_val,
                "price_text": f"Rs. {price_val:,}",
                "image": item.get("imageUrl") or "https://via.placeholder.com/200",
                "source": "Daraz",
                "best": False
            })
        return products
    except Exception as e:
        import logging
        logging.debug(f"Daraz API error: {e}")
        return []

# ==============================
# eBay Requests Scraper
# ==============================
def scrape_ebay_api(query):
    """Scrape eBay using direct HTTP requests - fast, no selenium needed."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sacat=0&LH_BIN=1"
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=20)
        logging.info(f"eBay requests status: {response.status_code}")
        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        
        # Try multiple selectors for eBay's evolving HTML structure
        items = soup.select("li.s-item")
        if not items:
            items = soup.find_all("li", class_=re.compile(r"s-item"))
            
        for item in items[:15]:
            try:
                # Title
                title_el = item.select_one(".s-item__title")
                if not title_el: continue
                title = title_el.get_text(strip=True).replace("Opens in a new window or tab", "").strip()
                if not title or "Shop on eBay" in title: continue
                
                # Price
                price_el = item.select_one(".s-item__price")
                if not price_el: continue
                price_text = price_el.get_text(strip=True)
                if " to " in price_text: price_text = price_text.split(" to ")[0]
                
                # Image - eBay lazy-loads images
                img_el = item.select_one(".s-item__image img")
                img_url = "https://via.placeholder.com/200"
                if img_el:
                    img_url = img_el.get("src") or img_el.get("data-src") or img_el.get("srcset", "").split(" ")[0] or img_url
                    if not img_url.startswith("http"):
                        img_url = "https://via.placeholder.com/200"
                
                # Link
                link_el = item.select_one("a.s-item__link")
                link = link_el.get("href") if link_el else "#"
                
                price_val = clean_price(price_text.replace(",", "").split(".")[0])
                pkr_price = int(price_val * 280) if price_val else 0
                if pkr_price == 0: continue
                
                products.append({
                    "name": title,
                    "price": pkr_price,
                    "price_text": price_text + f" (~Rs. {pkr_price:,})",
                    "image": img_url,
                    "url": link,
                    "source": "eBay",
                    "best": False
                })
            except Exception as inner_e:
                logging.debug(f"eBay item parse error: {inner_e}")
                continue
        
        logging.info(f"eBay requests returned {len(products)} products")
        return products
    except Exception as e:
        logging.error(f"eBay requests scraping error: {e}")
        return []


# ==============================
# Selenium fallback (Daraz)
# ==============================
# Daraz Requests Scraper
# ==============================
def scrape_daraz(query):
    """Scrape Daraz using their internal AJAX API (Fast, No Selenium)."""
    url = f"https://www.daraz.pk/catalog/?ajax=true&q={query.replace(' ', '+')}"
    headers = {
        "User-Agent": get_random_ua(),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.daraz.pk/"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return []
            
        data = r.json()
        mods = data.get('mods', {})
        list_items = mods.get('listItems', [])
        
        products = []
        for item in list_items[:15]:
            try:
                name = item.get('name')
                if not name: continue
                
                price_val = clean_price(item.get('price'))
                if not price_val: continue
                
                img_url = item.get('image')
                if img_url and img_url.startswith('//'):
                    img_url = "https:" + img_url
                
                link = item.get('productUrl') or item.get('itemUrl')
                if link and link.startswith('//'):
                    link = "https:" + link
                elif link and not link.startswith('http'):
                    link = "https://www.daraz.pk" + link
                
                products.append({
                    "name": name,
                    "price": price_val,
                    "price_text": f"Rs. {price_val:,}",
                    "image": img_url or "https://via.placeholder.com/200",
                    "url": link,
                    "source": "Daraz",
                    "best": False,
                    "rating": item.get('ratingScore') or 4.0,
                    "reviews_count": item.get('review') or 5
                })
            except:
                continue
        return products
    except Exception as e:
        print(f"Daraz AJAX Error: {e}")
        return []

# ==============================
# Selenium fallback (eBay)
# ==============================
def scrape_ebay_selenium(query):
    logging.info(f"Starting eBay Selenium (UC) scrape for: {query}")
    page_source = ""
    with selenium_semaphore:
        # Switch to UC for better anti-detection on eBay
        driver = get_driver(use_uc=True)
        if not driver:
            logging.error("Failed to initialize UC driver for eBay.")
            return []
            
        try:
            driver.get(f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}")
            
            # Wait for results with more robust selectors (s-card or s-item)
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".srp-results, .s-card, .s-item"))
                )
            except:
                logging.warning("eBay results container or items not found within timeout (Selenium UC)")

            # Better scroll strategy: Step-wise scrolling to trigger lazy images
            for step in range(3):
                driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * { (step + 1) / 3 });")
                time.sleep(1)
            
            page_source = driver.page_source
        finally:
            try:
                # Windows handle fix: wrap driver.quit() to prevent crashing thread on [WinError 6]
                driver.quit()
            except OSError as e:
                logging.warning(f"Handled OSError during eBay driver cleanup: {e}")
            except Exception as e:
                logging.warning(f"Handled Exception during eBay driver cleanup: {e}")
            
    soup = BeautifulSoup(page_source, "html.parser")
    products = []
    
    # eBay layout change: prioritize s-card then s-item
    items = soup.select(".s-card, .s-item")
    
    for item in items[:15]:
        try:
            # Title
            title_div = item.find(class_=re.compile("s-card__title|s-item__title"))
            if not title_div:
                continue
            title = title_div.get_text(strip=True).replace("Opens in a new window or tab", "")
            if "Shop on eBay" in title: # Skip the "Shop on eBay" ad banner
                continue
                
            # Price
            price_span = item.find(class_=re.compile("s-card__price|s-item__price"))
            if not price_span:
                continue
            price_text = price_span.get_text(strip=True)
            
            # Extract only the first price if it's a range like "$20.00 to $30.00"
            if " to " in price_text:
                price_text = price_text.split(" to ")[0]
            
            # Image
            img_tag = item.find("img")
            img_url = "https://via.placeholder.com/200"
            if img_tag:
                img_url = img_tag.get("src") or img_tag.get("data-src") or "https://via.placeholder.com/200"
                if ("ir.ebaystatic.com" in img_url or "base64" in img_url) and img_tag.get("data-src"):
                    img_url = img_tag.get("data-src")
            
            # Link
            link_tag = item.find("a", class_=re.compile("s-card__link|s-item__link")) or item.find("a")
            link = link_tag.get("href") if link_tag else "#"
            
            # Use clean_price and convert to PKR
            price_val = clean_price(price_text.split(".")[0])
            pkr_price = int(price_val * 280)

            products.append({
                "name": title,
                "price": pkr_price,
                "price_text": f"{price_text} (~Rs. {pkr_price})",
                "image": img_url,
                "url": link,
                "source": "eBay",
                "best": False
            })
        except Exception as e:
            logging.error(f"Error parsing eBay item: {e}")
            continue
    return products


# ==============================
# Selenium fallback (Amazon)
# ==============================
def scrape_amazon_selenium(query):
    logging.info(f"Starting Amazon Selenium (UC) scrape for: {query}")
    # Lock to prevent Chrome OOM crashes on concurrent searches
    selenium_lock.acquire()
    with selenium_semaphore:
        # Use undetected-chromedriver for Amazon
        driver = get_driver(use_uc=True)
        if not driver:
            logging.error("Failed to initialize UC driver for Amazon.")
            selenium_lock.release()
            return []
            
        page_source = ""
        try:
            # Navigate to Amazon with explicit timeout handling
            driver.get(f"https://www.amazon.com/s?k={query.replace(' ', '+')}")
        except Exception as e:
            logging.warning(f"Amazon page load timeout or error (attempting to continue anyway): {e}")

        try:
            # Handle Amazon "Continue shopping" or Captcha-lite page
            if "Continue shopping" in driver.page_source or "validateCaptcha" in driver.current_url:
                logging.info("Amazon redirect/captcha detected, attempting to bypass...")
                # Try clicking any link that might bypass
                bypass_selectors = [By.PARTIAL_LINK_TEXT, By.CSS_SELECTOR]
                bypass_targets = ["Continue shopping", "div.a-box-inner a"]
                for selector, target in zip(bypass_selectors, bypass_targets):
                    try:
                        el = driver.find_element(selector, target)
                        if el:
                            el.click()
                            time.sleep(2)
                            break
                    except: continue

            # Wait for search results with shorter wait to avoid hanging entire app
            # Scroll down to trigger lazy loading
            driver.execute_script("window.scrollTo(0, 1000);")
            time.sleep(1)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-component-type="s-search-result"], .s-result-item.s-asin'))
            )
            page_source = driver.page_source
        except Exception as e:
            logging.warning(f"Amazon search results wait failed: {e}")
            page_source = driver.page_source # Take what we have
        finally:
            safe_quit(driver)
            selenium_lock.release()
        
    if not page_source:
        return []
        
    soup = BeautifulSoup(page_source, "html.parser")
    products = []
    
    items = soup.find_all("div", {"data-component-type": "s-search-result"})
    if not items:
        # Fallback to broader selector if specific data-component-type is missing
        items = soup.select(".s-result-item.s-asin")
    
    for item in items[:10]:
        try:
            # Title - prefer subagent verified h2 a span
            title_tag = item.select_one("h2 a span") or item.find("h2") or item.select_one(".a-size-medium") or item.select_one(".a-size-base-plus")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not title:
                continue
            
            link_tag = item.select_one("h2 a") or item.find("a", class_="a-link-normal")
            link = "https://www.amazon.com" + link_tag["href"] if link_tag and 'href' in link_tag.attrs else "#"
            
            # Price - use subagent verified .a-offscreen
            price_val = 0
            price_text = ""
            
            # 1. Try offscreen price (most reliable)
            price_offscreen = item.select_one(".a-price .a-offscreen")
            if price_offscreen:
                price_text = price_offscreen.get_text(strip=True)
                price_val = clean_price(price_text)
            
            # 2. Try whole/fraction fallback
            if not price_val:
                price_whole = item.find("span", class_="a-price-whole")
                price_fraction = item.find("span", class_="a-price-fraction")
                if price_whole:
                    whole_clean = re.sub(r'[^\d]', '', price_whole.text.strip())
                    frac_clean = re.sub(r'[^\d]', '', price_fraction.text.strip()) if price_fraction else '00'
                    if whole_clean:
                        price_val = float(f"{whole_clean}.{frac_clean}")
                        price_text = f"${price_val:.2f}"
            
            if not price_val:
                # Try regex fallback ($ or PKR or Rs)
                p = re.search(r'(?:\$|PKR|Rs\.?)\s*([\d,]+\.?\d*)', item.get_text())
                if p:
                    price_val = clean_price(p.group(1))
                    price_text = p.group(0)
                    
            # Set default currency
            is_pkr = "PKR" in price_text or "Rs" in price_text
            
            # Sanity check — filter out obviously wrong prices
            # If PKR, range should be 100 to 5,000,000. If USD, 1 to 10,000.
            if is_pkr:
                if price_val > 5000000 or price_val < 100:
                    continue
                pkr_price = int(price_val)
                display_price_text = f"Rs. {pkr_price:,}"
            else:
                if price_val > 10000 or price_val < 1:
                    continue
                # Convert USD to PKR (~280 PKR per USD)
                pkr_price = int(price_val * 280)
                display_price_text = f"${price_val:.2f} (~Rs. {pkr_price:,})"
            
            # Robust Image Extraction
            img_url = get_image_url(item, "https://www.amazon.com")
            
            products.append({
                "name": clean_title(title),
                "price": pkr_price,
                "price_text": display_price_text,
                "image": img_url,
                "url": link,
                "source": "Amazon",
                "best": False
            })
        except Exception as e:
            continue
            
    return products

# ==============================
# Amazon Requests Scraper
# ==============================
def scrape_amazon_api(query):
    """Requests-based Amazon fallback scraper using global session."""
    headers = {
        "User-Agent": get_random_ua(),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    try:
        session = get_session()
        # Rotation of User Agents is already handled by get_random_ua() in get_session if we were creating it fresh,
        # but here we use the global session. Let's ensure we use a fresh-looking set of headers.
        headers["User-Agent"] = get_random_ua()
        # Reduced timeout to 5s so the Selenium fallback has time to run within the 25s total wait limit
        response = session.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        items = soup.find_all("div", {"data-component-type": "s-search-result"})
        for item in items[:10]:
            try:
                # Title
                title_elem = item.find("h2") or item.select_one(".a-size-medium") or item.select_one(".a-size-base-plus")
                if not title_elem: continue
                title = title_elem.get_text(strip=True)
                if not title: continue
                # Link
                link_tag = item.select_one("h2 a") or item.find("a", class_="a-link-normal")
                link = "https://www.amazon.com" + (link_tag["href"] if link_tag and 'href' in link_tag.attrs else "#")
                # Price — 3 methods
                price_val = 0
                price_text = ""
                pw = item.find("span", class_="a-price-whole")
                pf = item.find("span", class_="a-price-fraction")
                if pw:
                    whole = re.sub(r'[^\d]', '', pw.text.strip())
                    frac = re.sub(r'[^\d]', '', pf.text.strip()) if pf else '00'
                    if whole:
                        price_val = float(f"{whole}.{frac}")
                if not price_val:
                    for span in item.find_all("span"):
                        t = span.get_text(strip=True)
                        m = re.match(r'^(?:\$|PKR|Rs\.?)\s*([\d,]+\.?\d*)$', t)
                        if m:
                            price_val = clean_price(m.group(1))
                            price_text = t
                            break
                if not price_val:
                    m = re.search(r'(?:\$|PKR|Rs\.?)\s*([\d,]+\.\d+)', item.get_text())
                    if m:
                        price_val = clean_price(m.group(1))
                        price_text = m.group(0)
                if not price_val: continue

                # Set default currency
                is_pkr = "PKR" in price_text or "Rs" in response.text[:2000] # Rough check
                
                # Currency Detection & Sanity Check
                if is_pkr or (price_val > 1000 and "$" not in price_text):
                    pkr_price = int(price_val)
                    display_price_text = f"Rs. {pkr_price:,}"
                    if pkr_price > 5000000 or pkr_price < 100:
                        continue
                else:
                    pkr_price = int(price_val * 280)
                    display_price_text = f"${price_val:.2f} (~Rs. {pkr_price:,})"
                    if price_val > 10000 or price_val < 0.1:
                        continue
                
                img_url = get_image_url(item, "https://www.amazon.com")

                products.append({
                    "name": clean_title(title),
                    "price": pkr_price,
                    "price_text": display_price_text,
                    "image": img_url,
                    "url": link,
                    "source": "Amazon",
                    "best": False
                })
            except:
                continue
        return products
    except Exception as e:
        print(f"Amazon requests error: {e}")
        return []

# = = = = = = = = = = = = = = =
# Helper functions for ThreadPool
# = = = = = = = = = = = = = = =
def get_telemart(query):
    return scrape_telemart(query)

def scrape_daraz_selenium(query):
    """Selenium-based Daraz scraper - confirmed selectors from live HTML."""
    logging.info(f"Starting Daraz Selenium scrape for: {query}")
    base_url = "https://www.daraz.pk"
    url = f"{base_url}/catalog/?q={query.replace(' ', '+')}"
    driver = None
    try:
        with selenium_semaphore:
            # Strategy 'eager' is usually best
            for attempt in range(3):
                try:
                    driver = get_driver(strategy='eager')
                    driver.get(url)
                    # wait logic as per user request
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-tracking='product-card']"))
                    )
                    break
                except Exception as e:
                    print(f"Daraz driver.get error (attempt {attempt+1}): {e}")
                    if driver: driver.quit()
                    time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Scroll through full page to trigger ALL lazy images (not just half)
            try:
                scroll_height = driver.execute_script("return document.body.scrollHeight")
                # Scroll in steps to trigger IntersectionObserver on all cards
                for step in [0.3, 0.6, 1.0]:
                    driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {step})")
                    time.sleep(0.7)
                # Scroll back to top
                driver.execute_script("window.scrollTo(0, 0)")
                time.sleep(1)
                # Re-capture full HTML after images have loaded
                soup = BeautifulSoup(driver.page_source, "html.parser")
            except:
                pass
            products = []
            
            items = soup.select("[data-tracking='product-card']")
            if not items:
                items = soup.select("[data-qa-locator='product-item']")
            
            for item in items[:12]:
                try:
                    # Robust Image Extraction
                    img_url = get_image_url(item, base_url)
                    
                    # Link
                    link_tag = item.find("a")
                    link = link_tag.get("href") if link_tag else "#"
                    if link and link.startswith("//"):
                        link = "https:" + link
                    elif link and not link.startswith("http"):
                        link = urljoin(base_url, link)
                    
                    # Title - extraction based on live subagent check
                    name_tag = (item.select_one("a[title]") or 
                                item.select_one(".title--w9WB") or 
                                item.select_one(".RfSBy") or
                                item.select_one("[class*='title']") or
                                item.find("h3"))
                    if not name_tag:
                        logging.debug(f"Daraz item: name_tag not found in {item.prettify()[:200]}")
                        continue
                    name = name_tag.get("title") or name_tag.text.strip()
                    if not name: continue
                    
                    price_val = 0
                    price_tag = item.select_one(".ooOxS") or item.select_one(".price") or item.select_one("[class*='price']")
                    if price_tag:
                        price_val = clean_price(price_tag.text)
                    if not price_val:
                        price_elem = item.find(string=re.compile(r'Rs\.?\s*[\d,]'))
                        if price_elem:
                            price_val = clean_price(str(price_elem))
                    if not price_val: continue
                    
                    products.append({
                        "name": name,
                        "price": price_val,
                        "price_text": f"Rs. {price_val:,}",
                        "image": img_url,
                        "url": link,
                        "source": "Daraz",
                        "best": False
                    })
                except:
                    continue
            return products
    except Exception as e:
        print(f"Daraz Selenium Error: {e}")
        return []
    finally:
        safe_quit(driver)

def get_daraz(query):
    # Daraz AJAX is preferred (fast and reliable)
    res = scrape_daraz(query)
    if not res:
        print("Daraz AJAX failed. Falling back to Selenium.")
        res = scrape_daraz_selenium(query)
    return res

def get_ebay(query):
    """
    eBay scraper - uses requests with rotating UA.
    If eBay returns 403 (blocked), returns empty gracefully to avoid 45s Selenium timeouts.
    """
    res = scrape_ebay_api(query)
    if not res:
        # Try with a different approach: eBay search via a different URL pattern
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
                "Referer": "https://www.google.com",
            }
            url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_ipg=60"
            session = requests.Session()
            session.headers.update(headers)
            # First visit homepage to get cookies
            session.get("https://www.ebay.com", timeout=10)
            response = session.get(url, timeout=20)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.content, "html.parser")
                items = soup.select("li.s-item")
                products = []
                for item in items[:12]:
                    try:
                        title_el = item.select_one(".s-item__title")
                        price_el = item.select_one(".s-item__price")
                        link_el = item.select_one("a.s-item__link")
                        img_el = item.select_one(".s-item__image img")
                        if not (title_el and price_el): continue
                        title = title_el.get_text(strip=True).replace("Opens in a new window or tab", "").strip()
                        if "Shop on eBay" in title or not title: continue
                        price_text = price_el.get_text(strip=True)
                        if " to " in price_text: price_text = price_text.split(" to ")[0]
                        price_val = clean_price(price_text.replace(",", "").split(".")[0])
                        pkr_price = int(price_val * 280) if price_val else 0
                        if pkr_price == 0: continue
                        img_url = (img_el.get("src") or img_el.get("data-src") or "https://via.placeholder.com/200") if img_el else "https://via.placeholder.com/200"
                        products.append({
                            "name": title, "price": pkr_price,
                            "price_text": price_text + f" (~Rs. {pkr_price:,})",
                            "image": img_url,
                            "url": link_el.get("href") if link_el else "#",
                            "source": "eBay", "best": False
                        })
                    except:
                        continue
                if products:
                    logging.info(f"eBay session retry returned {len(products)} products")
                    return products
        except Exception as e:
            logging.error(f"eBay session retry failed: {e}")
        logging.warning("eBay is blocked on requests. Falling back to Selenium.")
        return scrape_ebay_selenium(query)
    return res

def get_amazon(query):
    # Try requests first (Amazon hides prices from headless Selenium)
    res = scrape_amazon_api(query)
    if not res:
        print("Amazon requests returned empty. Falling back to Selenium.")
        res = scrape_amazon_selenium(query)
    return res

# ==============================
# ==============================
# ==============================
# COMBINED SCRAPER
# ==============================
def scrape_all_sources(query, fallback=False, sources_enabled=None):
    if sources_enabled is None:
        sources_enabled = {
            'daraz': True, 'ebay': True, 'amazon': True,
            'telemart': True, 'surmawala': True, 'ubuy': True, 'shophive': True, 'clicky': True, 'mega': True, 'priceoye': True, 'alfatah': True
        }
    # Increased workers to 20 to ensure fast scrapers (API based) are not blocked 
    # by slow Selenium scrapers waiting for the semaphore.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
    futures = {}
    
    # helper to submit if enabled
    def submit_if(key, func, query):
        if sources_enabled.get(key) not in (False, 'false', None, '') or sources_enabled.get(f"{key}_enabled") == 'true':
            futures[key] = executor.submit(func, query)

    submit_if('daraz', get_daraz, query)
    submit_if('ebay', get_ebay, query)
    submit_if('amazon', get_amazon, query)
    submit_if('telemart', get_telemart, query)
    submit_if('surmawala', scrape_surmawala, query)
    submit_if('mega', scrape_mega_pk, query)
    submit_if('clicky', scrape_clicky, query)
    submit_if('ubuy', scrape_ubuy, query)
    submit_if('shophive', scrape_shophive, query)
    submit_if('priceoye', scrape_priceoye, query)
    submit_if('alfatah', scrape_alfatah, query)
    
    results_map = {}
    timeout_count = 0
    # Increased total wait time to 45s for better result coverage from slow Selenium scrapers
    done, not_done = concurrent.futures.wait(futures.values(), timeout=45)
    
    for key, f in futures.items():
        if f in done:
            try:
                res = f.result()
                results_map[key] = res if res else []
            except Exception as fe:
                logging.error(f"Scraper error [{key}]: {fe}")
                results_map[key] = []
        else:
            logging.warning(f"Scraper [{key}] timed out after 45s.")
            results_map[key] = []
            timeout_count += 1
    
    # Shutdown without blocking indefinitely for hanging threads
    executor.shutdown(wait=False)

    daraz_products    = results_map.get('daraz', [])
    ebay_products     = results_map.get('ebay', [])
    amazon_products   = results_map.get('amazon', [])
    telemart_products = results_map.get('telemart', [])
    surmawala_products= results_map.get('surmawala', [])
    mega_products      = results_map.get('mega', [])
    clicky_products    = results_map.get('clicky', [])
    ubuy_products      = results_map.get('ubuy', [])
    shophive_products  = results_map.get('shophive', [])
    priceoye_products  = results_map.get('priceoye', [])
    alfatah_products   = results_map.get('alfatah', [])
    
    print(f"  Summary: Daraz:{len(daraz_products)} eBay:{len(ebay_products)} "
          f"Amazon:{len(amazon_products)} Telemart:{len(telemart_products)} "
          f"Surmawala:{len(surmawala_products)} Mega:{len(mega_products)} "
          f"Clicky:{len(clicky_products)} Ubuy:{len(ubuy_products)} "
          f"Shophive:{len(shophive_products)} PriceOye:{len(priceoye_products)} "
          f"Al-Fatah:{len(alfatah_products)}")

    all_products = (daraz_products + ebay_products + amazon_products + 
                    telemart_products + surmawala_products + mega_products + 
                    clicky_products + ubuy_products + shophive_products + 
                    priceoye_products + alfatah_products)

    # Calculate relevance and finalize product data
    query_words = [w.lower() for w in query.split() if len(w) > 2]
    
    for p in all_products:
        name_lower = p['name'].lower()
        score = 0
        if not query_words:
            score = 100
        else:
            matches = 0
            for w in query_words:
                if re.search(r'\b' + re.escape(w.rstrip('s')) + r'\b', name_lower):
                    matches += 1
            score = (matches / len(query_words)) * 100
            
            # Boost for exact matches or matches at start
            if query.lower() in name_lower:
                score += 20
            
            # Penalize for common "irrelevant" words if query is specific
            # e.g., if searching for 'glasses' (eyewear), penalize 'drinking', 'cup', 'disposable'
            if 'glasses' in query_words:
                negatives = ['drinking', 'cup', 'disposable', 'plastic', 'water', 'wine']
                if any(n in name_lower for n in negatives):
                    score -= 50
        
        p['relevance'] = score

    # Sort: Primary by Relevance (Descending), Secondary by Price (Ascending)
    all_products = sorted(all_products, key=lambda x: (-x["relevance"], x["price"]))
    if all_products:
        # Find lowest price greater than 0
        valid_prices = [p["price"] for p in all_products if p["price"] > 0]
        if valid_prices:
            lowest = min(valid_prices)
            for p in all_products:
                if p["price"] == lowest:
                    p["best"] = True
                    
    # Prevent "No Products Found" by running a broad matching single keyword search if everything fails
    # But DO NOT fallback if the lack of results was primarily due to timeouts, to avoid CPU/Socket death spirals.
    if not all_products and not fallback and timeout_count < 3:
        broad_query = query.split()[0] if len(query.split()) > 0 else "trending"
        print(f"Initial query '{query}' yielded no results. Running broad fallback query: '{broad_query}'")
        return scrape_all_sources(broad_query, fallback=True, sources_enabled=sources_enabled)
        
    return all_products

# ==============================
# PRICEOYE SCRAPER
# ==============================
def scrape_priceoye(query):
    """Scrapes PriceOye using Requests and BeautifulSoup."""
    url = f"https://priceoye.pk/search?q={query.replace(' ', '+')}"
    headers = {
        "User-Agent": get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://priceoye.pk/"
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return []
            
        soup = BeautifulSoup(r.text, 'html.parser')
        # Updated selector: PriceOye uses .product-card now
        items = soup.select('.product-card') or soup.select('.productBox') or soup.select('div[class*="productBox"]')
        
        products = []
        # Filter out very short common words from query for better matching
        stopwords = {'the', 'and', 'for', 'with', 'from', 'best', 'price', 'deals', 'online', 'pakistan'}
        query_words = [w for w in query.lower().split() if len(w) > 2 and w not in stopwords]
        
        # Build strict whole-word regex pattern
        if query_words:
            # Match singular/plural for some common items (glass/glasses, iron/irons)
            pattern_str = r'\b(' + '|'.join(re.escape(w.rstrip('s')) + r'e?s?' for w in query_words) + r')\b'
            pattern = re.compile(pattern_str, re.IGNORECASE)
        else:
            pattern = None
        
        for item in items[:21]:
            try:
                # Title
                title_elem = item.select_one('.p-title') or item.find('div', class_='p-title')
                if not title_elem:
                    continue
                name = title_elem.text.strip()
                
                # Category Block: Protect against common 'Trending' traps on PriceOye
                # If searching for non-tech items like 'glasses' or 'iron', block 'Mobiles', 'Trimmers', etc.
                name_lc = name.lower()
                tech_categories = ['phone', 'mobile', 'smartphone', 'itel', 'nokia', 'vivo', 'oppo', 'infinix', 'trimmer', 'clipper', 'shaver', 'earbud', 'watch', 'ronin', 'audionic']
                non_tech_queries = ['iron', 'glasses', 'perfume', 'jug', 'cup', 'bottle', 'shirt', 'shoe']
                
                if any(nt in query.lower() for nt in non_tech_queries):
                    if any(tc in name_lc for tc in tech_categories):
                        continue
                
                # Double Check Relevance: Ensure at least one query word is in the name
                if pattern and not pattern.search(name_lc):
                    continue
                
                relevance_matched = True
                        
                # Anti-noise Filter: If searching for 'iron', exclude obvious mobiles/phones (often matched by color 'Iron Grey')
                if 'iron' in query.lower():
                    if any(x in name.lower() for x in ['phone', 'mobile', 'smartphone', 'itel', 'nokia', 'vivo', 'oppo', 'infinix']):
                        continue
                
                # Link
                link_tag = item.select_one('a')
                link = link_tag['href'] if link_tag and 'href' in link_tag.attrs else url
                
                # Price
                price_val = 0
                price_elem = item.select_one('.price-box')
                if price_elem:
                    price_val = clean_price(price_elem.text)
                if not price_val:
                    continue
                    
                # Image
                img_url = ""
                img_elem = item.select_one('amp-img[src]') or item.select_one('img[src]')
                if img_elem:
                    img_url = img_elem['src']
                if not img_url:
                    img_url = "https://via.placeholder.com/200"
                    
                products.append({
                    "name": name,
                    "price": int(price_val),
                    "price_text": f"Rs. {int(price_val):,}",
                    "image": img_url,
                    "url": link,
                    "source": "PriceOye",
                    "best": False,
                    "relevance_matched": relevance_matched if 'relevance_matched' in locals() else False
                })
            except Exception as e:
                continue
                
        # Relevance Threshold: If PriceOye returns a 'Trending' page that doesn't 
        # contain a single relevant product for the query, return empty.
        # This prevents 'glasses' search from showing 'refrigerators'.
        if products:
            matched_any = any(p.get('relevance_matched', False) for p in products)
            if not matched_any:
                print(f"PriceOye: No direct keyword matches for '{query}'. Ignoring trending fallbacks.")
                return []
                
        # Remove internal flag before returning
        for p in products:
            p.pop('relevance_matched', None)
            
        return products
    except Exception as e:
        print(f"PriceOye scraper error: {e}")
        return []

# ==============================
# TELEMART SCRAPER (Algolia API - Fast, No Selenium)
# ==============================
def scrape_telemart(query):
    """Replaces Selenium-based Telemart scraper with direct Algolia API call."""
    try:
        url = "https://7z6unqyqer-1.algolianet.com/1/indexes/*/queries"
        headers = {
            "x-algolia-application-id": "7Z6UNQYQER",
            "x-algolia-api-key": "9b4c33f99e845fe1363fd4c6ceb0f467",
            "Content-Type": "application/json",
            "Connection": "close"
        }
        payload = {
            "requests": [
                {
                    "indexName": "products",
                    # Request more hits so we still get 10+ after filtering irrelevant results
                    "params": f"query={query}&hitsPerPage=20"
                }
            ]
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        data = response.json()
        hits = data.get('results', [{}])[0].get('hits', [])
        
        # Build word-boundary keyword set for relevance filtering
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        
        products = []
        for hit in hits:
            try:
                name = hit.get('title') or hit.get('name') or hit.get('product_name', '')
                if not name: continue
                
                # Relevance: Flexible matching (handles plural/singular)
                name_lower = name.lower()
                if query_words and not any(
                    (re.search(r'\b' + re.escape(w.rstrip('s')) + r'.*?\b', name_lower))
                    for w in query_words
                ):
                    continue
                
                price_val = hit.get('sale_price') or hit.get('price') or 0
                if not price_val: continue
                price_val = int(price_val)
                
                img_url = hit.get('mainImageLink', '') or hit.get('image', '')
                if img_url and img_url.startswith('//'):
                    img_url = 'https:' + img_url
                
                slug = hit.get('slug', '')
                link = f"https://www.telemart.pk/{slug}" if slug else "https://www.telemart.pk"
                
                products.append({
                    "name": name,
                    "price": price_val,
                    "price_text": f"Rs. {price_val:,}",
                    "image": img_url,
                    "url": link,
                    "source": "Telemart",
                    "best": False
                })
                if len(products) >= 20:
                    break
            except:
                continue
        return products
    except Exception as e:
        print(f"Telemart API Error: {e}")
        return []

# ==============================
# MEGA.PK SCRAPER (Requests - Fast, No Selenium)
# ==============================
def scrape_mega_pk(query):
    """Scrape Mega.pk using requests and BeautifulSoup."""
    # Lowercase query and try singular if plural is used
    query_clean = query.lower().strip()
    def fetch_mega(q):
        url = f"https://www.mega.pk/search/{q.replace(' ', '+')}/"
        headers = {
            "User-Agent": get_random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, 'html.parser')
            items = soup.select('.item_grid li') or soup.select('.product-list-item')
            return items, soup
        except: return [], None

    items, soup = fetch_mega(query_clean)
    
    # Fallback: if plural "Laptops" yields 0, try singular "Laptop"
    if not items and query_clean.endswith('s'):
        singular = query_clean.rstrip('s')
        if len(singular) >= 3:
            items, soup = fetch_mega(singular)

    if not items:
        return []
    
    products = []
        
    for item in items[:20]:
        try:
            # Title & Link
            title_elem = item.select_one('h3 a')
            if not title_elem:
                continue
            name = title_elem.text.strip()
            link = title_elem['href'] if 'href' in title_elem.attrs else ""
            if link and not link.startswith('http'):
                link = "https://www.mega.pk" + link
                
            # Price
            price_elem = item.select_one('.cat_price') or item.select_one('.price')
            price_val = 0
            price_text = "No Price"
            if price_elem:
                # Clean up: Mega.pk often has two prices (old and new) concatenated or separated by space
                # Example: "Rs. 181,999Rs. 175,000" or "Rs. 181,999 -PKR"
                price_raw = price_elem.get_text(strip=True).replace('-PKR', '').strip()
                # Use regex to find all price-like patterns and pick the smallest non-zero one
                found_prices = re.findall(r'[\d,]+', price_raw)
                cleaned_prices = [clean_price(p) for p in found_prices if clean_price(p) > 0]
                if cleaned_prices:
                    price_val = min(cleaned_prices)
                    price_text = f"Rs. {price_val:,}"
            
            if not price_val:
                continue

            # Image
            img_elem = item.select_one('.image img')
            img_url = ""
            if img_elem:
                img_url = img_elem.get('src') or img_elem.get('data-src')
            if img_url and not img_url.startswith('http'):
                img_url = "https://www.mega.pk" + img_url
            if not img_url:
                img_url = "https://via.placeholder.com/200"

            products.append({
                "name": name,
                "price": price_val,
                "price_text": price_text,
                "image": img_url,
                "url": link,
                "source": "Mega.pk",
                "best": False
            })
        except:
            continue
    return products

# ==============================
# CLICKY.PK SCRAPER (API - Fast, No Selenium)
# ==============================
def scrape_clicky(query):
    """Scrape Clicky.pk using their internal search API."""
    url = f"https://www.clicky.pk/api/search/products?q={query.replace(' ', '+')}&limit=24&page=1"
    headers = {
        "User-Agent": get_random_ua(),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.clicky.pk/",
        "Connection": "keep-alive"
    }

    try:
        session = requests.Session()
        r = session.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return []
            
        data = r.json()
        results = data.get('results', [])
        if not results and 'data' in data:
            results = data['data'].get('results', [])
            
        # Build query words for relevance filtering
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        
        products = []
        for item in results[:20]:
            try:
                name = item.get('name') or item.get('title', '')
                if not name: continue
                
                # Relevance: Ensure at least one query word matches (whole-word)
                # Relevance: Flexible matching (handles plural/singular)
                name_lower = name.lower()
                if query_words and not any(
                    (re.search(r'\b' + re.escape(w.rstrip('s')) + r'.*?\b', name_lower))
                    for w in query_words
                ):
                    continue
                
                # Price logic based on API inspection
                price_val = 0
                price_text = "No Price"
                p = item.get('price')
                if isinstance(p, dict):
                    price_val = p.get('selling_price') or p.get('original_price') or 0
                else:
                    price_val = p or 0
                
                if not price_val: continue
                price_val = int(price_val)
                price_text = f"Rs. {price_val:,}"
                
                # Image
                img_url = item.get('featuredImageUrl') or item.get('image') or item.get('thumbnail')
                if not img_url:
                    img_url = "https://via.placeholder.com/200"
                
                # Link pattern verified as /product/{id}
                prod_id = item.get('id')
                link = f"https://www.clicky.pk/product/{prod_id}" if prod_id else "https://www.clicky.pk"

                products.append({
                    "name": name,
                    "price": price_val,
                    "price_text": price_text,
                    "image": img_url,
                    "url": link,
                    "source": "Clicky.pk",
                    "best": False
                })
            except:
                continue
        return products
    except Exception as e:
        print(f"Clicky.pk scraper error: {e}")
        return []


# ==============================
# SURMAWALA SCRAPER (Shopify JSON API)
# ==============================
def scrape_surmawala(query):
    try:
        def fetch_hits(q):
            url = f"https://surmawala.pk/search/suggest.json?q={q.replace(' ', '+')}&resources[type]=product&resources[limit]=20"
            headers = {
                "User-Agent": get_random_ua(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://surmawala.pk/",
                "X-Requested-With": "XMLHttpRequest",
                "Connection": "close"
            }
            # Retry with increasing timeouts to handle slow/unstable responses
            for attempt_timeout in [15, 25]:
                try:
                    response = requests.get(url, headers=headers, timeout=attempt_timeout)
                    if response.status_code != 200:
                        return []
                    return response.json().get('resources', {}).get('results', {}).get('products', [])
                except requests.exceptions.Timeout:
                    logging.warning(f"Surmawala timeout ({attempt_timeout}s) for query: {q}")
                    continue
                except Exception as e:
                    logging.warning(f"Surmawala fetch error: {e}")
                    return []
            return []

        # Try full query first
        hits = fetch_hits(query)
        
        # If full multi-word query returns nothing, retry with first meaningful keyword
        if not hits and ' ' in query:
            words = [w for w in query.split() if len(w) > 2]
            if words:
                hits = fetch_hits(words[0])

        # Whole-word relevance filter (avoids fuzzy Shopify matches)
        query_words = [w.lower() for w in query.split() if len(w) > 2]
        products = []
        for hit in hits:
            try:
                name = hit.get('title', '')
                if not name: continue
                # Improved relevance check: match either as whole word or common sub-word parts for glasses/eyewear
                name_lower = name.lower()
                matched = False
                if not query_words:
                    matched = True
                else:
                    for w in query_words:
                        # Match whole word OR specific common compound word patterns
                        if re.search(r'\b' + re.escape(w) + r'\b', name_lower):
                            matched = True
                            break
                        # Special case: allow 'glasses' to match 'eyeglasses' or 'sunglasses'
                        if w == 'glasses' and ('eyeglasses' in name_lower or 'sunglasses' in name_lower):
                            matched = True
                            break
                        # Allow partial match for longer words (e.g. 'eyewear' matches 'eyewear-container')
                        if len(w) > 4 and w in name_lower:
                            matched = True
                            break
                
                if not matched:
                    # Fallback: check if any query word is a substring of the title
                    if query_words and any(w.rstrip('s') in name_lower for w in query_words):
                        matched = True
                
                if not matched:
                    continue
                link = hit.get('url', '')
                if link and not link.startswith('http'):
                    link = 'https://surmawala.pk' + link
                # Price is in paise (0.01 of a rupee), like Shopify uses cents
                price_val = hit.get('price', '0')
                price_val = int(float(str(price_val).replace(',', '')) if price_val else 0)
                if not price_val: continue
                img_url = hit.get('image', '') or hit.get('featured_image', {}).get('url', '')
                if img_url and img_url.startswith('//'):
                    img_url = 'https:' + img_url
                products.append({
                    "name": name,
                    "price": price_val,
                    "price_text": f"Rs. {price_val:,}",
                    "image": img_url,
                    "url": link,
                    "source": "Surmawala",
                    "best": False
                })
            except:
                continue
        return products
    except Exception as e:
        print(f"Surmawala Error: {e}")
        return []

# ==============================
# AL-FATAH SCRAPER (Shopify JSON API)
# ==============================
def scrape_alfatah(query):
    try:
        def fetch_hits(q):
            url = f"https://www.alfatah.pk/search/suggest.json?q={q.replace(' ', '+')}&resources[type]=product&resources[limit]=20"
            headers = {
                "User-Agent": get_random_ua(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.alfatah.pk/",
                "Connection": "close"
            }
            for attempt_timeout in [8, 15]:
                try:
                    response = requests.get(url, headers=headers, timeout=attempt_timeout)
                    if response.status_code != 200:
                        return []
                    return response.json().get('resources', {}).get('results', {}).get('products', [])
                except requests.exceptions.Timeout:
                    continue
                except:
                    return []
            return []

        hits = fetch_hits(query)
        if not hits and ' ' in query:
            words = [w for w in query.split() if len(w) > 2]
            if words:
                hits = fetch_hits(words[0])

        query_words = [w.lower() for w in query.split() if len(w) > 2]
        products = []
        for hit in hits:
            try:
                name = hit.get('title', '')
                if not name: continue
                
                name_lower = name.lower()
                matched = False
                if not query_words:
                    matched = True
                else:
                    for w in query_words:
                        if re.search(r'\b' + re.escape(w) + r'\b', name_lower):
                            matched = True
                            break
                        if len(w) > 4 and w in name_lower:
                            matched = True
                            break
                if not matched:
                    if query_words and any(w.rstrip('s') in name_lower for w in query_words):
                        matched = True
                
                if not matched:
                    continue
                    
                link = hit.get('url', '')
                if link and not link.startswith('http'):
                    link = 'https://www.alfatah.pk' + link
                    
                price_val = hit.get('price', '0')
                price_val = int(float(str(price_val).replace(',', '')) if price_val else 0)
                if not price_val: continue
                
                img_url = hit.get('image', '') or hit.get('featured_image', {}).get('url', '')
                if img_url and img_url.startswith('//'):
                    img_url = 'https:' + img_url
                    
                products.append({
                    "name": name,
                    "price": price_val,
                    "price_text": f"Rs. {price_val:,}",
                    "image": img_url,
                    "url": link,
                    "source": "Al-Fatah",
                    "best": False
                })
            except:
                continue
        return products
    except Exception as e:
        print(f"Al-Fatah Error: {e}")
        return []

# ==============================
# UBUY.COM.PK SCRAPER (Requests + esonesearch)
# ==============================
def scrape_ubuy(query):
    """Scrape Ubuy.com.pk using requests and beautifulsoup and its esonesearch API."""
    import base64
    import json
    
    # 1. Fetch main search page to get CSRF token and bypass Cloudflare
    url = f"https://www.ubuy.com.pk/en/search/?q={query.replace(' ', '+')}"
    # Use a fresh cloudscraper session specifically for Ubuy to avoid session cookie sharing/blocking
    session = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    products = []
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            print(f"Ubuy landing page failed with status {r.status_code}")
            return []
            
        html = r.text
        match = re.search(r"var\s+csrftoken_search\s*=\s*'([^']+)'", html)
        if not match:
            print("Could not find csrftoken_search in Ubuy HTML")
            return []
            
        csrf_token = match.group(1)
        
        # 2. Call the products AJAX API using the CSRF token
        requestData = {
            "q": query,
            "ctx": query,
            "node_id": "",
            "page": 1,
            "brand": "",
            "ufulfilled": "",
            "price_range": "",
            "sort_by": "",
            "lang": "",
            "dc": "",
            "search_type": "",
            "skus": "",
            "next_store": "usstore",
            "is_scrap": 1,
            "es_count": 0,
            "store": "us",
            "total_fetched": 0,
            "es_filter_status": "",
            "csrf_token": csrf_token
        }
        
        json_str = json.dumps(requestData)
        req_b64 = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        
        api_url = f"https://www.ubuy.com.pk/en/ubcommon/esglobal-v2/search/products?ubuy=es1&dtm=&is_app=&req={req_b64}"
        
        headers = {
            "Referer": url,
            "Accept": "text/html, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Cache-Control": "max-age=10"
        }
        
        resp = session.get(api_url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"Ubuy API failed with status {resp.status_code}")
            return []
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.select('.listing-product')
        if not items:
            items = soup.select('.product-card')
            
        for item in items[:20]:
            try:
                # Title
                title_elem = item.find('input', {'name': 'title'})
                if title_elem:
                    name = title_elem.get('value', '').replace('&amp;', '&').strip()
                else:
                    name_a = item.select_one('a[title]')
                    name = name_a.get('title', '').strip() if name_a else "No Name"
                    
                # Link
                link_elem = item.select_one('a[href]')
                link = link_elem.get('href', '') if link_elem else ""
                
                # Price (decomposing <del> old prices first to avoid concatenation)
                price_wrapper = item.select_one('.product-price') or item.select_one('.price')
                price_val = 0
                if price_wrapper:
                    import copy
                    price_wrapper_copy = copy.copy(price_wrapper)
                    for d in price_wrapper_copy.find_all('del'):
                        d.decompose()
                    price_val = clean_price(price_wrapper_copy.get_text())
                
                if not price_val:
                    continue
                    
                # Image
                img_elem = item.find('input', {'name': 'image'})
                if img_elem:
                    img_url = img_elem.get('value', '').strip()
                else:
                    img_tag = item.select_one('img')
                    img_url = img_tag.get('data-src') or img_tag.get('src') or ""
                    
                products.append({
                    "name": name,
                    "price": int(price_val),
                    "price_text": f"Rs. {int(price_val):,}",
                    "image": img_url,
                    "url": link,
                    "source": "Ubuy",
                    "best": False
                })
            except Exception as e:
                print(f"Ubuy item parse error: {e}")
                continue
                
        return products
    except Exception as e:
        print(f"Ubuy error: {e}")
        return []


# ==============================
# SHOPHIVE SCRAPER (Requests)
# ==============================
def scrape_shophive(query):
    """Scrape Shophive.com using global session for faster results."""
    url = f"https://www.shophive.com/catalogsearch/result/?q={query.replace(' ', '+')}"
    session = get_session()
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, 'html.parser')
        # More robust Shophive selectors
        items = soup.select('.product-item') or soup.select('.item.product.product-item') or soup.select('.products.list.items.product-items li')
        products = []
        for item in items[:20]:
            try:
                title_elem = item.select_one('.product-item-link') or item.select_one('.product-item-name a')
                if not title_elem: continue
                name = title_elem.text.strip()
                link = title_elem.get('href') if title_elem else ""
                
                price_elem = item.select_one('.price-container .price') or item.select_one('.price')
                # Improved price parsing for Shophive formatting
                price_text = price_elem.text if price_elem else "0"
                # If price is 'Rs. 174,999.00', we want '174999'
                price_val = clean_price(price_text.split('.')[0]) 
                if not price_val: continue
                
                img_url = get_image_url(item, base_url="https://www.shophive.com")
                # Debug print for Shophive image extraction
                # print(f"DEBUG: Shophive item: {name[:30]} | Image: {img_url}")
                
                products.append({
                    "name": name,
                    "price": price_val,
                    "price_text": f"Rs. {price_val:,}",
                    "image": img_url,
                    "url": link,
                    "source": "Shophive",
                    "best": False
                })
            except: continue
        return products
    except Exception as e:
        print(f"Shophive error: {e}")
        return []

