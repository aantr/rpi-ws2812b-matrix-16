import os
import socket
import time
import subprocess as sp


class Matrix:
    packet_frames = 1
    delay = 0.01
    count = 0
    null_state = [[(0, 0, 0) for _ in range(16)] for _ in range(16)]

    def __init__(self, host, port, get_state_cb):
        self.host = host
        self.port = port
        self.cb = get_state_cb

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

    def set_button_callback(self, url):
        self.sock.send(b'u' + bytes(url, encoding='utf8'))
        self.sock.recv(1024)

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
        self.sock.send(b'b' + bytes([value]))
        self.sock.recv(1024)

    def set_fps(self, value):
        self.sock.send(b'f' + bytes([value]))
        self.sock.recv(1024)

    def clear(self):
        self.sock.send(b'c')
        self.sock.recv(1024)

    def run(self):
        check = False
        while True:
            response = self.send_frames()
            time.sleep(self.delay)

    def send_frames(self):
        self.sock.send(b'a' + self.get_frames())
        res = self.sock.recv(1024)
        return res

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
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                s.send(b'/')
                data = s.recv(1024)
        except socket.error:
            return False
        res = len(data) > 0
        return bool(res)
