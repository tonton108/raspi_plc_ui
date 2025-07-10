import requests
import socket
import uuid

def get_mac():
    return ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,8)][::-1])

data = {
    "ip": "192.168.0.101",
    "mac_address": get_mac(),
    "hostname": socket.gethostname()
}

r = requests.post("http://<FlaskサーバーIP>:5000/api/register", json=data)
print(r.json())
