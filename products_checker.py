"""
Zara Product Availability Checker

This script monitors Zara products for availability and sends notifications
via Telegram when products become available.
"""

import requests
from bs4 import BeautifulSoup
import time
from typing import Dict, Set
import subprocess
import sys

# === CONFIG ===
PRODUCTS: Dict[str, str] = {
    "Z1975 Balloon Denim Jumpsuit": "https://www.zara.com/ro/en/z1975-balloon-denim-jumpsuit-p01879228.html?v1=410575325",
    "Ages 6‑14 Merino Wool Pyjamas": "https://www.zara.com/ro/en/ages-6-14---merino-wool-pyjamas-p05644694.html?v1=410590544",
    "Waxed Jacket with Contrast Collar": "https://www.zara.com/ro/en/waxed-jacket-with-contrast-collar-p04341750.html?v1=450412290",
    "Interlock Contrast Dress": "https://www.zara.com/ro/en/interlock-contrast-dress-p03641319.html?v1=423726533",
    "Down Jacket – Ski Collection": "https://www.zara.com/ro/en/down-jacket-water-resistant-and-wind-protection-recco--technology-ski-collection-p08073077.html?v1=410569861",
    "Flare Trousers – Ski Collection": "https://www.zara.com/ro/en/flare-trousers-water-resistant-and-wind-protection-recco--technology-ski-collection-p08073082.html?v1=422752710",
}

# === Telegram Bot Config ===
BOT_TOKEN = "7946217242:AAGmI0FTaE1-eyNZaI80_OYKVE0emabDT5A"
CHAT_ID = "7103134233"  # Replace this with your real chat ID
CHECK_INTERVAL = 30  # seconds (30 seconds instead of 60)

# Keywords that indicate product availability
AVAILABILITY_KEYWORDS = [
    "add to basket",
    "add to cart",
    "add",  # catches generic 'Add' button
    "put it in your basket",
    "add to bag",
    "add to wishlist",
    "buy now",
    "purchase",
    "order now",
    "add to shopping bag",
    "add to shopping cart",
]


def check_with_selenium(url: str) -> bool:
    """
    Alternative method using Selenium to handle dynamic content and anti-bot protection.
    Requires selenium and webdriver to be installed.
    """
    try:
        # Try to import selenium
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        print("🌐 Using Selenium to check page...")
        
        # Setup Chrome options - simpler approach
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            print("🚀 Loading page...")
            driver.set_page_load_timeout(20)  # 20 second timeout
            driver.get(url)
            
            print("⏳ Waiting for page to load...")
            time.sleep(5)  # Wait for JavaScript to load content
            
            # Look for actual "add" buttons with Selenium first
            print("🔍 Searching for 'add' buttons with Selenium...")
            buttons = driver.find_elements(By.TAG_NAME, "button")
            add_buttons = []
            
            for button in buttons:
                try:
                    button_text = button.text.lower().strip()
                    if "add" in button_text:
                        add_buttons.append(button.text.strip())
                        print(f"✅ Found button with 'add': '{button.text.strip()}'")
                except:
                    continue
            
            # Also check for links with "add"
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    link_text = link.text.lower().strip()
                    if "add" in link_text:
                        add_buttons.append(link.text.strip())
                        print(f"✅ Found link with 'add': '{link.text.strip()}'")
                except:
                    continue
            
            if add_buttons:
                print(f"🎉 Found {len(add_buttons)} elements with 'add': {add_buttons}")
                return True
            
            # Get page source for text analysis
            page_source = driver.page_source
            page_text = page_source.lower()
            
            print(f"📄 Page loaded successfully!")
            print(f"📏 Page length: {len(page_text)} characters")
            
            # Check for availability keywords in page text (be more strict)
            availability_keywords = [
                "add to basket",
                "add to cart", 
                "add to bag"
            ]
            
            found_keywords = []
            for keyword in availability_keywords:
                if keyword in page_text:
                    found_keywords.append(keyword)
                    print(f"✅ Found availability keyword: '{keyword}'")
            
            # Only return True if we found specific availability keywords
            if found_keywords:
                print(f"🎉 Found {len(found_keywords)} availability keywords: {found_keywords}")
                return True
            
            # Check for out of stock indicators (but avoid CSS comments)
            out_of_stock_indicators = [
                "out of stock", 
                "sold out", 
                "unavailable", 
                "not available", 
                "currently unavailable",
                "temporarily unavailable",
                "no longer available",
                "product not available",
                "item not available"
            ]
            
            for indicator in out_of_stock_indicators:
                if indicator in page_text:
                    # Show context around the indicator
                    indicator_pos = page_text.find(indicator)
                    context_start = max(0, indicator_pos - 100)
                    context_end = min(len(page_text), indicator_pos + 100)
                    context = page_text[context_start:context_end]
                    print(f"❌ Found out of stock indicator: '{indicator}'")
                    print(f"🔍 Context: {context}")
                    
                    # Only consider it out of stock if it's not in CSS comments
                    if "/*" not in context and "*/" not in context:
                        return False
                    else:
                        print("⚠️ Ignoring 'out of stock' found in CSS comments")
            
            print("❌ No 'add' buttons or availability indicators found")
            return False
            
        finally:
            driver.quit()
            
    except ImportError:
        print("⚠️ Selenium not available. Install with: pip install selenium")
        return False
    except Exception as e:
        print(f"⚠️ Selenium error: {e}")
        return False


