import colorsys
import os
import random
import socket
import threading
import time
import requests
from PIL import Image
from flask import Flask, request, abort
import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)


class Matrix:
    host = '192.168.0.112'
    port = 4792
    url_base = f'http://{host}:{port}'
    url_animation = url_base + '/animation'
    url_speed = url_base + '/speed/{}'
    url_brightness = url_base + '/brightness/{}'
    url_clear = url_base + '/clear'
    url_button_callback = url_base + '/button_callback?url={}'

    print(f'Request to: {url_base}')

    packet_frames = 8
    base_delay = 0.5
    middle_frames = packet_frames * 3
    count = 0

    def __init__(self, get_state_cb):
        self.cb = get_state_cb

    def set_button_callback(self, url):
        self.safe_request(self.url_button_callback.format(url))

    def get_frames(self):
        frames = b''
        for i in range(self.packet_frames):
            matrix = self.cb(self.count)
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


def hsv2rgb(h, s, v):
    return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h, s, v))


@app.route('/button_click', methods=['GET', 'POST'])
def button_click():
    global states
    states = states[1:] + states[:1]
    current = states[0]
    matrix.set_speed(current.speed)

    matrix.clear()
    matrix.send_frames()
    return 'ok'
   

@app.route('/hue_add/<int:value>', methods=['GET', 'POST'])
def hue_add(value):
    FireState.HUE_ADD = value
    matrix.clear()
    matrix.send_frames()
    return 'ok'


class State:
    speed = 200

    def get_frame(self, idx):
        ...


class StringState(State):
    speed = 255

    def __init__(self):
        sym = open('font/sym.txt', encoding='utf8').read()
        self.font = {}
        im: Image.Image = Image.open('font/font16_arial.bmp')
        width = im.size[0] // len(sym)
        for i in range(len(sym)):
            cropped = im.crop((i * width, 0, width * (i + 1), 16))
            pix = cropped.load()
            start, end = 0, 4
            for x in range(cropped.width):
                filled = False
                for y in range(cropped.height):
                    if pix[x, y]:
                        filled = True
                if filled and not start:
                    start = x
                if filled:
                    end = x
            res = cropped.crop((start, 0, end + 1, 16))
            pix = res.load()
            self.font[sym[i]] = res.width + 2, [[1 if 1 <= x <= res.width and pix[x - 1, y] else 0
                                                 for x in range(res.width + 2)]
                                                for y in range(res.height)]

    def get_frame(self, idx):
        string = 'С новым годом!'.upper()
        color = hsv2rgb(idx % 255 / 255, 1, 1)
        m = [[(0, 0, 0) for _ in range(16)] for _ in range(16)]

        length = 16
        for i in string:
            length += self.font[i][0]

        start = 16 - (idx % length)
        for i in range(len(string)):
            w, sym = self.font[string[i]]
            for x in range(w):
                for y in range(len(sym)):
                    vx, vy = start + x, y
                    if 0 <= vx <= 15 and 0 <= vy <= 15 and sym[y][x]:
                        m[vy][vx] = color
                if start + x > 15:
                    break
            start += w
        return m


class SnowState(State):
    speed = 255

    def __init__(self):
        self.m_snow = [[(0, 0, 0) for _ in range(16)] for _ in range(16)]

    def get_frame(self, idx):
        self.m_snow.insert(0, [[255 if not random.randint(0, 32) else 0] * 3 for _ in range(16)])
        self.m_snow.pop(-1)

        return self.m_snow


