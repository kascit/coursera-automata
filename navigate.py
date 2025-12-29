
#python
import os
import time
import logging


#my
from misc import *



# selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException


# global shite
clicked_modules = set()




# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTABLE_CHROME_PATH = os.path.join(BASE_DIR, "chromium", "chrome.exe")
CHROMEDRIVER_PATH = os.path.join(BASE_DIR, "chromium", "chromedriver.exe")
PROFILE_PATH = os.path.join(BASE_DIR, "chrome-profile")

def get_driver(headless=False, mute=True, block_images=True):
    """Creates and returns a Chrome WebDriver with the specified settings."""
    options = Options()
    options.binary_location = PORTABLE_CHROME_PATH

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

    # Mute audio
    if mute:
        options.add_argument("--mute-audio")

    # Use the persistent user profile
    options.add_argument(f"--user-data-dir={PROFILE_PATH}")

    # Incognito mode
    
    # Disable images (Saves bandwidth)
    if block_images:
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

    # Disable SSL and Google API issues
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")

    # Additional performance optimizations
    options.add_argument("--no-sandbox")  # Prevents issues in certain environments
    options.add_argument("--disable-dev-shm-usage")  # Prevents memory crashes
    options.add_argument("--log-level=3")  # Suppresses unnecessary logs

    # Disable automation detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Disable geolocation and unwanted requests
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.automatic_downloads": 1,
    })

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    driver.maximize_window()
    return driver

def is_logged_in(driver, wait_time=240):
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

def mylearning_click(driver):
    """Clicks the 'My Learning' button and ensures the correct tab is selected."""
    wait = WebDriverWait(driver, iota() + 10)

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        for _ in range(3):
            try:
                # Click the 'My Learning' button
                my_learning_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@data-click-key, 'page_nav_link_my_learning')]")))
                driver.execute_script("arguments[0].click();", my_learning_btn)
                print("Clicked 'My Learning' button.")

                # Ensure the 'In Progress' tab is selected
                for _ in range(3):
                    try:
                        in_progress_tab = wait.until(EC.presence_of_element_located((By.XPATH, "//button[@data-e2e='my-learning-tab-in_progress']")))
                        aria_checked = in_progress_tab.get_attribute("aria-checked")

                        if aria_checked == "true":
                            print("'In Progress' tab is already selected.")
                            return driver
                        else:
                            driver.execute_script("arguments[0].click();", in_progress_tab)
                            print("Clicked 'In Progress' tab.")
                            time.sleep(iota()+2)  # Allow time for the change to take effect
                    except (StaleElementReferenceException, TimeoutException) as e:
                        print(f"Retrying 'In Progress' tab click due to: {e}")
                        time.sleep(iota()+2)

                print("Could not confirm 'In Progress' tab selection after multiple attempts.")
                return None

            except (StaleElementReferenceException, TimeoutException) as e:
                print(f"Retrying 'My Learning' button due to: {e}")
                time.sleep(iota()+2)

        print("Could not find 'My Learning' button after multiple attempts.")
        return None

    except Exception as e:
        print(f"Error clicking 'My Learning': {e}")
        return None

def has_incomplete_course(driver):
    """Returns True if there is at least one course with progress < 100%."""
    wait = WebDriverWait(driver, 5)  # Adjust wait time if necessary
    time.sleep(3 + iota())  # Allow page to load
    try:
        # Wait for progress elements to be present
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@data-testid='visually-hidden']")))

        # Find all progress elements
        progress_elements = driver.find_elements(By.XPATH, "//div[@data-testid='visually-hidden']")

        for elem in progress_elements:
            try:
                text = elem.text.strip().lower()  # Convert to lowercase for consistency
                if "progress bar" in text:
                    text = text.split(",")[1].strip().replace("%", "")  # Extract percentage
                    progress_value = int(text)

                    if progress_value < 100:
                        print(f"Found a course with progress: {progress_value}%")
                        return True

            except ValueError:
                print(f"Could not parse progress value: {elem.text}")

        print("No courses found with progress < 100%.")
        return False

    except Exception as e:
        print(f"Error checking course progress: {e}")
        return False

