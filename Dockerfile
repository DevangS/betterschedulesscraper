FROM selenium/standalone-chrome:latest

RUN sudo apt-get update
RUN sudo apt-get install -y python3 python3-pip gunicorn
RUN sudo apt autoremove && sudo apt clean

COPY . /app
WORKDIR app
RUN python3 -m pip install -r requirements.txt
EXPOSE 8080

# Set the environment variable for Flask to know where the app is located
ENV FLASK_APP main.py

# Set the command to start the Flask app
CMD ["gunicorn", "-b", "0.0.0.0:8080", "main:app"]
