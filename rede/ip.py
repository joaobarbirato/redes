# -*- coding: utf-8 -*-
import socket
import asyncio
import struct
from time import sleep as alan_turing

"""
```shell
    ip link set lo mtu 1500
```
"""

__MULTIPLIER = 10
__GOLD = b"C47170"
__PING_HEADER = b"\x45\x00\x00\x54\xb4\x76\x40\x00\x40\x01\x6b\x26"
__DATAGRAM = b"\x01\x01\x01\x01\x08\x00\xa4\xdb\x67\x9f \
            \x00\x06\xa5\xaa\xe1\x5b\x00\x00\x00\x00    \
            \xa5\xa5\x00\x00\x00\x00\x00\x00\x10\x11    \
            \x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b    \
            \x1c\x1d\x1e\x1f\x20\x21\x22\x23\x24\x25    \
            \x26\x27\x28\x29\x2a\x2b\x2c\x2d\x2e\x2f    \
            \x30\x31\x32\x33\x34\x35\x36\x37" + __GOLD * __MULTIPLIER + b"fim"
            
ETH_P_IP = 0x0800

# O endereço abaixo pode ser qualquer endereço fora da sua rede local.
# O sistema operacional vai utilizá-lo somente para determinar qual o próximo
# roteador para onde vai encaminhar o datagrama. Experimente trocar por um
# endereço pertencente à sua subrede local e veja o que acontece!
EXT_ADDR = ('127.0.0.1', 0)#open('my_addr.txt').read(), 0)

# Coloque abaixo o endereço IP do seu computador na sua rede local
my_ip = bytes(map(int, '127.0.0.1'.split('.')))

dicionario = {}

def send_ping(send_fd):
    #print('enviando ping: ', len(__PING_HEADER + my_ip + __DATAGRAM))
    # Exemplo de pacote ping (ICMP echo request) destinado a 1.1.1.1.
    # Veja que como estamos montando o cabeçalho IP, precisamos preencher
    # endereço IP de origem e de destino.
    send_fd.sendto(__PING_HEADER + my_ip + __DATAGRAM, EXT_ADDR)

    asyncio.get_event_loop().call_later(1, send_ping, send_fd)


def raw_recv(recv_fd):
    packet = recv_fd.recv(12000)
    version_trash, total_length, ident, flag_fragoffset, _, chksum, src_ip, dst_ip = struct.unpack('!HHHHHHII', packet[:20])

    # se eh ipv4 (teste de unidade)
    if not version_trash >> 12 == 4:
        print("muito estranho")
        return 0
    
    if str(ident) not in dicionario:
        dicionario[str(ident)] = [repr(packet)]
    else:
        dicionario[str(ident)].append(repr(packet))
    
    [print("id: ", key," quantos: ", len(value), end=", ") for key, value in dicionario.items()]
    print()
    alan_turing(1)

if __name__ == '__main__':
    # Segundo a manpage http://man7.org/linux/man-pages/man7/raw.7.html,
    # o raw socket com protocolo IPPROTO_RAW só pode ser usado para enviar
    # datagramas IP. Ao tentar receber datagramas por ele, nunca chega nada.
    send_fd = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)

    # Para receber existem duas abordagens. A primeira é a da etapa anterior
    # do trabalho, de colocar socket.IPPROTO_TCP, socket.IPPROTO_UDP ou
    # socket.IPPROTO_ICMP. Assim ele filtra só datagramas IP que contenham um
    # segmento TCP, UDP ou mensagem ICMP, respectivamente, e permite que esses
    # datagramas sejam recebidos. No entanto, essa abordagem faz com que o
    # próprio sistema operacional realize boa parte do trabalho da camada IP,
    # como remontar datagramas fragmentados. Para que essa questão fique a
    # cargo do nosso programa, é necessário uma outra abordagem: usar um socket
    # de camada de enlace, porém pedir para que as informações de camada de
    # enlace não sejam apresentadas a nós, como abaixo. Esse socket também
    # poderia ser usado para enviar pacotes, mas somente se eles forem quadros,
    # ou seja, se incluírem cabeçalhos da camada de enlace.
    recv_fd = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_P_IP))

    loop = asyncio.get_event_loop()
    loop.add_reader(recv_fd, raw_recv, recv_fd)
    asyncio.get_event_loop().call_later(1, send_ping, send_fd)
    loop.run_forever()
