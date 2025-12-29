#inbuilto
import os
import time
import logging

#installed

#mein kampf
import navigate
import course
import quiz
import misc


    
def main():
    """Main execution function."""
    driver = navigate.open_and_login()
    logging.info("Session active. Ready for automation.")
    driver = navigate.mylearning_click(driver)

    while navigate.has_incomplete_course(driver):
        course.course_end = False
        navigate.clicked_modules.clear()
        driver = navigate.course_select(driver)
        driver.switch_to.window(driver.window_handles[-1])

        try:
            driver = navigate.module(driver)
            driver = navigate.item(driver)

            while not course.course_end:  # Process each item until no more remain
                driver = process_module(driver)
                print("course.retry:", course.retry, "course.quiz_opened:", course.quiz_opened)
                if not(course.quiz_opened or course.retry or course.did_next):
                    if "/home/module" in driver.current_url:
                        driver = navigate.module(driver)
                        driver = navigate.item(driver)
                        continue
                    driver = course.next_item(driver)
                


            # driver = course.open_grades_page(driver)
            # grade_url = driver.current_url

            # while course.check_and_open_quiz(driver):
            #     time.sleep(6)
            #     course.quiz_opened = course.retry
            #     driver = quiz.quiz_open(driver)
            #     if course.quiz_opened:
            #         driver = quiz.solve_quiz(driver)
            #     driver.get(grade_url)
            #     print("Waiting before checking again...")
            #     time.sleep(6)

            # print("All quizzes are passed!")

            # Get all open window handles
            window_handles = driver.window_handles

            # Keep the last opened tab
            last_tab = window_handles[-1]

            # Close all other tabs
            for handle in window_handles:
                if handle != last_tab:
                    driver.switch_to.window(handle)
                    driver.close()

            # Switch to the last remaining tab and navigate to
            driver.switch_to.window(last_tab)
            driver.get("https://www.coursera.org")
            logging.info("here we go again.")
            driver = navigate.mylearning_click(driver)

        except Exception as e:
            print(f"⚠️ Unexpected Error in module processing: {e}")

    print("✅ No incomplete courses left. Exiting.")
    driver.quit()  # Close browser when done


def process_module(driver):
    """Processes a single module by navigating through items and solving them."""
    max_retries = 3  # Set max retry attempts

    while max_retries > 0:
        # driver = misc.scroll_randomly(driver)
        time.sleep(misc.iota(2))  # Small delay before processing the item
        course.skip = False
        course.did_next = False
        course.quiz_opened = course.quiz_opened or course.retry  # Ensure quiz state is correctly set
        # course.retry = False
        # Process each item
        driver = course.close_button(driver)

        driver = course.mark_as_completed(driver)
        if course.skip:
            break

        driver = course.should_skip(driver)
        if course.skip:
            break

        driver = course.video(driver)
        if course.skip:
            break

        driver = quiz.quiz_open(driver)
        print("Quiz opened:", course.quiz_opened)
        if course.quiz_opened:
            driver = quiz.solve_quiz(driver)

        if course.skip or course.retry:
            break

        max_retries -= 1
        print("Remaining Attempts:", max_retries)

        if max_retries == 0:
            print("❌ Max attempts reached for this item.")
            break

    return driver  # Always return driver


if __name__ == "__main__":
    main()