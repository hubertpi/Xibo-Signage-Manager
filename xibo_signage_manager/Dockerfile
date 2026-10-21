FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache poppler-utils
RUN pip install --no-cache-dir requests==2.32.3 paho-mqtt==2.1.0 'icalendar>=6,<7' 'recurring-ical-events>=3,<4'
COPY manager.py counter_widget.py calendar_widget.py layout_sync.py slideshow.py config.yaml /app/
CMD ["python3", "-u", "/app/manager.py"]