def course_select(driver):
    """Finds and clicks the course with the least progress."""
    wait = WebDriverWait(driver, 5)  # Adjust wait time if necessary

    try:
        time.sleep(3)  # Allow page to load

        # Wait for progress elements
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@data-testid='visually-hidden']")))
        progress_elements = driver.find_elements(By.XPATH, "//div[@data-testid='visually-hidden']")

        # Wait for course buttons
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[@aria-label and (contains(@aria-label, 'Resume') or contains(@aria-label, 'Go to course'))]")))
        course_buttons = driver.find_elements(By.XPATH, "//a[@aria-label and (contains(@aria-label, 'Resume') or contains(@aria-label, 'Go to course'))]")

        if not progress_elements or not course_buttons:
            print("No courses or progress elements found!")
            return None

        courses = []

        for progress_elem, course_btn in zip(progress_elements, course_buttons):
            try:
                text = progress_elem.text.strip().lower()
                if "progress bar" in text:
                    text = text.split(",")[1].strip().replace("%", "")
                    progress_value = int(text)
                    courses.append((progress_value, course_btn))
            except ValueError:
                print(f"Could not parse progress value: {progress_elem.text}")

        if not courses:
            print("No valid progress values found!")
            return None

        # Sort by progress value (ascending) and select the course with the least progress
        courses.sort(key=lambda x: x[0])
        least_progress_course = courses[0][1]

        driver.execute_script("arguments[0].click();", least_progress_course)
        print(f"Clicked course with least progress: {courses[0][0]}%")
        return driver

    except StaleElementReferenceException:
        print("Stale element encountered. Retrying...")
        time.sleep(2)
        return course_select(driver)  # Retry recursively

    except Exception as e:
        print(f"Error selecting course: {e}")
        return None

def burger_nav(driver):
    try:
        wait = WebDriverWait(driver, 5)  # Removed iota() since it's unclear

        button_xpath = "//button[@data-e2e='mobile-nav-icon']"
        button = wait.until(EC.presence_of_element_located((By.XPATH, button_xpath)))

        # Check the current state of aria-expanded
        is_expanded = button.get_attribute("aria-expanded")

        if is_expanded == "true":
            print("ℹ️ Mobile navigation is already expanded. No action needed.")
            return driver  # Return early to avoid unnecessary interaction

        # Ensure the button is clickable before interacting
        button = wait.until(EC.element_to_be_clickable((By.XPATH, button_xpath)))

        # Click using JavaScript execution
        driver.execute_script("arguments[0].click();", button)
        print("✅ Clicked mobile navigation button.")

        # Wait for aria-expanded to change to true
        wait.until(lambda d: button.get_attribute("aria-expanded") == "true")
        print("✅ Mobile navigation expanded.")

    except Exception as e:
        print("❌ Error:", str(e))

    return driver

