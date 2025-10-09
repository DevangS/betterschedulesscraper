# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands
- Activate virtual environment: `source bin/activate`
- Install dependencies: `pip3 install -r requirements.txt` (use system pip3 when venv is active)
- Run application: `python3 main.py`
- Run tests: `python3 -m unittest tests.py`
- Run specific test: `python3 -m unittest tests.TestCalendarFunctions.test_create_ical`
- Deactivate virtual environment: `deactivate`
- Docker build: `docker build -t betterschedulesscraper .`
- Docker run: `docker run -p 8080:8080 betterschedulesscraper`

## Remote Deployment & Testing
- **Production server**: lapew (accessible via `ssh devang@lapew`)
- **Deploy script**: `./deploy_lapew.sh` - deploys main.py and restarts the service
- **SSH key**: Already loaded in SSH agent (id_ed25519)
- **Service name**: `betterschedulescraper.service`
- **Remote path**: `/home/devang/betterschedulescraper/`

### Testing Changes Autonomously
- Since code cannot be run locally, ALWAYS test changes on lapew after making them
- Use `ssh devang@lapew "<command>"` to run remote commands
- Check service status: `ssh devang@lapew "sudo systemctl status betterschedulescraper.service"`
- View logs: `ssh devang@lapew "journalctl -u betterschedulescraper.service -n 50"`
- Restart service: `ssh devang@lapew "sudo systemctl restart betterschedulescraper.service"`
- After deploying with `./deploy_lapew.sh`, verify the service started successfully and check logs for errors

## Code Style Guidelines
- Use PEP 8 conventions for Python code
- Import order: standard library, third-party, local application imports
- Use type hints for function parameters and return values
- Naming: snake_case for functions/variables, CamelCase for classes
- Error handling: Use try/except with specific exceptions
- Follow existing pattern of exception handling with error messages
- Document complex functions with docstrings
- Include informative print statements for debugging

## Security & ENV Variables
- Credentials should be loaded from environment variables, not hardcoded
- Use os.environ.get() with fallback to secret.py for development
- Do not commit sensitive credentials in secret.py

## Debugging Selenium Issues
- For Selenium NoSuchElementException errors, first check if elements exist with `inspect_login.py`
- Always use WebDriverWait with explicit waits instead of immediate element finding
- Add comprehensive error handling with current URL and page title logging
- List all page elements when debugging to identify selector changes
- For Chrome binary issues, ensure Chrome is installed and accessible to the WebDriver
- Use `debug_login.py` to test Chrome driver configuration and element detection