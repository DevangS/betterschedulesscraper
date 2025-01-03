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

        all_days = chrome_driver.find_elements(By.CLASS_NAME, "day")
        scheduled_days = chrome_driver.find_elements(By.CLASS_NAME, "has-actions")
        print('Found %s schedules on %s days for date %s' % (len(scheduled_days), len(all_days), date))


        for day_div in all_days:
            try:
                if day_div.text:
                    classes = day_div.get_attribute('class')

                    if 'has-actions' in classes:
                        # get the shift start date
                        shift_element = day_div.find_element(By.CLASS_NAME, "shift-v2")
                        shift_id = shift_element.get_attribute("data-shift-id")
                        shift_date = shift_id.split(':')[-1]

                        # create datetime objects for start and end
                        start = datetime.strptime(shift_date, '%Y%m%d')
                        end = datetime.strptime(shift_date, '%Y%m%d')

                        # get the shift schedule time
                        off_text = day_div.find_element(By.CLASS_NAME, "content").text
                        off = off_text.split('\n')
                        time = off[0]
                        start_str, _, end_str = time.split(' ')

                        start = _update_date_with_time(start, start_str)
                        end = _update_date_with_time(end, end_str)

                        # some shifts go overnight so end the next day
                        if end < start:
                            end = end.replace(day=end.day + 1)

                        location = off[-1]
                        events.add((start, end, location))
                    else:
                        continue

            except Exception as e:
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
    dates = [datetime.today(), datetime.today() + timedelta(days=30)]
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