def module(driver):
    global clicked_modules
    fucked = False
    """Finds and clicks the first available module that does NOT contain a checkmark SVG, avoiding previously clicked modules."""
    wait = WebDriverWait(driver, iota() + 10)

    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[@data-test='rc-WeekNavigationItem']")))
        old_url = driver.current_url

        while True:  # Loop to handle stale element issues
            try:
                modules = driver.find_elements(By.XPATH, "//a[@data-test='rc-WeekNavigationItem']")
                print(f"🔍 Found {len(modules)} modules.")

                for module in modules:  
                    try:
                        module_id = module.get_attribute("href") or module.get_attribute("aria-label")  # Use href if available
                        has_svg = bool(module.find_elements(By.TAG_NAME, "svg"))  # Check for checkmark

                        if not module_id:
                            continue  # Skip if no valid identifier

                        if module_id in clicked_modules:
                            fucked = True
                            print(f"⏭️ Skipping already clicked module: {module_id}")
                            continue  

                        print(f"🔹 Checking module: '{module_id}', Has Checkmark: {has_svg}")

                        if not has_svg:
                            try:
                                module.click()
                            except:
                                driver.execute_script("arguments[0].click();", module)  # Fallback JS click

                            print(f"✅ Clicked module: {module_id}")

                            # Wait for a URL change or a new page load
                            wait.until(lambda d: d.current_url != old_url or d.execute_script("return document.readyState") == "complete")
                            print(f"✅ Page loaded! New URL: {driver.current_url}")

                            clicked_modules.add(module_id)  # Store clicked module
                            if fucked:
                                fucked = False
                                return item(driver)
                            else:
                                return driver  # Exit after clicking the first valid module

                    except StaleElementReferenceException:
                        print("⚠️ Stale Element: The module list changed. Retrying...")
                        break  # Exit inner loop and re-fetch elements

                else:
                    print("❌ No clickable module found!")
                    return driver  # Exit if no valid module is found

            except TimeoutException:
                print(f"⚠️ Timeout: The page did not load after clicking.")
                return driver

            except Exception as e:
                print(f"❌ Unexpected Error: {e}")
                return driver

    except Exception as e:
        print(f"❌ Critical Error: {e}")

    return driver

def item(driver):
    wait = WebDriverWait(driver, 10)
    print("🔍 Locating available items...")

    while True:
        try:
            items = wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//a[@data-click-key='open_course_home.period_page.click.item_link']")
            ))
            print(f"📌 Found {len(items)} items.")

            for index in range(1, len(items) + 1):
                try:
                    item = wait.until(EC.presence_of_element_located(
                        (By.XPATH, f"(//a[@data-click-key='open_course_home.period_page.click.item_link'])[{index}]")
                    ))

                    # Locate the parent div text content
                    parent_div = wait.until(EC.presence_of_element_located(
                        (By.XPATH, f"(//div[contains(@class, 'rc-WeekSingleItemDisplayRefresh')])[{index}]")
                    ))

                    # ✅ Get the full text content
                    parent_text = driver.execute_script("return arguments[0].textContent.trim();", parent_div)

                    # ✅ Check for completion, warnings, and failed status using JavaScript
                    should_skip = driver.execute_script("""
                        function shouldSkipItem(element) {
                            let ariaLabel = element.getAttribute("aria-label") || "";
                            let textContent = element.textContent || "";
                            let isCompleted = /Completed|peer|capstone|Reading completed|Discussion Prompt/i.test(ariaLabel + textContent);
                            let isFailed = /Failed/i.test(textContent);  // Check for failed status

                            let warningIcon = element.querySelector('[data-testid="learn-item-warning-icon"]');
                            let isWarningVisible = warningIcon && warningIcon.offsetParent !== null;

                            return (isCompleted && !isWarningVisible && !isFailed);  // Skip only if fully completed, no warning, and not failed
                        }
                        return shouldSkipItem(arguments[0]);
                    """, parent_div)



                    # ✅ Skip if completed, has no warning, or has failed status
                    if should_skip:
                        print(f"💬 Skipping item {index} ({parent_text})")
                        continue

                    # Click the item
                    try:
                        wait.until(EC.element_to_be_clickable((By.XPATH, f"(//a[@data-click-key='open_course_home.period_page.click.item_link'])[{index}]"))).click()
                    except:
                        driver.execute_script("arguments[0].click();", item)

                    print(f"🎯 Clicked item {index}: {parent_text}")
                    return driver

                except (StaleElementReferenceException, TimeoutException):
                    print(f"⚠️ Issue detected with item {index}, retrying...")
                    continue  

            print("❌ No valid incomplete items found.")
            return module(driver)

        except Exception as e:
            print(f"❌ Error: {e}")
            return driver