def is_product_available(url: str) -> bool:
    """
    Check if a product is available on the given URL.
    
    Args:
        url: The product URL to check
        
    Returns:
        bool: True if product is available, False otherwise
    """
    # More realistic headers to avoid bot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=8)  # Reduced timeout
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text().lower()
        
        # Debug: Print a snippet of the page text to see what's available
        print(f"🔍 Checking page content for: {url[:50]}...")
        print(f"📄 Page text snippet: {page_text[:200]}...")
        print(f"📊 Response status: {response.status_code}")
        print(f"📏 Content length: {len(response.text)}")
        
        # Check if page is blocked or empty (common with anti-bot protection)
        if len(page_text.strip()) < 100:
            print("⚠️ Page appears to be blocked or empty (anti-bot protection?)")
            print("🔄 Trying Selenium as alternative...")
            return check_with_selenium(url)
        
        # Method 1: Check for availability keywords in page text
        found_keywords = []
        for keyword in AVAILABILITY_KEYWORDS:
            if keyword in page_text:
                found_keywords.append(keyword)
        
        if found_keywords:
            print(f"✅ Found availability keywords in text: {found_keywords}")
            return True
        
        # Method 2: Check for buttons with add-related text
        buttons = soup.find_all('button')
        for button in buttons:
            button_text = button.get_text().strip().lower()
            if any(keyword in button_text for keyword in AVAILABILITY_KEYWORDS):
                print(f"✅ Found add button: '{button.get_text().strip()}'")
                return True
        
        # Method 3: Check for links with add-related text
        links = soup.find_all('a')
        for link in links:
            link_text = link.get_text().strip().lower()
            if any(keyword in link_text for keyword in AVAILABILITY_KEYWORDS):
                print(f"✅ Found add link: '{link.get_text().strip()}'")
                return True
        
        # Method 4: Check for common button selectors
        common_selectors = [
            'button[class*="add"]',
            'button[class*="cart"]',
            'button[class*="basket"]',
            'a[class*="add"]',
            'a[class*="cart"]',
            'a[class*="basket"]',
            '[data-testid*="add"]',
            '[data-testid*="cart"]',
            '[aria-label*="add"]',
            '[aria-label*="cart"]'
        ]
        
        for selector in common_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"✅ Found element with selector '{selector}': '{elements[0].get_text().strip()}'")
                return True
        
        # Method 5: Check for "out of stock" indicators (if not found, might be available)
        out_of_stock_indicators = [
            "out of stock",
            "sold out",
            "unavailable",
            "not available",
            "currently unavailable"
        ]
        
        for indicator in out_of_stock_indicators:
            if indicator in page_text:
                print(f"❌ Found out of stock indicator: '{indicator}'")
                return False
        
        print(f"❌ No availability indicators found")
        return False
        
    except Exception as e:
        print(f"⚠️ Error fetching {url[:50]}...: {e}")
        return False


