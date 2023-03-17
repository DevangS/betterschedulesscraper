import http.cookiejar
from selenium import webdriver
from selenium.webdriver.common.by import By
from datetime import datetime

from secrets import USERNAME, PASSWORD

#URL_TEMPLATE = 'https://portal.providerscience.com/account/signin?returnurl=/employee/schedule/?date=%s'
URL_TEMPLATE = 'https://portal.providerscience.com/employee/schedule/?date=%s'


def run():
    cookie_jar = http.cookiejar.MozillaCookieJar(filename="cookies.txt")
    cookie_jar.load()

    chrome_driver = webdriver.Chrome()
    url = URL_TEMPLATE % datetime.today().strftime('%m/%d/%Y')
    chrome_driver.get(url)
    for cookie in cookie_jar:
        chrome_driver.add_cookie(cookie.__dict__)
    # chrome_driver.maximize_window()

    if len(cookie_jar) == 0:
        # login to the website
        username_text_field = chrome_driver.find_element(By.ID, "Username")
        username_text_field.send_keys(USERNAME)

        password_text_field = chrome_driver.find_element(By.ID, "Password")
        password_text_field.send_keys(PASSWORD)

        # save cookies for next time
        for cookie in chrome_driver.get_cookies():
            cookie_jar.set_cookie(http.cookiejar.Cookie(
                version=0,
                name=cookie['name'],
                value=cookie['value'],
                port=None,
                port_specified=False,
                domain=cookie['domain'],
                domain_specified=True,
                domain_initial_dot=False,
                path=cookie['path'],
                path_specified=True,
                secure=cookie['secure'],
                expires=None,
                discard=False,
                comment=None,
                comment_url=None,
                rest=None
            ))
        cookie_jar.save()

    chrome_driver.find_element(By.CLASS_NAME, "btn-signin").click()

    all_days = chrome_driver.find_elements(By.CLASS_NAME, "day")
    scheduled_days = chrome_driver.find_elements(By.CLASS_NAME, "has-actions")
    print('Found %s schedules' % len(scheduled_days))

    month = ''
    for day_div in all_days:
        if day_div.text:
            # Get the Month and Day
            date_text = day_div.find_element(By.CLASS_NAME, "title").text
            if len(date_text) > 2:
                month, day = date_text.split(' ')
            else:
                day = date_text

            if month is None:
                continue

            # Figure out type of day
            day_type = day_div.get_attribute("class")
            if 'is-off' in day_type:
                # PTO
                print (month, day, '00:00', '23:59', 'PTO')
            elif 'non-month' in day_type:
                # can't look ahead that far yet
                continue
            elif 'has-actions' in day_type:
                #scheduled to work
                off_text = day_div.find_element(By.CLASS_NAME, "content")
                off = off_text.text.split('\n')
                time = off[0]
                start, _, end = time.split(' ')

                location = off[-1]
                print(month, day, start, end, location)



if __name__ == '__main__':
    run()

