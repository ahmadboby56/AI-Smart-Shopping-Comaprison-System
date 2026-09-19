import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

def seed_data():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Clear existing featured products to avoid duplicates during re-seeding
    conn.execute("DELETE FROM featured_products")
    
    # 2. Seed Premium Featured Products
    featured = [
        ("Apple iPhone 15 Pro Max (256GB)", 585000, "/static/images/featured/iphone.png", "Premium Store", "https://www.apple.com/iphone-15-pro/"),
        ("Samsung Galaxy S24 Ultra AI", 399999, "/static/images/featured/samsung.png", "Premium Store", "https://www.samsung.com/galaxy-s24-ultra/"),
        ("Apple MacBook Air M3 Chip 2024", 345000, "/static/images/featured/macbook.png", "Premium Store", "https://www.apple.com/macbook-air/"),
        ("Sony WH-1000XM5 Wireless Headphones", 95000, "/static/images/featured/sony.png", "Premium Audio", "https://www.sony.com/electronics/headphones/wh-1000xm5")
    ]
    
    conn.executemany("INSERT INTO featured_products (name, price, image, source, url) VALUES (?, ?, ?, ?, ?)", featured)
    
    # 3. Seed Price History for Trends (iPhone 15 Pro example)
    history = [
        ("Apple iPhone 15 Pro Max (256GB)", "Telemart", 595000, "2026-06-18 10:00:00"),
        ("Apple iPhone 15 Pro Max (256GB)", "Telemart", 592000, "2026-06-19 11:00:00"),
        ("Apple iPhone 15 Pro Max (256GB)", "Telemart", 590000, "2026-06-20 12:00:00"),
        ("Apple iPhone 15 Pro Max (256GB)", "Telemart", 588000, "2026-06-21 09:00:00"),
        ("Apple iPhone 15 Pro Max (256GB)", "Telemart", 587000, "2026-06-22 14:00:00"),
        ("Apple iPhone 15 Pro Max (256GB)", "Telemart", 585000, "2026-06-23 16:00:00"),
        ("Apple iPhone 15 Pro Max (256GB)", "Telemart", 585000, "2026-06-24 18:00:00")
    ]
    
    conn.execute("DELETE FROM price_history WHERE product_name = 'Apple iPhone 15 Pro Max (256GB)'")
    conn.executemany("INSERT INTO price_history (product_name, source, price, timestamp) VALUES (?, ?, ?, ?)", history)
    
    conn.commit()
    print(f"Successfully seeded {len(featured)} featured products and {len(history)} price history entries.")
    conn.close()

if __name__ == "__main__":
    seed_data()
