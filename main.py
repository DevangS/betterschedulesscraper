import os
import pathlib
from flask import Flask, Response
import icalendar
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
from secret import USERNAME, PASSWORD

LOGIN_URL = 'https://portal.providerscience.com/account/signin'
URL_TEMPLATE = 'https://portal.providerscience.com/employee/schedule/?date=%s'

app = Flask(__name__)


def scrape_url_to_calendar(date=datetime.today()):
    def _update_date_with_time(date_obj: datetime, time_str: str) -> datetime:
        regex = '%I:%M%p' if ':' in time_str else '%I%p'
        new_time = datetime.strptime(time_str + 'm', regex)
        return datetime(year=date_obj.year, month=date_obj.month,
                        day=date_obj.day, hour=new_time.hour,
                        minute=new_time.minute)

    pathlib.Path('/tmp').mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-data-dir=selenium")
    chrome_driver = webdriver.Chrome(options=chrome_options)

    # login to the website
    chrome_driver.get(LOGIN_URL)
    username_text_field = chrome_driver.find_element(By.ID, "Username")
    username_text_field.send_keys(USERNAME)

    password_text_field = chrome_driver.find_element(By.ID, "Password")
    password_text_field.send_keys(PASSWORD)
    chrome_driver.find_element(By.CLASS_NAME, "btn-signin").click()

    # get the schedule
    url = URL_TEMPLATE % date.strftime('%m/%Y')
    chrome_driver.get(url)

    all_days = chrome_driver.find_elements(By.CLASS_NAME, "day")
    scheduled_days = chrome_driver.find_elements(By.CLASS_NAME, "has-actions")
    print('Found %s schedules on %s days' % (len(scheduled_days), len(all_days)))

    month_num = None
    events = []
    for day_div in all_days:
        try:
            if day_div.text:
                classes = day_div.get_attribute('class')

                # Get the Month and Day
                date_text = day_div.find_element(By.CLASS_NAME, "title").text
                #print(date_text, classes)
                if 'today' in classes:
                    today = datetime.today()
                    month_num = today.month
                    day_num = today.day
                elif len(date_text) > 2:
                    month, day_num = date_text.split(' ')
                    day_num = int(day_num)
                    month_num = datetime.strptime(month, '%b').month
                else:
                    day_num = int(date_text)
                    if month_num is not None and day_num == 1:
                        print('increasing month')
                        month_num = ((month_num + 1) % 12)
                if 'non-month' not in classes:
                    month_num = date.month

                if month_num is None:
                    continue

                # Figure out type of day
                start = datetime(month=month_num, day=day_num, year=datetime.today().year)
                end = datetime(month=month_num, day=day_num, year=datetime.today().year)

                day_type = day_div.get_attribute("class")
                if 'is-off' in day_type:
                    # PTO
                    location = 'PTO'
                elif 'non-month' in day_type:
                    # can't look ahead that far yet
                    continue
                elif 'has-actions' in day_type:
                    # scheduled to work
                    off_text = day_div.find_element(By.CLASS_NAME, "content")
                    off = off_text.text.split('\n')
                    time = off[0]
                    start_str, _, end_str = time.split(' ')

                    start = _update_date_with_time(start, start_str)
                    end = _update_date_with_time(end, end_str)

                    # midnight ending shift ends the next day
                    if end.hour == 0 and end.minute == 0:
                        end = end.replace(day=end.day + 1)

                    location = off[-1]
                else:
                    continue

                events.append((start, end, location))
        except Exception as e:
            continue
    return events


def create_ical(events, pharmacy='Kaiser', directory=os.getcwd()):
    # Create calendar object
    cal = icalendar.Calendar()
    name = '%s Shifts' % pharmacy
    cal.add('prodid', '-//%s//dayindev.com//' % name)
    cal.add('version', '2.0')

    # Create event object
    for start, end, location in events:
        event = icalendar.Event()
        event.add('summary', location)
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', name)
        cal.add('x-wr-timezone', cal.add('x-wr-timezone', 'America/Los_Angeles'))

        if start == end:
            event.add('dtstart', start.date())  # Use DATE value for all-day event
            event.add('dtend', start.date())  # Use DATE value for all-day event
        else:
            event.add('dtstart', start)
            event.add('dtend', end)

        event.add('dtstamp', datetime.now())

        if location != 'PTO':
            event.add('location', pharmacy + ' ' + location)

        # Add event to calendar
        cal.add_component(event)

    # Generate iCal file
    f = open(os.path.join(directory, '%s.ics' % pharmacy), 'wb')
    f.write(cal.to_ical())
    f.close()


# Define a route to serve the iCalendar data
@app.route('/<pharmacy>.ics')
def serve_ical(pharmacy, directory='/tmp'):
    # Check if the calendar file exists
    path = os.path.join(directory, '%s.ics' % pharmacy)
    if not os.path.isfile(path):
        return 400

    # Serve the calendar file
    with open(path, 'rb') as f:
        calendar_data = f.read()
    return Response(calendar_data, mimetype='text/calendar')


@app.route('/update')
def update_schedule():
    events = set([])
    for date in [datetime.today(),
                 datetime.today() + timedelta(days=30)]:
        result = scrape_url_to_calendar(date)
        events.update(set(result))
    create_ical(sorted(events, key=lambda x: x[0]), directory='/tmp')

    log = 'Updated %s schedules' % len(events)
    print(log)
    return log, 200


# Define a route for a health check
@app.route('/health')
def health_check():
    return 'OK', 200

if __name__ == '__main__':
    update_schedule()
