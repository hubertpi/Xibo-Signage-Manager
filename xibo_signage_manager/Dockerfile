FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache tzdata font-dejavu
RUN pip install --no-cache-dir requests==2.32.3 paho-mqtt==2.1.0 Pillow==11.3.0
COPY manager.py counter.py /app/
CMD ["python3", "-u", "/app/manager.py"]
