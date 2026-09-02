# keef 🚬🎵

CLI para atualizar uma biblioteca musical com segurança, usando o slskd como
backend Soulseek e Rich como interface inicial.

## Desenvolvimento

O ambiente oficial do projeto fica em `.keef`:

```bash
UV_PROJECT_ENVIRONMENT=.keef uv sync
```

Para verificar a instalação:

```bash
UV_PROJECT_ENVIRONMENT=.keef uv run keef --help
```

## Status do slskd

Configure a URL da API e, se necessário, o token:

```bash
export KEEF_SLSKD_URL=http://127.0.0.1:5030
export KEEF_SLSKD_TOKEN=seu-token
UV_PROJECT_ENVIRONMENT=.keef uv run keef status
```

Também é possível passar a URL diretamente:

```bash
UV_PROJECT_ENVIRONMENT=.keef uv run keef status --url http://127.0.0.1:5030
```

O comando consulta as rotas `/api/v0/application` e `/api/v0/server`. Nesta
fase ele apenas verifica conectividade e estado; não pesquisa nem baixa
arquivos.

## Testes

```bash
UV_PROJECT_ENVIRONMENT=.keef uv run pytest
```
