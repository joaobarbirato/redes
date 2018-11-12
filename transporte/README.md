# Camada de transporte
Trabalho da disciplina de Redes de Computadores


- Clonar o repositório

```shell
git clone https://github.com/joaobarbirato/redes
cd transporte/
```

- Antes de usar, execute o seguinte comando para evitar que o Linux feche as conexões TCP abertas por este programa:

```shell
sudo iptables -I OUTPUT -p tcp --tcp-flags RST RST -j DROP
```

- Execução

```shell
sudo python tcp_new.py
```

- Para testar:

```shell
wget localhost:7000
```
