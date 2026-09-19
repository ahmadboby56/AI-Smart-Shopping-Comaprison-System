
import os
import sys

# Add project dir to path
project_dir = r"c:\Users\Administrator\Desktop\Smart Shopping final project\Smart Shopping"
sys.path.append(project_dir)

print("--- Testing Module Imports ---")
try:
    import nlp_engine
    print("[SUCCESS] nlp_engine imported")
except ImportError as e:
    print(f"[FAIL] nlp_engine: {e}")

try:
    import scraper
    print("[SUCCESS] scraper imported")
except ImportError as e:
    print(f"[FAIL] scraper: {e}")

try:
    from app import app
    print("[SUCCESS] app (Flask) imported")
except ImportError as e:
    print(f"[FAIL] app: {e}")

print("\n--- Checking Static Assets ---")
images_dir = os.path.join(project_dir, "static", "images")
if os.path.exists(images_dir):
    images = os.listdir(images_dir)
    print(f"Found {len(images)} images in static/images: {images}")
    if "vision.png" in images:
        print("[SUCCESS] vision.png exists")
    else:
        print("[WARNING] vision.png missing from static/images")
else:
    print("[FAIL] static/images directory not found")

print("\n--- Checking Database ---")
users_db_path = os.path.join(project_dir, "users.db")
if os.path.exists(users_db_path):
    print(f"[SUCCESS] users.db exists ({os.path.getsize(users_db_path)} bytes)")
else:
    print("[FAIL] users.db missing")

print("\n--- Checking Visual Search Endpoint ---")
# Check if /api/visual_search is in app.url_map
with app.app_context():
    routes = [str(p) for p in app.url_map.iter_rules()]
    if "/api/visual_search" in routes:
        print("[SUCCESS] /api/visual_search route exists")
    else:
        print("[FAIL] /api/visual_search route NOT found in app")

print("\n--- Verification Complete ---")
