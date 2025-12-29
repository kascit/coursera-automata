#python
import time
import re

#my
from misc import *

#selenium
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Global variables
skip = False
retry = False
did_next = False
course_end = False
quiz_opened = False
questions_data = []

# Functions
def close_button(driver):
    close_variants = [
        "//button[span[contains(text(), 'Close')]]",  # Text-based
        "//button[contains(@class, 'c-close-mobile-nav')]",  # Class-based
        "//button[@aria-label='Close']"  # Aria-label
    ]

    for xpath in close_variants:
        try:
            close_btn = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            close_btn.click()
            print(f"❎ 'Close' button clicked.")
            return driver  # Exit after clicking
        except TimeoutException:
            pass  # Silently continue checking other buttons

    return driver  # No close button found, return without error



def should_skip(driver):
    """Checks if the course item should be skipped based on completion, participation, labs, apps, or failed status."""
    global skip
    wait = WebDriverWait(driver, 1 + iota())

    def check(xpath, msg, action=None):
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            print(f"✅ {msg}")
            if action: action(element)
            return True
        except TimeoutException:
            return False

    if check("//h3[contains(@aria-label, 'Reading completed') and text()='Completed']", "Item marked as completed. Skipping..."):
        skip = True
        return driver

    try:
        selected_item = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@aria-label, 'selected')]") ))
        should_skip_item = driver.execute_script(
            """
            let el = document.querySelector('[aria-label*="selected"]');
            if (!el) return false;

            let aria = el.getAttribute("aria-label") || "";
            let text = el.textContent || "";

            // Check if the item is explicitly "Completed", "peer", or "capstone"
            let isCompleted = /\b(Completed|peer|capstone)\b/i.test(aria);

            // Check if the item is "Failed" in aria-label OR text content
            let isFailed = /\bFailed\b/i.test(aria) || /\bFailed\b/i.test(text);

            // Check if a warning icon is present and visible
            let warning = el.querySelector('[data-testid="learn-item-warning-icon"]');
            let hasWarning = warning && window.getComputedStyle(warning).display !== "none";

            // Debugging logs for testing in browser
            console.log({
                aria, text, isCompleted, isFailed, hasWarning
            });

            // Return final condition
            return isCompleted && !isFailed && !hasWarning;

            """
        )
        if should_skip_item:
            print("✅ Item completed/failed with no warnings. Skipping...")
            skip = True
            return driver
    except TimeoutException:
        pass

    if check("//div[contains(@class, 'color-hint-text') and contains(@class, 'participation-text') and text()='Participation is optional']", "'Participation is optional'. Skipping..."):
        skip = True
        return driver

    if check("//button[contains(@data-track-component, 'ungraded_lab_item_page_launch_lab')]", "Lab detected. Skipping..."):
        skip = True
        return driver

    if check("//button[@aria-label='Launch app. Opens in new window']", "App detected. Launching...", "Lab detected. Skipping..."):
        skip = True
        return driver

    print("❌ No conditions met. Proceeding normally...")
    skip = False
    return driver


def video(driver):
    global skip
    wait = WebDriverWait(driver, iota() + 0.5)
    time.sleep(iota()+1)
    # Check if a video element is present
    video_exists = driver.execute_script("return document.querySelector('video') !== null")
    
    if video_exists:
        # Play the video
        driver.execute_script("""
            let video = document.querySelector('video');
            if (video) {
                video.muted = true;
                video.play();
                let duration = video.duration;
                setTimeout(() => {
                    video.currentTime = duration - 2;  // Seek to end after 500ms delay
                }, 2000);
            }
        """)
        time.sleep(iota()+5)
        print("✅ Video found and skipped to end.")
        skip = True
    else:
        print("❌ No video found on this page.")

    return driver

def mark_as_completed(driver, timeout=1, max_retries=2):
    global skip
    wait = WebDriverWait(driver, iota() + timeout)
    
    try:
        retries = 0
        while retries < max_retries:
            try:
                # Wait for the button to appear and be clickable
                complete_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='mark-complete']"))
                )

                # Click the button
                complete_button.click()
                print("✅ Marked as completed successfully.")
                skip = True
                return driver  # Exit function after successful click

            except StaleElementReferenceException:
                print(f"⚠️ Button became stale, retrying... ({retries + 1}/{max_retries})")
                retries += 1
            except TimeoutException:
                print("❌ No 'Mark as Completed' button found, skipping.")
                return driver  # Exit function if button isn't found within timeout

    except Exception as e:
        print(f"⚠️ Error marking as completed: {e}")

    return driver

