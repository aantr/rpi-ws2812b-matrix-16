import json
import os
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
    js = {'count': request.args.get('count', type=int, default=1),
          'hold': request.args.get('hold', type=int, default=0)}
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
    matrix.send_frames(clear=True, fps=current.speed)


def switch_mode_prev():
    global states
    if not enabled:
        return
    states = states[-1:] + states[:-1]
    current = states[0]
    current.__init__()
    matrix.send_frames(clear=True, fps=current.speed)


def switch_off_on():
    global enabled
    enabled = not enabled
    matrix.send_frames(clear=True)
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
    port = 4792

    saved_host = 'host.txt'
    if not os.path.exists(saved_host):
        open(saved_host, 'w')
    host = open(saved_host, 'r', encoding='utf8').read()
    print(f'Request to "{host}"')
    if not Matrix.check_host(host, port):
        while True:
            print('Scanning...')
            host = Matrix.find_host()
            if not host:
                print('Cannot find ip in local network')
                host = input('Custom ip (empty for scan): ').strip()
                if host:
                    break
            else:
                break
    if not Matrix.check_host(host, port):
        print(f'"{host}" don`t respond')
        exit()
    open(saved_host, 'w', encoding='utf8').write(host)
    matrix = Matrix(host, port, get_state)
    print(f'Host was found: {matrix.url_base}')
    matrix.clear()
    matrix.set_brightness(150)
    matrix.set_fps(90)
    matrix.set_button_callback(f'http://{local_host}:{local_port}/button_click')

    # Local server
    thread = threading.Thread(
        target=app.run,
        args=(local_host, local_port),
        kwargs={'debug': False},
        daemon=True)
    thread.start()

    matrix.run()
