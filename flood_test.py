import socket, time, struct

# Get real MAC of h1-eth0
import uuid
raw = open('/sys/class/net/h1-eth0/address').read().strip()
src_mac = bytes(int(x, 16) for x in raw.split(':'))

s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
s.bind(('h1-eth0', 0))
for i in range(10):
    pkt = b'\xff\xff\xff\xff\xff\xff' + src_mac + b'\x08\x00' + b'X'*20
    s.send(pkt)
    print(f'Sent broadcast {i+1} from {raw}')
    time.sleep(0.5)
