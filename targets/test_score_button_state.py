from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from datetime import date, timedelta
from targets.models import DailyAgenda
from projects.models import Project
from unittest import skip
import time


class ScoreButtonStateSeleniumTestCase(StaticLiveServerTestCase):
    """
    Selenium tests for score button state management when navigating between dates.

    This test catches the regression where score buttons retain their visual "active" state
    from previously viewed dates, making it appear that a date has been scored when it hasn't.

    Bug scenario:
    1. View a date with a scored "Other Plans" (button shows active with blue border)
    2. Navigate to a date without a score on "Other Plans"
    3. BUG: Button still shows as active even though database has no score
    4. FIX: Button should not show as active when there's no score in database
    """

    @classmethod
    def setUpClass(cls):
        """Set up Selenium WebDriver for all tests in this class."""
        super().setUpClass()
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        try:
            cls.selenium = webdriver.Chrome(options=chrome_options)
            cls.selenium.implicitly_wait(10)
        except Exception as e:
            print(f"Warning: Could not initialize Chrome WebDriver: {e}")
            cls.selenium = None

    @classmethod
    def tearDownClass(cls):
        """Clean up Selenium WebDriver."""
        if hasattr(cls, 'selenium') and cls.selenium:
            cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        """Set up test data for each test."""
        if not self.selenium:
            self.skipTest("Selenium WebDriver not available")

        # Create test project
        self.project = Project.objects.create(
            project_id=999,
            display_string='Test Project'
        )

        # Create two test dates
        self.date_with_score = date.today() - timedelta(days=2)
        self.date_without_score = date.today() - timedelta(days=1)

        # Create agenda WITH score
        self.agenda_with_score = DailyAgenda.objects.create(
            date=self.date_with_score,
            project_1=self.project,
            target_1='Complete first target',
            target_1_score=1.0,
            other_plans='# 🏆 Habits\n- [x] Exercise\n- [x] Eat clean'
        )

        # Create agenda WITHOUT score
        self.agenda_without_score = DailyAgenda.objects.create(
            date=self.date_without_score,
            project_1=self.project,
            target_1='Complete second target',
            target_1_score=0.5,
            other_plans='# 🏆 Habits\n- [ ] Exercise\n- [ ] Eat clean'
        )

    @skip("Other Plans scoring was removed - test no longer applicable")
    def test_score_button_state_clears_when_navigating_between_dates(self):
        """
        Test that score buttons clear their active state when navigating to a date without scores.

        This is a regression test for the bug where score buttons showed as active
        even when the database had no score for that date.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Navigate to activity logger
        url = f'{self.live_server_url}/activity-logger/'
        self.selenium.get(url)

        # Wait for page to load (wait for body, then wait a bit for JS to initialize)
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(0.5)  # Give JavaScript time to initialize

        # Wait for the date display to appear
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'today-date'))
        )

        # Click calendar button using XPath and JavaScript click
        calendar_button = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@onclick='showCalendarModal()']"))
        )
        self.selenium.execute_script("arguments[0].click();", calendar_button)

        # Wait for modal to appear
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, 'calendarModal'))
        )

        # Find and click the date WITH score
        # Format date as "YYYY-MM-DD" which matches the dateStr in the onclick handler
        date_with_score_str = self.date_with_score.strftime('%Y-%m-%d')
        date_cell_with_score = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//div[@class='calendar-day clickable' and contains(@onclick, '{date_with_score_str}')]")
            )
        )
        date_cell_with_score.click()

        # Wait for modal to close and agenda to load
        time.sleep(1)

        # Verify the date is displayed
        date_display = self.selenium.find_element(By.ID, 'today-date')
        self.assertIn(self.date_with_score.strftime('%B'), date_display.text)

        # Check that the "Great!" button (score=1) for Other Plans (target 4) is active
        score_button_1_happy = self.selenium.find_element(
            By.CSS_SELECTOR,
            '.score-buttons[data-target="4"] .score-btn[data-score="1"]'
        )
        self.assertIn('active', score_button_1_happy.get_attribute('class'),
                     "Score button should be active for date WITH score")

        # Now navigate to the calendar again
        calendar_button = self.selenium.find_element(By.XPATH, "//button[@onclick='showCalendarModal()']")
        self.selenium.execute_script("arguments[0].click();", calendar_button)

        # Wait for modal to appear again
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, 'calendarModal'))
        )

        # Find and click the date WITHOUT score
        date_without_score_str = self.date_without_score.strftime('%Y-%m-%d')
        date_cell_without_score = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//div[@class='calendar-day clickable' and contains(@onclick, '{date_without_score_str}')]")
            )
        )
        date_cell_without_score.click()

        # Wait for modal to close and agenda to load
        time.sleep(1)

        # Verify the date is displayed
        date_display = self.selenium.find_element(By.ID, 'today-date')
        self.assertIn(self.date_without_score.strftime('%B'), date_display.text)

        # THE CRITICAL TEST: Check that the "Great!" button for Other Plans is NOT active
        # This is the bug we're testing - before the fix, the button would still show as active
        score_button_2_happy = self.selenium.find_element(
            By.CSS_SELECTOR,
            '.score-buttons[data-target="4"] .score-btn[data-score="1"]'
        )
        self.assertNotIn('active', score_button_2_happy.get_attribute('class'),
                        "Score button should NOT be active for date WITHOUT score - "
                        "this tests the fix for the state persistence bug")

        # Also verify that none of the other score buttons are active either
        all_score_buttons_target_4 = self.selenium.find_elements(
            By.CSS_SELECTOR,
            '.score-buttons[data-target="4"] .score-btn[data-score]'
        )
        for button in all_score_buttons_target_4:
            self.assertNotIn('active', button.get_attribute('class'),
                           "No score buttons should be active when database has no score")

    @skip("Other Plans scoring was removed - test no longer applicable")
    def test_score_button_state_loads_correctly_for_date_with_score(self):
        """
        Test that score buttons correctly show as active when loading a date that HAS a score.

        This ensures our fix doesn't break the normal functionality of loading scores.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Navigate to activity logger
        url = f'{self.live_server_url}/activity-logger/'
        self.selenium.get(url)

        # Wait for page to load (wait for body, then wait a bit for JS to initialize)
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(0.5)  # Give JavaScript time to initialize

        # Wait for the date display to appear
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'today-date'))
        )

        # Click calendar button using XPath and JavaScript click
        calendar_button = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@onclick='showCalendarModal()']"))
        )
        self.selenium.execute_script("arguments[0].click();", calendar_button)

        # Wait for modal to appear
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, 'calendarModal'))
        )

        # Find and click the date WITH score
        date_with_score_str = self.date_with_score.strftime('%Y-%m-%d')
        date_cell = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//div[@class='calendar-day clickable' and contains(@onclick, '{date_with_score_str}')]")
            )
        )
        date_cell.click()

        # Wait for modal to close and agenda to load
        time.sleep(1)

        # Check that Target 1's score button (score=1) is active
        score_button_target1 = self.selenium.find_element(
            By.CSS_SELECTOR,
            '.score-buttons[data-target="1"] .score-btn[data-score="1"]'
        )
        self.assertIn('active', score_button_target1.get_attribute('class'),
                     "Target 1 score button should be active")

        # Check that Other Plans's score button (score=1) is active
        score_button_target4 = self.selenium.find_element(
            By.CSS_SELECTOR,
            '.score-buttons[data-target="4"] .score-btn[data-score="1"]'
        )
        self.assertIn('active', score_button_target4.get_attribute('class'),
                     "Other Plans score button should be active")
