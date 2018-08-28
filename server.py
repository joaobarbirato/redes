#!/bin/python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Menores que 1024 são restritos ao SO
s.bind(('', 1025))
s.listen(5)
while True:
    client, addr = s.accept()
    client.send(b'HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n <h1>Hello!</h1>')
    client.close()
