import threading

from flask import Flask, request, abort
import time
import board
import neopixel
import socket
import RPi.GPIO as GPIO
import requests

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


def button_rising(channel):
    if button_callback:
        try:
            requests.post(button_callback)
        except requests.RequestException:
            ...


GPIO.add_event_detect(button_pin, GPIO.RISING, callback=button_rising)


def animate():
    global frames, start, cleared
    while True:
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
            print(e)
        time.sleep(min_delay + (1 - speed_value / 255) * max_delay)


def socket_cycle():
    print('Started socket thread')
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    s.bind(('', 4793))
    while True:
        data, address = s.recvfrom(1024)
        print(data, address)
        if data == b'matrix_rpi':
            s.sendto(b'matrix_rpi', address)


if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 4792))
    name = s.getsockname()[0]
    s.close()

    # thread_socket = threading.Thread(
    #     target=socket_cycle,
    #     daemon=True)
    # thread_socket.start()
    # time.sleep(0.5)
    thread = threading.Thread(
        target=app.run,
        args=(name, 4792),
        kwargs={'debug': False},
        daemon=True)
    thread.start()
    time.sleep(0.5)

    try:
        animate()
    except KeyboardInterrupt:
        print('exit...')
    pixels.fill((0, 0, 0))
    pixels.show()
    GPIO.cleanup()