def next_item(driver, timeout=5):
    global course_end
    try:
        wait = WebDriverWait(driver, iota() + timeout)
        
        # Wait for the button to be clickable
        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Next Item']")))
        next_button = wait.until(EC.any_of(
            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Next Item']")),
            EC.element_to_be_clickable((By.XPATH, "//a[span[contains(text(), 'Next item')]]"))
        ))
        # Click the button
        next_button.click()
        print("✅ 'Next Item' button clicked.")
        return driver  # Return driver if button is clicked successfully

    except TimeoutException:
        print("❌ 'Next Item' button not found or not clickable.")
        course_end = True
        return driver  # No tabs left, return None to stop loop

    except Exception as e:
        print(f"⚠️ Error while clicking 'Next Item': {e}")
        return driver  # Return None for any unexpected errors


def click_next_or_retry(driver):
    global retry, quiz_opened, questions_data, did_next
    """
    Tries to click the 'Retry', 'Edit', 'Continue', or 'Try again' button first.
    If none are found, attempts to click the 'Next' button.
    """
    wait = WebDriverWait(driver, 5)  # Adjusted wait time
    retry = False

    # Check for 'Retry', 'Edit', 'Continue', or 'Try again' buttons first
    # redo_buttons = driver.find_elements(By.XPATH, "//span[text()='Retry' or text()='Edit' or text()='Continue'] | //a[@role='button' and span[text()='Try again']]")
    # for button in redo_buttons:
    #     try:
    #         redo_button = wait.until(EC.element_to_be_clickable(button))
    #         driver.execute_script("arguments[0].scrollIntoView();", redo_button)
    #         time.sleep(1)  # Allow scrolling animation
    #         driver.execute_script("arguments[0].click();", redo_button)
    #         print(f"✅ Clicked '{redo_button.text}' button.")
    #         time.sleep(1.5)
    #         retry = True
    #         return driver  # Exit function after clicking a redo button
    #     except TimeoutException:
    #         print(f"ℹ️ '{button.text}' button not found or not clickable. Skipping...")

    # print("⚠️ No visible 'Retry' button found. Checking for 'Next' button...")
    
    # If no redo button was clicked, proceed to check for 'Next' button
    try:
        next_buttons = driver.find_elements(By.XPATH, "//a[span[contains(text(), 'Next')]] | //button[span[contains(text(), 'Next')]]")
        print(f"ℹ️ Found {len(next_buttons)} possible 'Next' buttons.")

        for next_button in next_buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", next_button)
                time.sleep(0.5)  # Allow time for scrolling
                wait.until(EC.element_to_be_clickable(next_button))
                driver.execute_script("arguments[0].click();", next_button)
                print("✅ Clicked 'Next' button.")
                time.sleep(1)
                quiz_opened = False
                did_next = True
                return driver  # Exit function after clicking 'Next'
            except Exception as e:
                print(f"⚠️ Could not click 'Next' button: {e}")

    except TimeoutException:
        print("ℹ️ 'Next' button not found or not clickable.")

    return driver



def open_grades_page(driver):
    """
    Opens the Grades page by clicking the 'Grades' tab.
    Returns the driver if successful, otherwise None.
    """
    try:
        # Click the 'Module' link if present
        driver.execute_script("""
            let moduleLink = Array.from(document.querySelectorAll('a[data-click-key]'))
                .find(a => a.textContent.trim().includes('Module'));
            if (moduleLink) moduleLink.click();
        """)
        time.sleep(2)  # Small delay to allow UI updates

        # Wait for 'Grades' tab to be visible & clickable
        wait = WebDriverWait(driver, 10)
        grades_tab = wait.until(EC.presence_of_element_located((By.XPATH, "//span[strong[text()='Grades']]")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", grades_tab)
        time.sleep(1)  # Allow time for scrolling

        # Attempt to click 'Grades' tab with a retry in case of StaleElementReferenceException
        for _ in range(3):  # Retry up to 3 times if needed
            try:
                grades_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[strong[text()='Grades']]")))
                driver.execute_script("arguments[0].click();", grades_tab)
                break  # Success, exit loop
            except StaleElementReferenceException:
                print("⚠️ Stale element detected, retrying...")
                time.sleep(2)  # Short wait before retrying


        # Wait for the grades page to fully load
        time.sleep(3)
        print("✅ Grades page opened successfully.")
        return driver

    except TimeoutException:
        print("❌ Error: Grades tab not found or took too long to load.")
    except Exception as e:
        print(f"❌ Error opening Grades page: {e}")

    return driver  # Return driver even if there's an error to allow further execution


def check_and_open_quiz(driver):
    """
    Checks quiz statuses and opens the first one that is not passed.
    Returns True if a quiz was opened, False if all are passed.
    """
    driver.refresh()  # Refresh the page to ensure updated content
    time.sleep(5)  # Allow time for page to load

    try:
        quizzes = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".rc-AssignmentsTableRowCds"))
        )
    except TimeoutException:
        print("❌ Error: No quizzes found or page took too long to load.")
        return False

    all_passed = True

    for _ in range(3):  # Retry logic in case of stale elements
        try:
            for quiz in quizzes:
                title_element = quiz.find_element(By.CSS_SELECTOR, ".item-column-text a")
                status_element = quiz.find_element(By.CSS_SELECTOR, ".status-column-text p")

                quiz_title = title_element.text.strip()
                quiz_link = title_element.get_attribute("href")
                quiz_status = status_element.text.strip()

                print(f"{quiz_title}: {quiz_status}")

                # If a quiz is not passed, open it and return
                if quiz_status.lower() != "passed":
                    print(f"Opening {quiz_title}...")
                    driver.get(quiz_link)
                    all_passed = False
                    return True  # A quiz was opened
            break  # Exit retry loop if successful
        except StaleElementReferenceException:
            print("⚠️ Stale element detected, retrying...")
            time.sleep(2)
            quizzes = driver.find_elements(By.CSS_SELECTOR, ".rc-AssignmentsTableRowCds")  # Refresh elements

    return not all_passed  # Return True if a quiz was opened, False if all are passed



