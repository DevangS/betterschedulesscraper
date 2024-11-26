FROM selenium/standalone-chrome:latest

USER root
RUN apt-get update && apt-get install python3.12-venv gunicorn -y

# Create the /app directory and set correct permissions
RUN mkdir -p /app && \
    chown -R seluser:seluser /app && \
    chmod -R 755 /app

# Switch back to seluser
USER seluser

# Set working directory
WORKDIR /app
COPY main.py .
COPY requirements.txt .

RUN python3 -m venv venv
RUN . venv/bin/activate && pip3 install -r requirements.txt

EXPOSE 8080

# Set the environment variable for Flask to know where the app is located
ENV FLASK_APP=main.py

# Set the command to start the Flask app
CMD ["venv/bin/python3", "-m", "gunicorn", "-b", "0.0.0.0:8080", "main:app"]
