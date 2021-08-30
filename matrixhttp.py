import os
import socket
import time

import requests
import subprocess as sp


class Matrix:
    packet_frames = 16
    send_time = 1.5
    delay = 1
    count = 0
    null_state = [[(0, 0, 0) for _ in range(16)] for _ in range(16)]

    def __init__(self, host, port, get_state_cb):
        self.host = host
        self.port = port
        self.url_base = f'http://{host}:{port}'
        self.url_animation = self.url_base + '/animation'
        self.url_fps = self.url_base + '/fps/{}'
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

    def set_fps(self, value):
        self.safe_request(self.url_fps.format(value))

    def clear(self):
        self.safe_request(self.url_clear)

    def run(self):
        check = False
        while True:
            try:
                if check:
                    response = requests.post(self.url_animation)
                    check = False
                else:
                    response = self.send_frames()
                server_frames, server_delay = map(float, response.text.split(','))
                time_s = server_frames * server_delay
                if time_s > self.delay + 0.5:
                    check = True
                time.sleep(self.delay)
            except requests.exceptions.RequestException as e:
                exit(str(e))

    def update_packet_frames(self, response):
        server_frames, server_delay = map(float, response.text.split(','))
        self.packet_frames = int(self.send_time / server_delay)

    def send_frames(self, **kwargs):
        if kwargs:
            self.update_packet_frames(
                requests.post(
                    self.url_animation + f'?{"&".join([f"{k}={int(v)}" for k, v in kwargs.items()])}',
                    self.get_frames())
            )
            response = requests.post(self.url_animation, self.get_frames())
        else:
            response = requests.post(self.url_animation + f'?{"&".join([f"{k}={int(v)}" for k, v in kwargs.items()])}',
                                     self.get_frames())
            self.update_packet_frames(response)
        return response

    @staticmethod
    def safe_request(url, data=None, **kwargs):
        try:
            response = requests.post(url, data=data, **kwargs)
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
        try:
            suc = True
            parts = s.split(".")
            if len(parts) != 4:
                suc = False
            if parts[:2] != ['192', '168']:
                suc = False
            for item in parts:
                if not 0 <= int(item) <= 255:
                    suc = False
            return suc
        except Exception:
            return False

    @staticmethod
    def get_local_ip():
        ips = sorted([l for l in (
            [ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [
                [(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in
                 [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l])
        for addr in ips:
            addr = addr[0]
            if Matrix.check_format_ip(addr):
                return addr
        raise ValueError('Cannot determine local ip address')

    @staticmethod
    def find_host():
        local_host = Matrix.get_local_ip()
        iprange = f'{local_host[:local_host.rfind(".")]}.0/24'
        cmd = ['nmap', '-sP', iprange]
        out, err = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, encoding='utf8').communicate(timeout=30)
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
