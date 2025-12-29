import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTABLE_CHROME_PATH = os.path.join(BASE_DIR, "chromium", "chrome.exe")
CHROMEDRIVER_PATH = os.path.join(BASE_DIR, "chromium", "chromedriver.exe")
PROFILE_PATH = os.path.join(BASE_DIR, "chrome-profile")

def get_driver(headless=False):
    """Creates and returns a Chrome WebDriver with the specified settings."""
    options = Options()
    options.binary_location = PORTABLE_CHROME_PATH

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")

    # Use the persistent user profile
    options.add_argument(f"--user-data-dir={PROFILE_PATH}")

    # Disable SSL and Google API issues
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")

    # Disable geolocation and unwanted requests
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "profile.managed_default_content_settings.images": 1,
    })

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    driver.maximize_window()
    return driver

def is_logged_in(driver, wait_time=60):
    """Checks if the user is logged in to Coursera."""
    wait = WebDriverWait(driver, wait_time)
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@data-click-key, 'page_nav_link_my_learning')]")))
        logging.info("Login detected! Proceeding with automation.")
        return True
    except TimeoutException:
        logging.warning("Login timeout! Please ensure you log in within the time limit.")
        return False

def open_and_login():
    """Opens Coursera, waits for manual login, and saves the session for future automation."""
    driver = get_driver(headless=False)  # Start in normal mode
    driver.get("https://www.coursera.org")
    logging.info("Opened Coursera. Please log in manually.")

    if is_logged_in(driver):
        logging.info("Login successful. Saving session for future runs.")
    else:
        logging.error("Login failed. Exiting.")
        driver.quit()
        return None

    return driver  # Return driver for further automation

def main():
    """Main execution function."""
    driver = open_and_login()
    if driver:
        logging.info("Session active. Ready for automation.")
        # Add your automation tasks here
        driver.quit()

if __name__ == "__main__":
    main()
