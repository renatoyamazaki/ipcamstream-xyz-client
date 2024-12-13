#!/usr/bin/env python3

import socket
import requests
from subprocess import Popen
from multiprocessing import Process, Lock
from os import getenv
from dotenv import load_dotenv
import subprocess

def checkHostPort(ip, port, timeout=5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except:
        return False
    finally:
        s.close()

def getHostPort(rtsp):
    s = rtsp
    if s.rfind('@') < 0:
        r = s.split('/')[2].split('@')[0].split(':')
    else:
        r = s.split('/')[2].split('@')[1].split(':')
    return r[0], r[1]

def check_codec(rtsp_url):
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
        print(f"Error checking codec: {e}")
        return None

def streamIpcam(ipcamId, host, port, rtsp, time_limit):
    while True:
        cam_on = checkHostPort(host, port)
        if cam_on:
            codec = check_codec(rtsp)
            if not codec:
                print(f"Could not determine codec for {rtsp}")
                break

            streamUrl = getStreamUrl(ipcamId, codec)
            # Transform streamUrl for HLS if codec is H.265
            if codec == "hevc":
                parts = streamUrl.rsplit('/', 1)
                streamUrlHls = parts[0] + '/stream.m3u8'
                # H.265 (HEVC) command
                cmd = (
                    f"ffmpeg -timeout 5 -t {time_limit} -i {rtsp} -c:v copy -f hls "
                    f"-method PUT -hls_time 1 -hls_playlist_type event -http_persistent 1 '{streamUrlHls}' > config/h265.log 2>&1"
                )
                print(f"Stream URL (HLS): {streamUrlHls}")
                p = Popen("sleep 30", shell=True)
            elif codec == "h264":
                # H.264 command
                cmd = (
                    f"ffmpeg -t {time_limit} -nostdin -timeout 5000000 -i {rtsp} "
                    f"-vcodec copy -acodec copy -f flv {streamUrl} > config/h264.log 2>&1"
                )
                print(f"Stream URL: {streamUrl}")
                p = Popen("sleep 30", shell=True)
            else:
                print(f"Unsupported codec: {codec} for {rtsp}")
                break

            p = Popen(cmd, shell=True)
            print(f"Started stream from {host}:{port} {rtsp}")
        else:
            print(f"IP camera not up, sleeping 30 seconds...")
            p = Popen("sleep 30", shell=True)
        p.wait()

def getStreamUrl(ipcamId, codec):
    api_url = BASE_URI + "/api/stream?id=" + str(ipcamId) + "&codec=" + codec
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + BEARER}
    response = requests.get(api_url, headers=headers)
    res = response.json()
    return res["streamUrl"]

def listIpcam():
    api_url = BASE_URI + "/api/ipcam"
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + BEARER}
    response = requests.get(api_url, headers=headers)
    res = response.json()
    return res["ipcam"]

def loadEnv():
    global LOCK
    global BASE_URI
    global BEARER
    load_dotenv("config/env.txt")
    LOCK = Lock()
    BASE_URI = str(getenv("BASE_URI"))
    BEARER = str(getenv("BEARER"))

def main():
    loadEnv()
    ipcams = listIpcam()
    jobs = []
    for ipcam in ipcams:
        ipCamId = ipcam["id"]
        rtsp = ipcam["rtsp"]
        time_limit = str(ipcam["time_limit"])
        host, port = getHostPort(rtsp)
        p = Process(target=streamIpcam, args=(ipCamId, host, port, rtsp, time_limit))
        jobs.append(p)
        p.start()

if __name__ == "__main__":
    main()

