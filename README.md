# Cliente-Servidor
Trabalho da disciplina de Redes de Computadores


Para a primeira etapa do projeto de Redes de Computadores foi desenvolvido um servidor utilizando protocolo HTTP que aceita o upload de arquivos, implementado na linguagem Python.

Para rodar o servidor:
- Clonar o repositório
```shell
git clone https://github.com/joaobarbirato/redes
```

- Executar:
```shell
./server.py
```

Para adicionar arquivos:
```shell
curl -F 'nomedoarquivo=@caminhodoarquivo' http://localhost:1026
```
