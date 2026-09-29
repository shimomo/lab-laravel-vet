"""Drive an interactive command through a pseudo terminal.

Usage: python3 drive.py <cwd> <log> <steps> -- <command...>
  steps: 'pattern=>KEYS;pattern=>KEYS', KEYS joined with '+': DOWN, UP, ENTER, SPACE, ESC, CTRLC
Prints the ANSI-stripped transcript to <log> and the exit status to stdout.
"""
import fcntl
import os
import pty
import re
import select
import struct
import sys
import termios
import time

KEYS = {'DOWN': b'\x1b[B', 'UP': b'\x1b[A', 'ENTER': b'\r', 'SPACE': b' ', 'ESC': b'\x1b', 'CTRLC': b'\x03'}
ANSI = re.compile(rb'\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[()][A-Za-z0-9]|\x1b[=>78]|\r')

cwd, log_path, spec = sys.argv[1], sys.argv[2], sys.argv[3]
command = sys.argv[sys.argv.index('--') + 1:]
steps = [tuple(step.split('=>', 1)) for step in spec.split(';') if step]

pid, fd = pty.fork()
if pid == 0:
    os.chdir(cwd)
    os.execvp(command[0], command)

fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 60, 140, 0, 0))
transcript = b''


def pump(timeout: float) -> bool:
    global transcript
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return True
    try:
        data = os.read(fd, 65536)
    except OSError:
        return False
    if not data:
        return False
    transcript += data
    return True


def plain() -> bytes:
    return ANSI.sub(b'', transcript)


alive = True
for pattern, keys in steps:
    deadline = time.time() + 600
    seen_at = len(plain())
    while alive and time.time() < deadline and pattern.encode() not in plain():
        alive = pump(0.2)
    if not alive or pattern.encode() not in plain():
        print('step not reached: %r' % pattern)
        break
    time.sleep(0.8)
    for key in keys.split('+'):
        os.write(fd, KEYS[key])
        time.sleep(0.4)

while alive:
    alive = pump(0.5)

_, status = os.waitpid(pid, 0)
with open(log_path, 'wb') as log:
    log.write(plain())
print('exit=%d' % os.waitstatus_to_exitcode(status))
