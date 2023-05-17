source venv/bin/activate
python tests.py
fly version update
fly deploy
curl -L http://schedule.dayindev.com/update
