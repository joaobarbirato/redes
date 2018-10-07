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
curl -X POST -F 'nomedoarquivo=@caminhodoarquivo' http://localhost:1026
```

Para ver o conteúdo de arquivos enviados:
```shell
curl http://localhost:1026/<arquivo>
```
ou acesse http://localhost:1026/<arquivo> no browser.
