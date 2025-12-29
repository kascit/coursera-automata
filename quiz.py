import json
import re
import openai
from google import genai
from misc import *
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
import course


def quiz_open(driver):
    vamp = False
    course.quiz_opened = False  # Ensure it's set properly
    wait = WebDriverWait(driver, iota() + 1)

    try:
        main_content = wait.until(EC.presence_of_element_located((By.ID, "main")))

        if any(word in main_content.text.lower() for word in ["assignment", "grade", "attempts"]) and any(term in driver.current_url.lower() for term in ["quiz", "assignment", "exam"]):
            print("Assignment page detected.")

            # Try finding the Start button (optional)
            try:
                start_button = wait.until(EC.element_to_be_clickable((
                    By.XPATH, "//button[.//span[contains(translate(text(), 'START', 'start'), 'start') or contains(translate(text(), 'RESUME', 'resume'), 'resume') or contains(translate(text(), 'RETRY', 'retry'), 'retry') or contains(translate(text(), 'EDIT', 'edit'), 'edit')]]"
                )))
                driver.execute_script("arguments[0].click();", start_button)
                print("✅ Start button clicked.")
                vamp = True
                time.sleep(2)
            except TimeoutException:
                print("⚠️ Start button not found. Moving on...")

            # Try "Continue" button
            try:
                cont_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Continue']")))
                cont_button.click()
                print("✅ Clicked the 'Continue' button!")
                vamp = True
                time.sleep(2)
            except TimeoutException:
                print("⚠️ 'Continue' button not found. Skipping...")

            # Try "Try again" button
            try:
                try_again_button = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[@role='button' and span[text()='Try again']]")))
                try_again_button.click()
                print("✅ Clicked the 'Try again' button!")
                vamp = True
                time.sleep(2)
            except TimeoutException:
                print("⚠️ 'Try again' button not found. Skipping...")

            time.sleep(3)
            if vamp:
                course.quiz_opened = True
                vamp = False
                print("📝 Quiz opened successfully.")
                return driver

        else:
            print("❌ Quiz page not found.")
    except Exception as e:
        print("⚠️ An error occurred:", e)
    return driver




def normalize_question(text):
    """Normalize question text to improve matching."""
    return re.sub(r'[^a-zA-Z0-9 ]+', '', text).strip().lower()

def extract_question_text(question_block):
    """Extracts all text content inside the legend div, including deeply nested elements."""
    try:
        text_content = question_block.get_attribute("textContent").strip()
        text_content = re.sub(r"^\d+\.*\s*Question\s*\d+\s*", "", text_content, flags=re.IGNORECASE).strip()
        text_content = re.sub(r"^\W+|\W+$", "", text_content)
        return text_content if text_content else "No question found"
    except Exception:
        return "No question found"

def extract_questions_and_options(driver):
    if not course.retry:
        course.questions_data = []

    question_blocks = driver.find_elements(By.XPATH, "//div[@data-testid='legend']")

    for question_block in question_blocks:
        question_text = extract_question_text(question_block)
        parent_div = question_block.find_element(By.XPATH, "./..")

        # Updated XPath to include rich-text inputs
        input_elements = parent_div.find_elements(By.XPATH, """
            .//input | 
            .//textarea | 
            .//div[@contenteditable='true']
        """)

        input_type = "Unknown"
        textarea_value = ""

        for element in input_elements:
            element_type = element.get_attribute("type")

            if element_type == "radio":
                input_type = "Single answer"
                break
            elif element_type == "checkbox":
                input_type = "Multiple answers"
                break
            elif element.tag_name.lower() == "textarea":
                input_type = "Text input"
                textarea_value = element.get_attribute("value").strip() if element.get_attribute("value") else ""
            elif element.get_attribute("contenteditable") == "true":
                input_type = "Text input"
                textarea_value = element.text.strip()  # Extract inner text


        options = []
        try:
            option_elements = parent_div.find_elements(By.XPATH, ".//div[contains(@class, 'rc-Option')]//div[@data-testid='cml-viewer']")
            seen_options = set()
            for opt in option_elements:
                opt_text = opt.text.strip()
                if opt_text and opt_text not in seen_options:
                    seen_options.add(opt_text)
                    options.append(opt_text)
        except Exception:
            pass

        if input_type == "Text input" and textarea_value:
            options.append(textarea_value)

        course.questions_data.append({
            "question": normalize_question(question_text),
            "options": options if input_type in ["Single answer", "Multiple answers", "Text input"] else [],
            "input_type": input_type
        })
    
    return course.questions_data

