import random
import time

def iota(n = 1):
    """Returns a random float between 0.00 and n, rounded to 2 decimal places."""
    return round(random.uniform(0, n), 2)

def scroll_randomly(driver, max_scroll=500):
    """Scrolls down by a random amount between 0 and max_scroll pixels."""
    scroll_amount = iota(max_scroll)
    
    driver.execute_script(f"window.scrollBy(0, {scroll_amount});")  # Scroll down
    print(f"📜 Scrolled down by {scroll_amount} pixels.")
    
    time.sleep(0.5)  # Small delay for smooth scrolling

    return driver
