ARG BUILD_FROM
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-pip && python3 -m venv /venv && /venv/bin/pip install --no-cache-dir requests==2.32.3 paho-mqtt==2.1.0
COPY run.sh /run.sh
COPY manager.py /manager.py
RUN chmod +x /run.sh
CMD ["/run.sh"]