def extract_questions_and_options_with_remark(driver):
    global questions_data
    questions_data = []

    question_blocks = driver.find_elements(By.XPATH, "//div[@data-testid='legend']")

    def clean_text(text):
        """Removes leading numbers and trims excess spaces"""
        return re.sub(r"^\d+\s*", "", text.strip(), flags=re.MULTILINE)

    def extract_multiple_question_part(question_text):
        """Extracts the last occurrence of 'select' or 'choose' and everything after it"""
        match = re.search(r".*\b(select|choose)\b(.*)", question_text, re.IGNORECASE)
        return match.group(1).capitalize() + " " + match.group(2).strip() if match else ""

    for question_block in question_blocks:
        try:
            elements = question_block.find_elements(By.XPATH, ".//p | .//pre | .//code | .//textarea")
            seen_text = set()
            question_text_parts = []

            for elem in elements:
                if elem.tag_name.lower() == "textarea":
                    text_content = elem.get_attribute("value") or ""
                else:
                    text_content = elem.text.strip()

                clean_content = clean_text(text_content)
                if clean_content and clean_content not in seen_text:
                    seen_text.add(clean_content)
                    question_text_parts.append(clean_content)

            question_text = " ".join(question_text_parts).strip()
        except Exception:
            question_text = "No question found"

        parent_div = question_block.find_element(By.XPATH, "./parent::div")
        test_id = parent_div.get_attribute("data-testid") or ""
        input_type = "Unknown"
        if "text" in test_id.lower():
            input_type = "Text input"
        elif "checkbox" in test_id.lower():
            input_type = "Multiple answers"
        elif "multiple" in test_id.lower():
            input_type = "Single answer only"

        if input_type == "Multiple answers":
            additional_question_part = extract_multiple_question_part(question_text)
            if additional_question_part:
                input_type += ": " + additional_question_part

        options = []
        answered = []
        try:
            option_elements = parent_div.find_elements(By.XPATH, ".//div[contains(@class, 'rc-Option')]")
            seen_options = set()
            for opt in option_elements:
                opt_text = clean_text(opt.text)
                if opt_text and opt_text not in question_text and opt_text.lower() != "point":
                    seen_options.add(opt_text)
                    options.append(opt_text)
                    try:
                        label_element = opt.find_element(By.XPATH, ".//label[contains(@class, 'cui-isChecked')]")
                        if label_element:
                            answered.append(opt_text)
                    except Exception:
                        pass
        except Exception:
            pass

        if input_type == "Text input":
            try:
                # Find input element using aria-labelledby containing "text-input" or type="text"
                text_input = parent_div.find_element(By.XPATH, ".//textarea | .//input[contains(@aria-labelledby, 'text-input') or @type='text']")
                answered_text = text_input.get_attribute("value") or ""
                answered = [answered_text.strip()] if answered_text.strip() else []
            except Exception:
                pass


        if options and options[0] in question_text:
            options.pop(0)
        options = [opt for opt in options if opt.strip()]

        remark = "Unknown"
        try:
            icon_element = parent_div.find_element(By.XPATH, ".//*[contains(@data-testid, 'icon-incorrect') or contains(@data-testid, 'icon-correct')]")
            if 'icon-incorrect' in icon_element.get_attribute("data-testid"):
                remark = "Incorrect"
            elif 'icon-correct' in icon_element.get_attribute("data-testid"):
                remark = "Correct"
        except Exception:
            pass

        questions_data.append({
            "question": question_text,
            "options": options if input_type != "Text input" else [],
            "input_type": input_type,
            "answered": answered,
            "remark": remark
        })

    return questions_data