def select_answers(driver, question_data, ai_response):
    try:
        ai_answers = ai_response.get("answers", [])
        if not isinstance(ai_answers, list):
            print(f"⚠️ Unexpected AI response format: {ai_answers}")
            return

        # Normalize AI answers and map to extracted questions
        question_answer_map = {
            normalize_question(q["question"]): ans for q, ans in zip(question_data, ai_answers)
        }

        # Log AI response mapping
        for key, value in question_answer_map.items():
            print(f"🟢 Normalized Question: '{key}' → {value}")

        # Iterate over each question block in the UI
        for index, question_block in enumerate(driver.find_elements(By.XPATH, "//div[@data-testid='legend']")):
            try:
                # Use the extract_question_text function for consistency
                extracted_text = extract_question_text(question_block)
                question_text = normalize_question(extracted_text)

                print(f"🔍 Extracted Question (Raw): '{extracted_text}'")
                print(f"🔍 Extracted Question (Normalized): '{question_text}'")

                if question_text not in question_answer_map:
                    print(f"⚠️ No AI answer found for: '{question_text}'")
                    print(f"🔍 Available Keys: {list(question_answer_map.keys())}")  # Show all extracted questions
                    continue

                answer = question_answer_map[question_text]
                parent_div = question_block.find_element(By.XPATH, "./parent::div")

                # Identify input elements
                try:
                    input_group = parent_div.find_element(By.XPATH, ".//div[@role='radiogroup' or @role='group']")
                    group_role = input_group.get_attribute("role")
                except:
                    group_role = None  

                options_elements = parent_div.find_elements(By.XPATH, ".//label")
                text_input_elements = parent_div.find_elements(By.XPATH, """
                    .//div[contains(@data-testid, 'legend')]/following-sibling::div//textarea |
                    .//div[contains(@data-testid, 'legend')]/following-sibling::div//input[@type='text'] |
                    .//div[contains(@data-testid, 'legend')]/following-sibling::div//div[@contenteditable='true']
                """)

                # Handle text input questions
                if text_input_elements:
                    ai_text_answer = answer if isinstance(answer, str) else " ".join(answer)
                    text_input_elements[0].clear()
                    text_input_elements[0].send_keys(ai_text_answer)
                    continue

                # Normalize AI answer(s) for comparison
                answer_texts = [answer.strip().lower()] if isinstance(answer, str) else [a.strip().lower() for a in answer]
                selected = False

                for option_element in options_elements:
                    option_text = option_element.text.strip().lower()

                    # Allow partial matching as a fallback
                    for answer_text in answer_texts:
                        if answer_text in option_text or option_text in answer_text:
                            checkbox = option_element.find_element(By.TAG_NAME, "input")
                            driver.execute_script("arguments[0].click();", checkbox)
                            time.sleep(0.5)
                            selected = True
                            break  # Stop checking after selecting

                # If no match was found, pick the first option as a fallback
                if not selected and options_elements:
                    print(f"⚠️ No exact match found for '{question_text}', selecting first option as fallback.")
                    driver.execute_script("arguments[0].click();", options_elements[0].find_element(By.TAG_NAME, "input"))
                    time.sleep(0.5)

            except Exception as e:
                print(f"❌ Error selecting answer for question {index}: {e}")

    except Exception as e:
        print(f"❌ Fatal error in select_answers: {e}")


def solve_quiz(driver):
    print("🔍 Attempting to solve quiz...")
    course.questions_data
    """Extracts questions, gets AI answers, and selects correct options."""

    # Extract questions
    print("course.retry:", course.retry)
    # if course.retry:
    #     course.questions_data += [{"feedback": "That was feedback for some questions"}] + extract_questions_and_options(driver)
    #     course.retry = False
    # else:
    #     course.questions_data = extract_questions_and_options(driver)
    if course.retry:
        course.questions_data = extract_questions_and_options(driver)
        course.retry = False

    print("📋 Extracted questions:", course.questions_data)

    # Wait for the checkbox and click it using JavaScript
    checkbox = WebDriverWait(driver, iota() + 2).until(
        EC.presence_of_element_located((By.ID, "agreement-checkbox-base"))
    )
    driver.execute_script("arguments[0].click();", checkbox)

    # Get AI-generated answers
    response = ask_ai(course.questions_data)
    print("🤖 AI Response:", response)

    # Click the correct answers
    select_answers(driver, course.questions_data, response)

    print("✅ Quiz answered. Submitting...")

    # Submit the quiz
    submit_quiz(driver)

    course.skip = True
    time.sleep(iota() + 10)

    driver = course.click_next_or_retry(driver)
    return driver



def submit_quiz(driver):
    """Handles quiz submission."""
    try:
        wait = WebDriverWait(driver, 5)  # Increased wait time

        # XPath to handle both data-testid and data-test attributes
        submit_button_xpath = "//button[@data-testid='submit-button' or @data-test='submit-button']"
        confirm_button_xpath = "//button[@data-testid='dialog-submit-button' or @data-test='dialog-submit-button']"

        # Locate and click the submit button
        submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, submit_button_xpath)))
        driver.execute_script("arguments[0].click();", submit_button)
        print("✅ Clicked submit button.")

        # Try to find and click the confirmation button, but don't crash if it doesn't appear
        try:
            confirm_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, confirm_button_xpath)))
            driver.execute_script("arguments[0].click();", confirm_button)
            print("✅ Clicked confirmation button.")
        except Exception:
            print("ℹ️ No confirmation button appeared. Proceeding without it.")

        print("✅ Quiz submission flow completed.")

    except Exception as e:
        print(f"⚠️ Error submitting quiz: {e}")



