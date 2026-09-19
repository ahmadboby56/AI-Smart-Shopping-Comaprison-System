import time
import os
from playwright.sync_api import sync_playwright

def record_demonstration():
    video_folder = os.path.abspath("demo_video")
    os.makedirs(video_folder, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            record_video_dir=video_folder,
            record_video_size={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        
        print("1. Opening Admin Login & Authenticating...")
        page.goto("http://127.0.0.1:5001/admin-login")
        page.wait_for_timeout(500)
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", "password123")
        page.click("button[type='submit']")
        page.wait_for_timeout(1000)
        
        print("2. Opening Search Engine with Query 'iPhone 15'...")
        page.goto("http://127.0.0.1:5001/dashboard?q=iPhone+15")
        page.wait_for_timeout(4000)
        
        # Scroll down to reveal product cards, price comparison, & NLP trust badges
        page.mouse.wheel(0, 450)
        page.wait_for_timeout(3500)
        
        print("3. Navigating to Admin Control & Revenue Dashboard...")
        page.goto("http://127.0.0.1:5001/admin")
        page.wait_for_timeout(4000)
        
        # Scroll down in admin panel to show affiliate click logs & search volume chart
        page.mouse.wheel(0, 450)
        page.wait_for_timeout(3500)
        
        print("4. Finalizing recording...")
        context.close()
        browser.close()
        
        video_files = [f for f in os.listdir(video_folder) if f.endswith('.webm')]
        if video_files:
            src_file = os.path.join(video_folder, video_files[0])
            dest_file = os.path.abspath("smart_shopping_demo_video.webm")
            if os.path.exists(dest_file):
                os.remove(dest_file)
            os.rename(src_file, dest_file)
            print(f"SUCCESS: Video recorded and saved at {dest_file}, size: {os.path.getsize(dest_file)} bytes")
        else:
            print("ERROR: No webm file generated")

if __name__ == '__main__':
    record_demonstration()
