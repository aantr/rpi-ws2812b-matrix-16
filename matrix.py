import os
import socket
import time

import requests
import subprocess as sp


class Matrix:
    packet_frames = 8
    base_delay = 0.5
    middle_frames = packet_frames * 3
    count = 0
    null_state = [[(0, 0, 0) for _ in range(16)] for _ in range(16)]

    def __init__(self, host, port, get_state_cb):
        self.host = host
        self.port = port
        self.url_base = f'http://{host}:{port}'
        self.url_animation = self.url_base + '/animation'
        self.url_speed = self.url_base + '/speed/{}'
        self.url_brightness = self.url_base + '/brightness/{}'
        self.url_clear = self.url_base + '/clear'
        self.url_button_callback = self.url_base + '/button_callback?url={}'
        self.cb = get_state_cb

    def set_button_callback(self, url):
        self.safe_request(self.url_button_callback.format(url))

    def get_frames(self):
        frames = b''
        for i in range(self.packet_frames):
            matrix = self.cb(self.count)
            if not matrix:
                continue
            self.count += 1
            data = bytes(self.matrix_to_data(matrix))
            frames += data
        return frames

    def set_brightness(self, value):
        self.safe_request(self.url_brightness.format(value))

    def set_speed(self, value):
        self.safe_request(self.url_speed.format(value))

    def clear(self):
        self.safe_request(self.url_clear)

    def run(self):
        check = False
        while True:
            try:
                delay = self.base_delay
                if check:
                    response = requests.post(self.url_animation)
                    check = False
                else:
                    response = self.send_frames()
                queue = int(response.text)
                if queue < self.middle_frames:
                    delay /= 2
                if queue > self.middle_frames + self.packet_frames:
                    check = True
                # print(queue, delay, check)

                time.sleep(delay)
            except requests.exceptions.RequestException as e:
                input(str(e) + '\nPress enter to continue')
                time.sleep(self.base_delay)

    def send_frames(self):
        return requests.post(self.url_animation, self.get_frames())

    @staticmethod
    def safe_request(url, data=None):
        try:
            response = requests.post(url, data)
        except requests.exceptions.RequestException:
            return
        return response

    @staticmethod
    def matrix_to_data(matrix):
        data = []
        for i in range(16):
            for j in range(16):
                if i % 2 == 0:
                    data.extend([*matrix[15 - i][15 - j]])
                else:
                    data.extend([*matrix[15 - i][j]])
        return data

    @staticmethod
    def check_format_ip(s):
        suc = True
        parts = s.split(".")
        if len(parts) != 4:
            suc = False
        for item in parts:
            if not 0 <= int(item) <= 255:
                suc = False
        return suc

    @staticmethod
    def get_local_ip():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 0))
            local_host = s.getsockname()[0]
        if not Matrix.check_format_ip(local_host):
            raise ValueError('Cannot determine local ip address')
        return local_host

    @staticmethod
    def find_host():
        local_host = Matrix.get_local_ip()
        iprange = f'{local_host[:local_host.rfind(".")]}.0/24'
        cmd = ['nmap', '-sP', iprange]
        out, err = sp.Popen(cmd, shell=True, stdout=sp.PIPE, stderr=sp.PIPE, encoding='utf8').communicate(timeout=10)
        print(out, err)
        prev_ip = None
        for line in out.split('\n'):
            line = line.strip()
            s = 'scan report for '
            f = line.find(s)
            if f != -1:
                if line.find(')') > line.find('('):
                    ip = line[line.find('(') + 1: line.find(')')].strip()
                else:
                    ip = line[f + len(s):].strip()
                if Matrix.check_format_ip(ip):
                    prev_ip = ip
            s = 'MAC Address: '
            f = line.find(s)
            if f != -1:
                mac = line[f + len(s):f + len(s) + 17]
                ip = prev_ip
                if mac.startswith('B8:27:EB'):
                    return ip
        return False

    @staticmethod
    def check_host(host, port):
        m = Matrix(host, port, None)
        res = m.safe_request(m.url_base)
        return bool(res)
