# Build from the repository root: docker build -f webapp/Dockerfile -t sushasan_webapp .

FROM       debian:stable-slim
LABEL      maintainer="marcin@ulikowski.pl"

WORKDIR    /opt/sushasan

RUN        apt-get update && \
           apt-get install -y --no-install-recommends python3-idna python3-tld python3-dnspython python3-geoip gunicorn3 python3-flask

COPY       ./webapp/webapp.py /opt/sushasan/
COPY       ./webapp/webapp.html /opt/sushasan/
COPY       ./sushasan.py /opt/sushasan/

EXPOSE     8000

CMD        ["gunicorn3", "webapp:app", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "3", "--log-level", "debug"]
