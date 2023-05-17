import unittest
from datetime import datetime, timedelta
import pytz
import os

from main import scrape_url_to_calendar, create_ical

class TestCalendarFunctions(unittest.TestCase):
    
    def setUp(self):
        # Set up any necessary test data or configurations
        pass
    
    def tearDown(self):
        # Clean up after each test case
        pass
    
    def test_scrape_url_to_calendar(self):
        # Test the scrape_url_to_calendar function
        events = scrape_url_to_calendar()
        self.assertIsNotNone(events)
    
    def test_create_ical(self):
        # Test the create_ical function
        
        # Add your test cases here
        
        # Test case 1: Create iCalendar file with events
        events = [
            (datetime(2023, 5, 16, 9, 0), datetime(2023, 5, 16, 17, 0), 'Location 1'),
            (datetime(2023, 5, 17, 8, 0), datetime(2023, 5, 17, 16, 0), 'Location 2'),
            # Add more events if needed
        ]
        directory = '/tmp'  # Provide the directory where the iCalendar file should be saved
        create_ical(events, pharmacy='Kaiser', directory=directory)
        
        # Check if the iCalendar file was created
        file_path = os.path.join(directory, 'Kaiser.ics')
        self.assertTrue(os.path.isfile(file_path))
        
        # Test case 2: Create iCalendar file with no events
        events = []
        create_ical(events, pharmacy='Kaiser', directory=directory)
        
        # Check if the iCalendar file was created
        self.assertTrue(os.path.isfile(file_path))
    
    # Add more test cases if needed

if __name__ == '__main__':
    unittest.main()

