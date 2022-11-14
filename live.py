#!/usr/bin/env python3

import socket
import requests
from subprocess import Popen
from multiprocessing import Process, Lock
from os import getenv
from dotenv import load_dotenv


def checkHostPort (ip, port, timeout=5):
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


def getHostPort (rtsp):
    s = rtsp
    if s.rfind('@') < 0:
        r = s.split('/')[2].split('@')[0].split(':')
    else:
        r = s.split('/')[2].split('@')[1].split(':')
    return r[0], r[1]


def streamIpcam (ipcamId, host, port, rtsp):
    while True:
        cam_on = checkHostPort(host, port)
        if (cam_on):
            streamUrl = getStreamUrl(ipcamId)
            cmd = "ffmpeg -t 39600 -nostdin -stimeout 5000000 -i " + rtsp + " -vcodec copy -acodec copy -f flv " + streamUrl + " > /dev/null 2>&1 "
            p = Popen(cmd, shell=True)
            print(f'started stream from {host}:{port} {rtsp}')
            print(f'stream url "{streamUrl}"')
        else:
            print(f'Ipcam not up, sleeping 10 seconds...')
            p = Popen("sleep 10", shell = True)
        p.wait()


def getStreamUrl (ipcamId):
    api_url = BASE_URI + "/api/stream?id=" + ipcamId
    headers = {"Content-Type":"application/json", "Authorization": "Bearer " + BEARER }
    with LOCK:
        response = requests.get(api_url, headers=headers)
    res = response.json()
    return res["streamUrl"]


def listIpcam ():
    api_url = BASE_URI + "/api/ipcam"
    headers = {"Content-Type":"application/json", "Authorization": "Bearer " + BEARER }
    response = requests.get(api_url, headers=headers)
    res = response.json()
    return res["ipcam"]


def loadEnv ():
    global LOCK
    global BASE_URI
    global BEARER
    load_dotenv('config/env.txt')
    LOCK = Lock()
    BASE_URI = str(getenv('BASE_URI'))
    BEARER = str(getenv('BEARER'))


def main():
    loadEnv()
    ipcams = listIpcam()
    jobs = []
    for ipcam in ipcams:
        ipCamId = ipcam["id"]
        rtsp = ipcam["rtsp"]
        host, port = getHostPort(rtsp)
        p = Process(target=streamIpcam, args=(ipCamId, host, port,rtsp,))
        jobs.append(p)
        p.start()


if __name__ == "__main__":
    main()
