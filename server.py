#!/usr/bin/python3
# -*- encoding: utf-8 -*-
"""
    server.py
    Código principal para o socket de servidor
"""
import select
import socket
import re
import os
from constants import *

# Definição da socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', SOCK_PORT))
s.listen(1)
s.setblocking(False)

c_inputs = []   # lista de clientes
requests = {}   # requisições

# Lista de métodos do protocolo HTTP
list_methods = [
        b'GET',
        b'POST',
        b'HEAD',
        b'DELETE',
        b'PUT'
    ]

def main():
    """
        main()
        Procedimento principal
    """
    while True:
        rlist, wlist, xlist = select.select(c_inputs + [s], [], [])
        for client in rlist:
            
            if client == s:
                client, addr = s.accept()
                client.setblocking(0)
                c_inputs.append(client)
                requests[client] = b''
            else:
                methods = list_methods
                requests[client] += client.recv(MAX_SIZE_MSG)
                request = requests[client]
                
                if b'\r\n\r\n' in request or b'\n\n' in request:
                    method, path, body = request.split(b' ', 2)
                    
                    if method in methods:
                        if method == b'GET' or method == b'HEAD':
                            pattern = b'/(.+)?'
                            content = re.search(pattern, path)
                            if content.group(0) == b'/':
                                file_dir = "files/"
                                file_list = os.listdir(file_dir)
                                file_content = open('templates/indexinit.html', 'rb').read()
                                for file in file_list:
                                    file_content += b'<a href=%s> %s <a><br>' % (str.encode(file), str.encode(file))
                                file_content += open('templates/indexend.html', 'rb').read() 
                                response_content = HTML_GEN_BEGIN + file_content + HTML_GEN_END
                                status = OK
                            elif content.group(1) is not None:
                                filename = str(content.group(1)).strip('b\"\'')
                                try:
                                    response_content = open(f'templates/fileinit.html', 'rb').read()
                                    response_content += open(f'./files/{filename}', 'rb').read()
                                    response_content += open(f'templates/fileend.html', 'rb').read()
                                    status = OK
                                except IOError:
                                    response_content = open('templates/generic_error.html', 'rb').read()
                                    status = NOT_FOUND
                            else:
                                response_content = open('templates/generic_error.html','rb').read()
                                status = NOT_FOUND
                        elif method == b'POST':
                            #content = re.search(RE_EXPECT, str(body))
                            filename = re.search(RE_FILE, body)

                            if filename is not None:
                                print("> Received new file: Filename: {}, Content-Type: {}, Content: {}".format(content.group('filename'), content.group('type'), content.group('content')))
                                filename = str(content.group('filename')).strip('b\"\'').replace('..', '')
                                new_file = open(f'./files/{filename}', 'wb')
                                new_file.write(content.group('content'))
                                new_file.close()
                                response_content = b'Arquivo recebido com sucesso xD'
                                status = OK
                            else:
                                response_content = open('templates/try_again.html', 'rb').read()
                                status = FORB
                        else:
                            response_content = open('templates/generic_error.html', 'rb').read()
                            status = NOT_IMPL
                    else:
                        response_content = open('templates/generic_error.html', 'rb').read()
                        status = BAD_REQ
                    
                    response = b'HTTP/1.0 %s\r\nContent-Length: %d\r\n\r\n' % (status, len(response_content))
                    if method is not b'HEAD':
                        response += response_content
                    client.send(response)
                    client.close()
                    print("> Req: ", request)
                    print("> Res: ", response)
                    del requests[client]
                    c_inputs.remove(client)


if __name__ == '__main__':
    print("> Running server socket at http://localhost:%d" % SOCK_PORT)
    main()
