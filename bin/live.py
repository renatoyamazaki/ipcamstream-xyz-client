#!/usr/bin/env python3

import os
import socket
import requests
import logging
import subprocess
from subprocess import Popen
from multiprocessing import Process, Lock
from os import getenv
from dotenv import load_dotenv
import time
import signal
import sys
from datetime import datetime

def setup_logger(cameraname):
    """Set up logger with file handler for each camera."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    log_filename = os.path.join("logs", f"{cameraname}_{today}.log")
    
    logger = logging.getLogger(cameraname)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create file handler only
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    
    # Create formatter and add it to the handler
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s")
    file_handler.setFormatter(formatter)
    
    # Add the handler to the logger
    logger.addHandler(file_handler)
    
    return logger

def checkHostPort(ip, port, logger, timeout=5):
    """Check if the host and port are open."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except (socket.timeout, socket.error) as e:
        logger.error(f"Error connecting to {ip}:{port} - {e}")
        return False
    finally:
        s.close()

def getHostPort(rtsp):
    """Extract host and port from the RTSP URL."""
    s = rtsp
    if '@' not in s:
        r = s.split('/')[2].split(':')
    else:
        r = s.split('/')[2].split('@')[1].split(':')
    return r[0], r[1]

def check_codec(rtsp_url, logger):
    """Check the codec of the video stream."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1", rtsp_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        codec = result.stdout.strip()
        return codec
    except Exception as e:
        logger.error(f"Error checking codec for {rtsp_url}: {e}")
        return None

def streamIpcam(ipcamId, host, port, rtsp, time_limit):
    """Stream the IP camera's RTSP stream."""
    # Create logger for this camera
    logger = setup_logger(str(ipcamId))
    
    while True:
        cam_on = checkHostPort(host, port, logger)
        if cam_on:
            codec = check_codec(rtsp, logger)
            if not codec:
                logger.warning(f"Could not determine codec for {rtsp}, stopping.")
                break

            streamUrl = getStreamUrl(ipcamId, codec, logger)
            if codec == "hevc":
                streamUrlHls = f"{streamUrl.rsplit('/', 1)[0]}/stream.m3u8"
                cmd = f"ffmpeg -timeout 5 -t {time_limit} -i {rtsp} -c:v copy -f hls -method PUT -hls_time 1 -hls_playlist_type event -http_persistent 1 '{streamUrlHls}' > /dev/null 2>&1"
                logger.info(f"Stream URL (HLS): {streamUrlHls}")
            elif codec == "h264":
                cmd = f"ffmpeg -t {time_limit} -nostdin -timeout 5000000 -i {rtsp} -vcodec copy -acodec copy -f flv {streamUrl} > /dev/null 2>&1"
                logger.info(f"Stream URL: {streamUrl}")
            else:
                logger.error(f"Unsupported codec: {codec} for {rtsp}, stopping.")
                break

            try:
                p = Popen(cmd, shell=True)
                logger.info(f"Started streaming {rtsp} to {streamUrl}")
                p.wait()
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to start streaming: {e}")
        else:
            logger.warning(f"IP camera {host}:{port} is down. Retrying in 30 seconds...")
            time.sleep(30)

def getStreamUrl(ipcamId, codec, logger):
    """Get the stream URL from the server."""
    api_url = BASE_URI + f"/api/stream?id={ipcamId}&codec={codec}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {BEARER}"}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()["streamUrl"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching stream URL for {ipcamId}: {e}")
        return None

def listIpcam():
    """Fetch the list of IP cameras from the API."""
    api_url = BASE_URI + "/api/ipcam"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {BEARER}"}
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()["ipcam"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching IPCam list: {e}")
        return []

def loadEnv():
    """Load environment variables."""
    global LOCK
    global BASE_URI
    global BEARER
    load_dotenv("config/env.txt")
    LOCK = Lock()
    BASE_URI = str(getenv("BASE_URI"))
    BEARER = str(getenv("BEARER"))

def shutdown_handler(signal, frame):
    """Handle graceful shutdown."""
    logging.info("Shutting down gracefully...")
    sys.exit(0)

def main():
    """Main entry point of the script."""
    # Disable root logger's console output
    logging.basicConfig(level=logging.WARNING, handlers=[])
    
    loadEnv()
    signal.signal(signal.SIGINT, shutdown_handler)
    ipcams = listIpcam()
    if not ipcams:
        # Create a temporary logger for the initial message
        temp_logger = setup_logger("main")
        temp_logger.warning("No IP cameras found.")
        return

    jobs = []
    for ipcam in ipcams:
        ipCamId = ipcam["id"]
        rtsp = ipcam["rtsp"]
        time_limit = str(ipcam["time_limit"])
        host, port = getHostPort(rtsp)
        p = Process(target=streamIpcam, args=(ipCamId, host, port, rtsp, time_limit))
        jobs.append(p)
        p.start()

    # Wait for all processes to finish
    for p in jobs:
        p.join()

if __name__ == "__main__":
    main()