def send_telegram_message(message: str) -> None:
    """
    Send a message via Telegram bot.
    
    Args:
        message: The message to send
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    
    try:
        response = requests.post(url, data=payload)
        print("Telegram response:", response.text)  # DEBUG LINE
        
        if response.status_code != 200:
            print(f"❌ Failed to send Telegram message: {response.text}")
            
    except Exception as e:
        print(f"❌ Telegram error: {e}")


def monitor() -> None:
    """
    Main monitoring function that continuously checks product availability.
    """
    print("📦 Zara stock monitor started... checking every 30 seconds")
    print(f"🔍 Monitoring {len(PRODUCTS)} products...")
    notified: Set[str] = set()
    
    while True:
        print(f"\n⏰ Starting new check cycle at {time.strftime('%H:%M:%S')}")
        for i, (name, url) in enumerate(PRODUCTS.items(), 1):
            if name in notified:
                print(f"⏭️  Skipping {name} (already notified)")
                continue
                
            try:
                print(f"\n🔍 Checking ({i}/{len(PRODUCTS)}): {name}")
                if is_product_available(url):
                    msg = f"✅ *{name}* is now available!\n{url}"
                    send_telegram_message(msg)
                    print(f"✅ Available: {name} — Telegram sent")
                    notified.add(name)
                else:
                    print(f"❌ Not available yet: {name}")
                    
            except Exception as e:
                print(f"⚠️ Error checking {name}: {e}")
                
        print(f"\n⏳ Waiting {CHECK_INTERVAL} seconds until next check...")
        time.sleep(CHECK_INTERVAL)


def test_specific_url(url: str) -> None:
    """
    Test function to debug a specific URL and see what content is available.
    
    Args:
        url: The URL to test
    """
    print(f"🧪 Testing URL: {url}")
    print("=" * 50)
    
    # More realistic headers to avoid bot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📏 Content length: {len(response.text)}")
        print(f"📄 Full page text (first 500 chars):")
        print(page_text[:500])
        print("\n" + "=" * 50)
        
        # Check if page is blocked
        if len(page_text.strip()) < 100:
            print("⚠️ WARNING: Page appears to be blocked or empty!")
            print("This might be due to anti-bot protection.")
            print("🔄 Trying Selenium as alternative...")
            
            # Try Selenium
            selenium_result = check_with_selenium(url)
            if selenium_result:
                print("✅ Selenium found the page content!")
            else:
                print("❌ Selenium also failed to get content")
            return
        
        # Specifically look for "Add" buttons
        print("🔍 Searching for 'Add' buttons specifically:")
        
        # Method 1: Find buttons with "Add" text
        add_buttons = []
        buttons = soup.find_all('button')
        for button in buttons:
            button_text = button.get_text().strip()
            if 'add' in button_text.lower():
                add_buttons.append({
                    'text': button_text,
                    'html': str(button)[:200]  # First 200 chars of HTML
                })
        
        if add_buttons:
            print(f"✅ Found {len(add_buttons)} buttons with 'add' text:")
            for i, btn in enumerate(add_buttons):
                print(f"  Button {i+1}: '{btn['text']}'")
                print(f"  HTML: {btn['html']}")
        else:
            print("❌ No buttons with 'add' text found")
        
        # Method 2: Find any element with "Add" text
        print("\n🔍 Searching for ANY element with 'Add' text:")
        add_elements = []
        for element in soup.find_all(string=True):
            if 'add' in element.lower():
                parent = element.parent
                add_elements.append({
                    'text': element.strip(),
                    'tag': parent.name,
                    'html': str(parent)[:200]
                })
        
        if add_elements:
            print(f"✅ Found {len(add_elements)} elements with 'add' text:")
            for i, elem in enumerate(add_elements[:5]):  # Show first 5
                print(f"  Element {i+1}: '{elem['text']}' (tag: {elem['tag']})")
                print(f"  HTML: {elem['html']}")
        else:
            print("❌ No elements with 'add' text found")
        
        # Method 3: Look for common button classes/IDs
        print("\n🔍 Searching for common button patterns:")
        common_selectors = [
            'button[class*="add"]',
            'button[class*="cart"]',
            'button[class*="basket"]',
            'a[class*="add"]',
            'a[class*="cart"]',
            'a[class*="basket"]',
            '[data-testid*="add"]',
            '[data-testid*="cart"]',
            '[aria-label*="add"]',
            '[aria-label*="cart"]'
        ]
        
        for selector in common_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"✅ Found {len(elements)} elements with selector '{selector}':")
                for elem in elements[:3]:  # Show first 3
                    print(f"  Text: '{elem.get_text().strip()}'")
                    print(f"  HTML: {str(elem)[:150]}")
        
        # Method 4: Check for JavaScript variables or data attributes
        print("\n🔍 Checking for JavaScript data:")
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'add' in script.string.lower():
                print("✅ Found 'add' in JavaScript:")
                print(script.string[:300])
        
    except Exception as e:
        print(f"⚠️ Error testing URL: {e}")


if __name__ == "__main__":
    import sys
    
    # Check if we want to test or monitor
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test with cargo vest which is known to be in stock
        test_specific_url("https://www.zara.com/ro/en/cargo-waistcoat-with-linen-p08150433.html?v1=457154920")
    elif len(sys.argv) > 1 and sys.argv[1] == "test-out":
        # Test with a product that's out of stock
        test_specific_url("https://www.zara.com/ro/en/z1975-balloon-denim-jumpsuit-p01879228.html?v1=410575325")
    elif len(sys.argv) > 1 and sys.argv[1] == "test-other":
        # Test with another product
        test_specific_url("https://www.zara.com/ro/en/ages-6-14---merino-wool-pyjamas-p05644694.html?v1=410590544")
    elif len(sys.argv) > 1 and sys.argv[1] == "fast":
        # Fast mode - shorter intervals
        CHECK_INTERVAL = 15  # 15 seconds
        print("🚀 Fast mode enabled - checking every 15 seconds")
        send_telegram_message("🚀 Fast mode Zara bot started!")
        monitor()
    else:
        # Send test message
        send_telegram_message("🚀 Test message from Zara bot!")
        
        # Start monitoring
        monitor()


