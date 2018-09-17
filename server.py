#!/usr/bin/python3
# -*- encoding: utf-8 -*-

import select
import socket
import re

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# Menores que 1024 são restritos ao SO
s.bind(('', 1026))
s.listen(5)
c_inputs = []
requests = {}

while True:
    rlist, wlist, xlist = select.select(c_inputs + [s], [], [])
    for client in rlist:
        
        if client == s:
            client, addr = s.accept()
            client.setblocking(False)
            c_inputs.append(client)
            requests[client] = b''
        else:
            methods = [b'GET', b'POST', b'HEAD', b'DELETE', b'PUT']
            requests[client] += client.recv(1500)
            request = requests[client]
            
            if b'\r\n\r\n' in request or b'\n\n' in request:
                method, path, body = request.split(b' ', 2)
                
                if method in methods:
                    if method == b'GET':
                        pattern = b'/(.+)?'
                        content = re.search(pattern, path)
                        if content.group(0) == b'/':
                            file_content = open('index.html', 'rb').read()
                            response_content = b'<html lang="en"><head><meta charset="utf8"></head><body>' + file_content + b'</body></html>'
                            status = b'200 OK'
                        elif content.group(1) is not None:
                            filename = str(content.group(1)).strip('b\"\'')
                            try:
                                response_content = open(f'{filename}', 'rb').read()
                                status = b'200 OK'
                            except IOError:
                                response_content = open('generic_error.html', 'rb').read()
                                status = b'404 Not Found'
                        else:
                            response_content = open('generic_error.html','rb').read()
                            status = b'404 Not Found'
                    elif method == b'POST':
                        pattern = b'filename=\"(.+)\"\r\n' \
                                  b'Content-Type: (.+)\r\n\r\n' \
                                  b'(.+\n)\r\n'
                        content = re.search(pattern, body)
            
                        if content is not None:
                            print("Filename: {}\nContent-Type: {}\nContent: {}".format(content.group(1), content.group(2), content.group(3)))
                            filename = str(content.group(1)).strip('b\"\'').replace('..', '')
                            new_file = open(f'./{filename}', 'wb')
                            new_file.write(content.group(3))
                            new_file.close()
                            response_content = b"Arquivo recebido com sucesso xD"
                            status = b"200 OK"
                        else:
                            response_content = open('try_again.html', 'rb').read()
                            status = b"403 Forbidden"
                    else:
                        response_content = open('generic_error.html', 'rb').read()
                        status = b'501 Not Implemented'

                else:
                    response_content = open('generic_error.html', 'rb').read()
                    status = b'400 Bad Request'

                response = b'HTTP/1.0 %s\r\nContent-Length: %d\r\n\r\n' % (status, len(response_content))
                response += response_content
                client.send(response)
                client.close()
                del requests[client]
                c_inputs.remove(client)