### API MANAGEMENT FUNCTIONS

def load_api_keys():
    """Load API keys from api.json."""
    with open("api.json", "r") as file:
        return json.load(file)

def save_api_keys(api_data):
    """Save updated API keys to api.json."""
    with open("api.json", "w") as file:
        json.dump(api_data, file, indent=4)

def get_best_api():
    """Selects the API key using a weighted probability based on the counter."""
    api_data = load_api_keys()
    working_keys = [key for key in api_data["api_keys"] if key["status"] == "working"]

    if not working_keys:
        print("❌ No working API keys available!")
        return None, None

    # Find the highest counter value
    max_count = max(key["counter"] for key in working_keys)

    # Assign weights: lower counter -> higher probability
    weights = [(max_count - key["counter"] + 1) for key in working_keys]

    # Select API key using weighted choice
    best_key = random.choices(working_keys, weights=weights, k=1)[0]

    return best_key["key"], best_key["service"]

def mark_api_failed(api_key):
    """Marks an API key as failed in api.json."""
    api_data = load_api_keys()
    for key in api_data["api_keys"]:
        if key["key"] == api_key:
            key["status"] = "failed"
    save_api_keys(api_data)

def update_api_counter(api_key):
    """Increments API key usage counter in api.json."""
    api_data = load_api_keys()
    for key in api_data["api_keys"]:
        if key["key"] == api_key:
            key["counter"] += 1
    save_api_keys(api_data)


### AI REQUEST FUNCTION
def ask_ai(question_data, max_retries=3):
    """Gets AI answers in JSON format using the best available API key."""
    
    prompt = """
        You are an AI assistant answering multiple-choice and text-input quiz questions.

        ## Instructions:
        - Return answers in **valid JSON format**:  
        {"answers": [answer1, answer2, ..., answerN]}
        - **Each answer must correspond to exactly one question**, in the same order as provided.
        - Use the provided question format to structure responses:
        ```json
        [
            {"question": "Question text", "options": ["Option1", "Option2", ...], "input_type": "Single answer/Multiple answers/Text input"},
            ...
        ]
        ```
        - Answer formats:
        - For **"Multiple answers"** questions, return a **list** of correct options.
        - For **"Single answer"** questions, return a **string**.
        - For **"Text input"** questions, return a **string** response.
        - If the answer requires a **structured response**, return a dictionary (e.g., {"key": "value"}).
        - **Never return more answers than questions**. Each question gets **exactly one** response (list or string).
        - **Never leave an answer blank**. If no real answer is available, **make one up**.
        - **Example response** (for structured questions):
        ```json
        {
            "answers": [
            ["It provides addresses that are easier for people to remember."],
            "Root name server",
            "UDP is connectionless",
            "Service record (SRV)",
            "255"
            ]
        }
        ```
        - **Do not return** empty strings, placeholders like "I can't answer this", or explanations.
        """




    for i, q in enumerate(question_data):
        prompt += f"\n{i+1}. {q['question']}\n"
        for j, opt in enumerate(q['options']):
            prompt += f"  - {opt}\n"

    retries = 0
    while retries < max_retries:
        api_key, service = get_best_api()
        if not api_key:
            print("❌ No available API keys. Aborting.")
            return {"answers": []}

        try:
            if service == "openai":
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                answer_json = response.choices[0].message.content.strip()
                print("🔮 OpenAI Response:", answer_json)

            elif service == "gemini":
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-2.0-flash", contents=prompt
                )
                answer_json = response.text.strip()
                print("🔮 Gemini AI Response:", answer_json)

            else:
                print(f"❌ Error: Unknown service '{service}'")
                return {"answers": []}

            # Ensure we have a valid JSON response
            parsed_response = fix_and_parse_json(answer_json)

            if parsed_response and "answers" in parsed_response:
                update_api_counter(api_key)  # Only update if successful
                return parsed_response

        except Exception as e:
            print(f"❌ API Error: {e}. Marking API key as failed.")
            mark_api_failed(api_key)
            retries += 1

    print("❌ AI failed after multiple attempts.")
    return {"answers": []}


### JSON PARSING FUNCTIONS
def fix_and_parse_json(raw_response):
    """Fixes and parses AI responses into a valid JSON format."""
    try:
        # Attempt direct JSON parsing (handles well-formatted responses)
        parsed_response = json.loads(raw_response)

        # Ensure response contains "answers" and is a list
        if isinstance(parsed_response, dict) and "answers" in parsed_response:
            return parsed_response

    except json.JSONDecodeError:
        print("⚠️ AI response is not valid JSON. Attempting to fix it...")

    try:
        # Extract valid JSON using regex (handles messy responses)
        json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if json_match:
            clean_json = json_match.group(0)
            parsed_json = json.loads(clean_json)

            # Ensure it's properly structured
            if "answers" in parsed_json and isinstance(parsed_json["answers"], list):
                return parsed_json

    except Exception as e:
        print(f"❌ Failed to fix JSON: {e}")

    # If all else fails, return a default structure with an error message
    return {"answers": ["Error: Unable to parse response. AI output was invalid."]}
