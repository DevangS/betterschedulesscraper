import os
import pathlib

import pytz
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response
import icalendar
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

LOGIN_URL = 'https://portal.providerscience.com/account/signin'
URL_TEMPLATE = 'https://portal.providerscience.com/employee/schedule/?date=%s'

app = Flask(__name__)

try:
    from secret import USERNAME, PASSWORD
except ModuleNotFoundError:
    USERNAME = os.environ.get('USERNAME')
    PASSWORD = os.environ.get('PASSWORD')

STORAGE_DIR = '/tmp'
updated = None


def scrape_url_to_calendar(dates):
    def _update_date_with_time(date_obj: datetime, time_str: str) -> datetime:
        regex = '%I:%M%p' if ':' in time_str else '%I%p'
        new_time = datetime.strptime(time_str + 'm', regex)
        return datetime(year=date_obj.year, month=date_obj.month,
                        day=date_obj.day, hour=new_time.hour,
                        minute=new_time.minute)

    pathlib.Path('/tmp/selenium').mkdir(parents=True, exist_ok=True)

    chrome_options = Options()

    # check if chrome is already installed (arm64 installation is annoying with driver manager
    if os.path.exists('/usr/bin/chromedriver'):
        service = Service('/usr/bin/chromedriver')
    else:
        service = Service(ChromeDriverManager().install())

    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-data-dir=/tmp/selenium")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_driver = webdriver.Chrome(options=chrome_options, service=service)

    # login to the website
    chrome_driver.get(LOGIN_URL)
    username_text_field = chrome_driver.find_element(By.ID, "Username")
    username_text_field.send_keys(USERNAME)

    password_text_field = chrome_driver.find_element(By.ID, "Password")
    password_text_field.send_keys(PASSWORD)
    chrome_driver.find_element(By.CLASS_NAME, "btn-signin").click()

    events = set([])
    for date in dates:
        # get the schedule
        url = URL_TEMPLATE % date.strftime('%m/%Y')
        chrome_driver.get(url)
        
        # Wait for the calendar to load
        try:
            WebDriverWait(chrome_driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "day"))
            )
        except Exception as e:
            print(f"Timeout waiting for calendar to load: {e}")
            continue

        all_days = chrome_driver.find_elements(By.CLASS_NAME, "day")
        scheduled_days = chrome_driver.find_elements(By.CLASS_NAME, "has-actions")
        print('Found %s schedules on %s days for date %s' % (len(scheduled_days), len(all_days), date))

        for i, day_div in enumerate(all_days):
            try:
                # Get a fresh reference to the day div
                day_div = chrome_driver.find_elements(By.CLASS_NAME, "day")[i]
                if not day_div.get_attribute('textContent'):
                    continue
                
                classes = day_div.get_attribute('class')
                if 'has-actions' not in classes:
                    continue

                # get the day number for better error reporting
                try:
                    day_number = day_div.find_element(By.CLASS_NAME, "title").text
                except NoSuchElementException:
                    print("Could not find day number for a day")
                    continue

                # Try to find shifts div
                try:
                    shifts_div = day_div.find_element(By.CLASS_NAME, "shifts")
                except NoSuchElementException:
                    continue

                # Try to find shift element
                try:
                    shift_element = shifts_div.find_element(By.XPATH, ".//div[contains(@class, 'shift-v2')]")
                except NoSuchElementException:
                    print(f"No shift element found for day {day_number}")
                    continue

                # Get shift ID
                shift_id = shift_element.get_attribute("data-shift-id")
                if shift_id is None:
                    print(f"No shift ID found for day {day_number}")
                    continue

                # Try to get time element
                try:
                    content_div = shift_element.find_element(By.CLASS_NAME, "content")
                    time_element = content_div.find_element(By.CLASS_NAME, "content-item")
                except NoSuchElementException:
                    print(f"Could not find time element for day {day_number}")
                    continue

                shift_date = shift_id.split(':')[-1]

                # create datetime objects for start and end
                try:
                    start = datetime.strptime(shift_date, '%Y%m%d')
                    end = datetime.strptime(shift_date, '%Y%m%d')
                except ValueError as e:
                    print(f"Error parsing shift date for day {day_number}: {e}")
                    continue

                # get the shift schedule time
                time_text = time_element.text
                try:
                    start_str, _, end_str = time_text.split(' ')
                except ValueError:
                    print(f"Unexpected time format for day {day_number}: {time_text}")
                    continue

                try:
                    start = _update_date_with_time(start, start_str)
                    end = _update_date_with_time(end, end_str)
                except ValueError as e:
                    print(f"Error parsing time for day {day_number}: {e}")
                    continue

                # some shifts go overnight so end the next day
                if end < start:
                    end = end.replace(day=end.day + 1)

                # Try to get location
                try:
                    location_element = content_div.find_elements(By.CLASS_NAME, "content-item")[-1]
                    location = location_element.find_element(By.TAG_NAME, "strong").text
                except (NoSuchElementException, IndexError):
                    print(f"Could not find location for day {day_number}")
                    continue

                events.add((start, end, location))

            except Exception as e:
                print(f"Unexpected error processing day: {e}")
                continue

    return events


