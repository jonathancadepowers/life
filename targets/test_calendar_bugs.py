from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth.models import User
from targets.models import DailyAgenda
from datetime import date, timedelta


class CalendarBugsSeleniumTestCase(StaticLiveServerTestCase):
    """
    Selenium tests for calendar-related bugs on activity-logger page.

    Tests cover:
    1. Future dates with agendas showing as blue (past) instead of green (future)
    2. Future dates with agendas loading empty form instead of actual agenda data
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

        # Create test user
        self.user = User.objects.create_user(username='testuser', password='testpass')

        # Login
        self.selenium.get(f'{self.live_server_url}/admin/')
        from selenium.webdriver.common.by import By
        self.selenium.find_element(By.NAME, 'username').send_keys('testuser')
        self.selenium.find_element(By.NAME, 'password').send_keys('testpass')
        self.selenium.find_element(By.CSS_SELECTOR, 'input[type="submit"]').click()

        # Create agendas for testing
        self.today = date.today()
        self.yesterday = self.today - timedelta(days=1)
        self.tomorrow = self.today + timedelta(days=1)
        self.future_date = self.today + timedelta(days=3)

        # Create agenda for yesterday (past date)
        self.agenda_yesterday = DailyAgenda.objects.create(
            date=self.yesterday,
            target_1='Past target',
            other_plans='# Past plans'
        )

        # Create agenda for tomorrow (future date with agenda)
        self.agenda_tomorrow = DailyAgenda.objects.create(
            date=self.tomorrow,
            target_1='Future target',
            other_plans='# Future plans\n- Task 1\n- Task 2'
        )

    def test_future_date_with_agenda_shows_green_not_blue(self):
        """
        Test that future dates with existing agendas show green (future) styling
        instead of blue (past) styling.

        Bug: After creating agenda for Nov 3 (future), calendar showed it as blue
        instead of green because it didn't check if date was in future.

        Fix: Calendar now checks isFuture and applies green styling for future dates
        even when they have agendas.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time

        # Navigate to activity logger
        self.selenium.get(f'{self.live_server_url}/activity-logger/')

        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(0.5)

        # Click calendar button
        calendar_button = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@onclick='showCalendarModal()']"))
        )
        self.selenium.execute_script("arguments[0].click();", calendar_button)

        # Wait for modal to appear
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, 'calendarModal'))
        )

        time.sleep(1)  # Give calendar time to render

        # Find tomorrow's date cell
        tomorrow_str = self.tomorrow.strftime('%Y-%m-%d')
        tomorrow_cell = self.selenium.find_element(
            By.XPATH,
            f"//div[contains(@class, 'calendar-day') and contains(@onclick, '{tomorrow_str}')]"
        )

        # Verify it has the 'future' class (green styling)
        classes = tomorrow_cell.get_attribute('class')
        self.assertIn('future', classes,
                     f"Tomorrow's date ({self.tomorrow}) with agenda should have 'future' class for green styling")
        self.assertIn('clickable', classes,
                     "Tomorrow's date should be clickable")

        # Verify it has green background color
        background_color = tomorrow_cell.value_of_css_property('background-color')
        # Green is rgb(40, 167, 69) = #28a745
        self.assertIn('40', background_color,
                     "Future date with agenda should have green background color")

        # Also verify yesterday's date shows as blue (past), not green
        yesterday_str = self.yesterday.strftime('%Y-%m-%d')
        yesterday_cell = self.selenium.find_element(
            By.XPATH,
            f"//div[contains(@class, 'calendar-day') and contains(@onclick, '{yesterday_str}')]"
        )

        classes = yesterday_cell.get_attribute('class')
        self.assertNotIn('future', classes,
                        "Yesterday's date should NOT have 'future' class")
        self.assertIn('clickable', classes,
                     "Yesterday's date should be clickable")

    def test_future_date_with_agenda_loads_data_not_empty_form(self):
        """
        Test that clicking on a future date with existing agenda loads the actual
        agenda data instead of showing an empty form.

        Bug: After calendar color fix, future dates with agendas were passing
        isFuture=true to selectDate(), causing it to show empty form instead of
        fetching the actual agenda.

        Fix: Dates with existing agendas now always fetch data (isFuture=false),
        regardless of whether they're past or future.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time

        # Navigate to activity logger
        self.selenium.get(f'{self.live_server_url}/activity-logger/')

        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(0.5)

        # Click calendar button
        calendar_button = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@onclick='showCalendarModal()']"))
        )
        self.selenium.execute_script("arguments[0].click();", calendar_button)

        # Wait for modal to appear
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, 'calendarModal'))
        )

        time.sleep(1)  # Give calendar time to render

        # Click on tomorrow's date (future date with agenda)
        tomorrow_str = self.tomorrow.strftime('%Y-%m-%d')
        tomorrow_cell = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//div[contains(@class, 'calendar-day') and contains(@onclick, '{tomorrow_str}')]")
            )
        )
        self.selenium.execute_script("arguments[0].click();", tomorrow_cell)

        # Wait for modal to close and data to load
        time.sleep(2)

        # Verify the agenda data loaded correctly
        # Check that target_1 field contains the future target text
        target_1_field = self.selenium.find_element(By.ID, 'target_1')
        target_1_value = target_1_field.get_attribute('value')

        self.assertEqual(target_1_value, 'Future target',
                        "Future date with agenda should load actual target data, not empty form")

        # Check that other plans textarea contains the future plans
        other_plans_textarea = self.selenium.find_element(By.ID, 'other-plans-textarea')
        other_plans_value = other_plans_textarea.get_attribute('value')

        self.assertIn('Future plans', other_plans_value,
                     "Future date with agenda should load actual other plans data")
        self.assertIn('Task 1', other_plans_value,
                     "Other plans should contain full content from database")

        # Verify the date display is correct
        date_display = self.selenium.find_element(By.ID, 'today-date')
        # Should show the tomorrow's date in formatted form
        self.assertIn(self.tomorrow.strftime('%B'), date_display.text,
                     "Date display should show the correct month")

    def test_date_without_agenda_shows_empty_form(self):
        """
        Test that clicking on a future date WITHOUT an agenda shows empty form.

        This ensures our fix didn't break the normal behavior of future dates
        without agendas.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time

        # Navigate to activity logger
        self.selenium.get(f'{self.live_server_url}/activity-logger/')

        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(0.5)

        # Click calendar button
        calendar_button = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@onclick='showCalendarModal()']"))
        )
        self.selenium.execute_script("arguments[0].click();", calendar_button)

        # Wait for modal to appear
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, 'calendarModal'))
        )

        time.sleep(1)  # Give calendar time to render

        # Click on future_date (3 days from now, no agenda)
        future_str = self.future_date.strftime('%Y-%m-%d')
        future_cell = WebDriverWait(self.selenium, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//div[contains(@class, 'calendar-day') and contains(@onclick, '{future_str}')]")
            )
        )

        # Verify it has green styling (future)
        classes = future_cell.get_attribute('class')
        self.assertIn('future', classes,
                     "Future date without agenda should still have 'future' class")

        self.selenium.execute_script("arguments[0].click();", future_cell)

        # Wait for modal to close and form to appear
        time.sleep(2)

        # Verify the form is empty
        target_1_field = self.selenium.find_element(By.ID, 'target_1')
        target_1_value = target_1_field.get_attribute('value')

        self.assertEqual(target_1_value, '',
                        "Future date without agenda should show empty target field")

        # Check that other plans textarea is empty
        other_plans_textarea = self.selenium.find_element(By.ID, 'other-plans-textarea')
        other_plans_value = other_plans_textarea.get_attribute('value')

        self.assertEqual(other_plans_value, '',
                        "Future date without agenda should show empty other plans")