class GifState(State):
    speed = 200

    def __init__(self):
        directory = 'gif/success'
        self.gifs = []
        for i in os.listdir(directory):
            if os.path.isdir(os.path.join(directory, i)):
                continue
            im = Image.open(os.path.join(directory, i))
            frames_gif = []
            im.seek(0)
            try:
                while True:
                    m = [[(0, 0, 0) for _ in range(16)] for _ in range(16)]
                    pix = im.convert().load()
                    w, h = im.size
                    for i in range(16):
                        for j in range(16):
                            if sum(pix[w // 16 * i, h // 16 * j]) < 250 * 3:
                                m[j][i] = pix[w // 16 * i, h // 16 * j]
                            # print(m[i][j])
                    frames_gif.append(m)
                    im.seek(im.tell() + 1)
            except EOFError:
                pass
            self.gifs.append(frames_gif)

        self.start = time.time()
        self.timeout = 1.5

    def get_frame(self, idx):
        if time.time() - self.start > self.timeout:
            self.start = time.time()
            self.gifs = self.gifs[1:] + self.gifs[:1]
        return self.gifs[0][idx % len(self.gifs[0])]


class RainbowState(State):
    speed = 255

    def get_frame(self, idx):
        k = 10
        speed = 4
        m = [[hsv2rgb((i * k + j * k + idx * speed) % 255 / 255, 1, 1) for i in range(16)] for j in range(16)]
        return m


class FireState(State):
    speed = 255
    HUE_ADD = 0
    HUE_MUL = 4

    def __init__(self):
        self.valueMask = [
            [32, 0, 0, 0, 0, 0, 0, 32, 32, 0, 0, 0, 0, 0, 0, 32],
            [64, 0, 0, 0, 0, 0, 0, 64, 64, 0, 0, 0, 0, 0, 0, 64],
            [96, 32, 0, 0, 0, 0, 32, 96, 96, 32, 0, 0, 0, 0, 32, 96],
            [128, 64, 32, 0, 0, 32, 64, 128, 128, 64, 32, 0, 0, 32, 64, 128],
            [160, 96, 64, 32, 32, 64, 96, 160, 160, 96, 64, 32, 32, 64, 96, 160],
            [192, 128, 96, 64, 64, 96, 128, 192, 192, 128, 96, 64, 64, 96, 128, 192],
            [255, 160, 128, 96, 96, 128, 160, 255, 255, 160, 128, 96, 96, 128, 160, 255],
            [255, 192, 160, 128, 128, 160, 192, 255, 255, 192, 160, 128, 128, 160, 192, 255]
        ]
        self.hueMask = [
            [1, 11, 19, 25, 25, 22, 11, 1, 1, 11, 19, 25, 25, 22, 11, 1],
            [1, 8, 13, 19, 25, 19, 8, 1, 1, 8, 13, 19, 25, 19, 8, 1],
            [1, 8, 13, 16, 19, 16, 8, 1, 1, 8, 13, 16, 19, 16, 8, 1],
            [1, 5, 11, 13, 13, 13, 5, 1, 1, 5, 11, 13, 13, 13, 5, 1],
            [1, 5, 11, 11, 11, 11, 5, 1, 1, 5, 11, 11, 11, 11, 5, 1],
            [0, 1, 5, 8, 8, 5, 1, 0, 0, 1, 5, 8, 8, 5, 1, 0],
            [0, 0, 1, 5, 5, 1, 0, 0, 0, 0, 1, 5, 5, 1, 0, 0],
            [0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0]
        ]
        self.matrixValue = [[0 for i in range(16)] for j in range(8)]
        self.line = [0 for _ in range(16)]
        self.m = [[(0, 0, 0) for i in range(16)] for j in range(16)]
        self.pcnt = 0
        self.generate_line()

    def generate_line(self):
        for i in range(16):
            self.line[i] = random.randint(64, 255)

    def shift_up(self):
        for y in range(15, 0, -1):
            for x in range(16):
                if y > 7:
                    continue
                self.matrixValue[y][x] = self.matrixValue[y - 1][x]
        for x in range(16):
            self.matrixValue[0][x] = self.line[x]

    def draw_frame(self, pcnt):
        for y in range(15, 0, -1):
            for x in range(16):
                if y < 8:
                    nextv = (((100 - pcnt) * self.matrixValue[y][x] +
                              pcnt * self.matrixValue[y - 1][x]) / 100) - \
                            self.valueMask[y][x]
                    color = hsv2rgb((self.HUE_ADD + self.hueMask[y][x]) / 255 * self.HUE_MUL,
                                    1,
                                    max(0, nextv) / 255)
                    self.m[15 - y][x] = color
                elif y == 8:
                    if random.randint(0, 20) == 0 and self.m[16 - y][x] != (0, 0, 0):
                        self.m[15 - y][x] = self.m[16 - y][x]
                    else:
                        self.m[15 - y][x] = (0, 0, 0)
                else:
                    if self.m[16 - y][x] != (0, 0, 0):
                        self.m[15 - y][x] = self.m[16 - y][x]
                    else:
                        self.m[15 - y][x] = (0, 0, 0)
        for x in range(16):
            color = hsv2rgb((self.HUE_ADD + self.hueMask[0][x]) / 255 * self.HUE_MUL,
                            1,
                            (((100 - pcnt) * self.matrixValue[0][x] +
                              pcnt * self.line[x]) / 100) / 255)
            self.m[15][x] = color

    def get_frame(self, idx):
        if self.pcnt >= 100:
            self.shift_up()
            self.generate_line()
            self.pcnt = 0
        self.draw_frame(self.pcnt)
        self.pcnt += 30
        return self.m


class MatrixState(State):
    speed = 255

    def __init__(self):
        self.m = [[(0, 0, 0) for i in range(16)] for j in range(16)]

    def get_frame(self, idx):
        for x in range(16):
            col = self.m[0][x]
            if col == (0, 0, 0) and random.randint(0, 32) == 0:
                self.m[0][x] = (0, 255, 0)
            elif col[1] < 32:
                self.m[0][x] = (0, 0, 0)
            else:
                self.m[0][x] = (0, self.m[0][x][1] - 32, 0)

        for x in range(16):
            for y in range(15):
                self.m[15 - y][x] = self.m[14 - y][x]

        return self.m


states = [FireState(), MatrixState(), RainbowState(), StringState(), SnowState(), GifState()]


def get_state(*args, **kwargs):
    return states[0].get_frame(*args, **kwargs)


if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', Matrix.port))
    name = s.getsockname()[0]
    port = 5000
    s.close()

    thread = threading.Thread(
        target=app.run,
        args=(name, port),
        kwargs={'debug': False},
        daemon=True)
    thread.start()

    matrix = Matrix(get_state_cb=get_state)
    matrix.clear()
    matrix.set_brightness(40)
    matrix.set_speed(255)
    matrix.set_button_callback(f'http://{name}:{port}/button_click')
    matrix.run()