def create_ical(events, pharmacy='Kaiser', directory=os.getcwd(), timezone='America/Los_Angeles'):
    # Create calendar object
    cal = icalendar.Calendar()
    name = '%s Shifts' % pharmacy
    cal.add('prodid', '-//%s//dayindev.com//' % name)
    cal.add('version', '2.0')

    # Initialize timezone
    tz = pytz.timezone(timezone)

    # Set calendar timezone
    cal.add('x-wr-timezone', timezone)

    # Create event object
    for start, end, location in events:
        event = icalendar.Event()
        event.add('summary', location)

        if start == end:
            event.add('dtstart', start.date())  # Use DATE value for all-day event
            event.add('dtend', start.date())  # Use DATE value for all-day event
        else:
            event.add('dtstart', tz.localize(start))
            event.add('dtend', tz.localize(end))

        event.add('dtstamp', datetime.now())

        if location != 'PTO':
            event.add('location', pharmacy + ' ' + location)

        # Add event to calendar
        cal.add_component(event)

    # Generate iCal file
    f = open(os.path.join(directory, '%s.ics' % pharmacy), 'wb')
    f.write(cal.to_ical())
    f.close()


def _get_pharmacy_ics_path(pharmacy):
    path = os.path.join(STORAGE_DIR, '%s.ics' % pharmacy)
    if not os.path.isfile(path):
        return None
    return path


# Define a route to serve the iCalendar data
@app.route('/<pharmacy>.ics')
def serve_ical(pharmacy):
    # Check if the calendar file exists
    path = _get_pharmacy_ics_path(pharmacy)
    if not path:
        return 400

    # Serve the calendar file
    with open(path, 'rb') as f:
        calendar_data = f.read()
    return Response(calendar_data, mimetype='text/calendar')


@app.route('/update')
def update_schedule():
    # Get all unique months between today and 30 days from now
    start_date = datetime.today()
    end_date = start_date + timedelta(days=30)
    
    dates = []
    current_date = start_date
    while current_date <= end_date:
        # Create a new date object for the first of each month
        month_date = datetime(current_date.year, current_date.month, 1)
        if month_date not in dates:
            dates.append(month_date)
        # Move to the first of next month
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)
    events = scrape_url_to_calendar(dates)
    sorted_events = sorted(events, key=lambda x: x[0])

    create_ical(sorted_events, directory=STORAGE_DIR)

    # we dont believe in thread safety here
    global updated
    updated = datetime.now()

    log = 'Updated %s schedules. Latest shift is %s' % (len(events), [str(_) for _ in sorted_events[-1]])
    print(log)
    return log, 200


@app.route('/last_updated')
def last_updated():
    return str(updated), 200


# Define a route for a health check
@app.route('/health')
def health_check():
    return 'OK', 200


sched = BackgroundScheduler({
    'apscheduler.executors.default': {
        'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
        'max_workers': '1'
    },
    'apscheduler.job_defaults.coalesce': 'false',
    'apscheduler.job_defaults.max_instances': '1',
})
sched.add_job(update_schedule, 'interval', minutes=300)
sched.start()

if __name__ == '__main__':
    update_schedule()
