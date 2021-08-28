import logging
import threading

from flask import Flask, request, abort
import time
import socket

import RPi.GPIO as GPIO
import neopixel
import board

import requests

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)

button_pin = 23
GPIO.setwarnings(False)
# GPIO.setmode(GPIO.BOARD)
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Strip
pixel_pin = board.D18
num_pixels = 256
ORDER = neopixel.GRB

pixels = neopixel.NeoPixel(
    pixel_pin, num_pixels, brightness=0.1, auto_write=False, pixel_order=ORDER
)
pixels.fill((0, 0, 0))
pixels.show()

speed_value = 255
max_delay = 0.4
min_delay = 0.01
frames = []
start = None
timeout = 3
cleared = True
button_callback = None
running = True


@app.route('/', methods=['GET', 'POST'])
def index():
    return 'ok'


@app.route('/shutdown', methods=['GET', 'POST'])
def shutdown():
    global running
    running = False
    return 'ok'


@app.route('/brightness/<int:value>', methods=['GET', 'POST'])
def brightness(value):
    if value < 0:
        value = 0
    if value > 255:
        value = 255
    pixels.brightness = value / 255
    return 'ok'


@app.route('/speed/<int:value>', methods=['GET', 'POST'])
def speed(value):
    global speed_value
    if value < 0:
        value = 0
    if value > 255:
        value = 255
    speed_value = value
    return 'ok'


@app.route('/clear', methods=['GET', 'POST'])
def clear():
    global frames
    frames = []
    return 'ok'


@app.route('/animation', methods=['GET', 'POST'])
def animation():
    global frames, cleared, start
    frames.extend(request.data)
    cleared = False
    start = None
    return str(len(frames) // (256 * 3))


@app.route('/button_callback', methods=['GET', 'POST'])
def button_callback():
    global button_callback
    url = request.args.get('url', default=None)
    if url is None:
        return abort(400)
    button_callback = url
    return 'ok'


pressed_time = None
click_count = 0
last_hold = False
last_click_time = None
pressed = bool(GPIO.input(button_pin))

hold_timeout = 0.5
click_timeout = 0.3


def button_rising(channel):
    global pressed_time, pressed
    if not button_callback:
        return
    if pressed:
        pressed = not pressed
        return button_falling(channel)
    pressed = not pressed
    pressed_time = time.time()


def button_falling(channel):
    global pressed_time, last_hold, last_click_time, click_count
    if not button_callback:
        return
    if pressed_time is None:
        return
    hold_time = time.time() - pressed_time
    pressed_time = None
    last_hold = hold_time > hold_timeout
    last_click_time = time.time()
    click_count += 1


GPIO.add_event_detect(button_pin, GPIO.BOTH, callback=button_rising)


def button_cycle():
    global click_count, pressed_time, last_hold
    while True:
        extra = False
        if pressed_time is not None:
            hold_time = time.time() - pressed_time
            if hold_time > hold_timeout:
                pressed_time = None
                click_count += 1
                last_hold = True
                extra = True

        if click_count > 0:
            js = {'count': click_count, 'hold': last_hold}
            if (extra or time.time() - last_click_time > click_timeout) and pressed_time is None:
                click_count = 0
                if button_callback:
                    try:
                        requests.post(button_callback, json=js)
                    except requests.RequestException:
                        ...
        time.sleep(0.1)


def animate():
    global frames, start, cleared
    while running:
        try:
            if len(frames) >= 256 * 3:
                for i in range(256):
                    pixels[i] = frames[i * 3], frames[i * 3 + 1], frames[i * 3 + 2]
                frames = frames[768:]
                pixels.show()
            else:
                if start is None:
                    start = time.time()
                if not cleared:
                    if time.time() - start >= timeout:
                        pixels.fill((0, 0, 0))
                        pixels.show()
                        cleared = True
        except Exception as e:
            print('Exception in animate:', e)
        time.sleep(min_delay + (1 - speed_value / 255) * max_delay)


if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 4792))
    name = s.getsockname()[0]
    s.close()

    thread = threading.Thread(
        target=app.run,
        args=(name, 4792),
        kwargs={'debug': False},
        daemon=True)
    thread.start()
    time.sleep(0.5)

    thread_button = threading.Thread(
        target=button_cycle,
        daemon=True)
    thread_button.start()
    time.sleep(0.5)

    try:
        animate()
    except KeyboardInterrupt:
        ...
    print('exit...')
    pixels.fill((0, 0, 0))
    pixels.show()
    GPIO.cleanup()
