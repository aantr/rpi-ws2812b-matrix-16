import json
import threading
from flask import Flask, request
import logging
from matrix import Matrix
from modes import *

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)


@app.route('/button_click', methods=['GET', 'POST'])
def button_click():
    js = json.loads(request.data)
    key = js['count'], int(js['hold'])
    if key in button_functions:
        button_functions[key].__call__()
    return 'ok'


def switch_mode_next():
    global states
    if not enabled:
        return
    states = states[1:] + states[:1]
    current = states[0]
    current.__init__()
    matrix.set_speed(current.speed)
    matrix.clear()
    matrix.send_frames()


def switch_mode_prev():
    global states
    if not enabled:
        return
    states = states[-1:] + states[:-1]
    current = states[0]
    current.__init__()
    matrix.set_speed(current.speed)
    matrix.clear()
    matrix.send_frames()


def switch_off_on():
    global enabled
    enabled = not enabled
    matrix.clear()
    matrix.send_frames()
    if not enabled:
        states[0].__init__()


button_functions = {
    (1, 1): switch_off_on,
    (1, 0): switch_mode_next,
    (2, 0): switch_mode_prev,
}


@app.route('/hue_add/<int:value>', methods=['GET', 'POST'])
def hue_add(value):
    FireState.HUE_ADD = value
    matrix.clear()
    matrix.send_frames()
    return 'ok'


enabled = True
states = [FireState(), MatrixState(), RainbowState(), StringState(), SnowState(), GifState()]


def get_state(*args, **kwargs):
    if enabled:
        return states[0].get_frame(*args, **kwargs)

    return Matrix.null_state


if __name__ == '__main__':
    local_host = Matrix.get_local_ip()
    local_port = 5000

    while True:
        suc = True
        # host, port = input('Custom ip (empty for default scan): ').strip(), 4792
        host, port = '', 4792
        if not host:
            print('Scanning...')
            host = Matrix.find_host()
            if not host or not Matrix.check_host(host, port):
                print('Cannot find ip in local network')
                suc = False
                exit()
        else:
            res = Matrix.check_host(host, port)
            if not res:
                print(f'"{host}:{port}" don`t respond')
                suc = False
        if suc:
            break
    matrix = Matrix(host, port, get_state)
    print(f'Host was found: {matrix.url_base}')
    matrix.clear()
    matrix.set_brightness(40)
    matrix.set_speed(255)
    matrix.set_button_callback(f'http://{local_host}:{local_port}/button_click')

    # Local server
    thread = threading.Thread(
        target=app.run,
        args=(local_host, local_port),
        kwargs={'debug': False},
        daemon=True)
    thread.start()

    matrix.run()
