FROM python:3.12-alpine
WORKDIR /app
RUN pip install --no-cache-dir requests==2.32.3 paho-mqtt==2.1.0
COPY manager.py counter_widget.py /app/
CMD ["python3", "-u", "/app/manager.py"]
