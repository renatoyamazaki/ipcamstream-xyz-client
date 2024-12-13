FROM debian:stable-slim AS build

RUN apt-get update -qqy && \
    apt-get install -qqy \
    ffmpeg \
    git \
    python3 \
    python3-requests \
    python3-dotenv && \
    apt-get --quiet autoremove --yes && \
    apt-get --quiet --yes clean && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/renatoyamazaki/ipcamstream-xyz-client && \
    mv ipcamstream-xyz-client /app

VOLUME /app/config
VOLUME /app/bin

WORKDIR /app
CMD [ "/app/bin/live.py" ]
