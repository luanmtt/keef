# keef 🚬🎵

update sua biblioteca musical com Soulseek usando uma interface CLI.

## Desenvolvimento

O ambiente oficial do projeto fica em `.keef`. Com direnv instalado, o
`.envrc` carrega automaticamente a variável definida em `.uv_env`:

```bash
direnv allow
uv sync
```

Sem direnv, carregue a variável manualmente:

```bash
set -a
source .uv_env
set +a
uv sync
```

Para verificar a instalação:

```bash
uv run keef --help
```

## Status do slskd

O keef usa o slskd como backend Soulseek. O slskd pode ser executado por
binário nativo ou Docker.

- Site: https://slskd.org/
- Código e releases: https://github.com/slskd/slskd

### Inicialização com Docker

```bash
docker run -d \
  --name slskd \
  -p 127.0.0.1:5030:5030 \
  -p 127.0.0.1:5031:5031 \
  -p 127.0.0.1:50300:50300 \
  -e SLSKD_REMOTE_CONFIGURATION=true \
  -v "$HOME/.local/share/slskd:/app" \
  slskd/slskd:latest
```

Depois, abra `http://127.0.0.1:5030` e configure separadamente as credenciais
Soulseek, o diretório de downloads e uma API key local com permissão de leitura
e escrita. Não exponha essas portas diretamente à internet.

### Inicialização por binário

Baixe o arquivo correspondente ao seu sistema na página de releases, extraia e
execute o binário `slskd`. A configuração será criada no diretório de dados do
usuário. Consulte a documentação oficial antes de expor o serviço ou alterar
as configurações de HTTPS.

### Configuração do keef

O token da API deve ser fornecido somente por ambiente local. Não use `--token`
nem grave o token em arquivos versionados:

```bash
set -a
source .env.local
set +a
uv run keef status
```

Exemplo de `.env.local` — mantenha este arquivo local e com permissões restritas:

```bash
KEEF_SLSKD_URL=http://127.0.0.1:5030
KEEF_SLSKD_TOKEN=<api-key-local>
```

O comando consulta as rotas `/api/v0/application` e `/api/v0/server`. Nesta
fase ele apenas verifica conectividade e estado; não pesquisa nem baixa
arquivos.

## Instalação single-track

Para testar uma música sem alterar a biblioteca original:

```bash
uv run keef install <track.mp3>
```

O comando usa dry-run por padrão. Para solicitar um download, informe uma
pasta de staging fora da biblioteca e habilite explicitamente a execução:

```bash
uv run keef install <track.mp3> \
  --staging-dir <staging-directory> \
  --execute
```

O arquivo original nunca é sobrescrito por este comando.

## Parsing de uma biblioteca

Para ler todos os MP3s de um diretório e gerar um relatório temporal:

```bash
uv run keef scan <library-directory>
```

O relatório será salvo em `outputs/DD/MM-HH-mm/metadata.json`. O comando
apenas lê os arquivos; não acessa o slskd e não inicia downloads.

## Preview batch

Para visualizar um plano de atualização sem iniciar downloads:

```bash
uv run keef preview outputs/DD/MM-HH-mm/metadata.json
```

Por padrão, o preview é offline e apenas valida o relatório. Para pesquisar
candidatos no slskd, use `--online`:

```bash
uv run keef preview outputs/DD/MM-HH-mm/metadata.json \
  --online \
  --policy higher
```

As políticas disponíveis são `higher`, `lower` e `exact`. O preview nunca
solicita downloads.

Quando uma instalação é executada com `--execute`, o keef exibe o
identificador e o estado retornados pelo slskd. O estado detalhado pode ser
consultado pela API em
`/api/v0/transfers/downloads/{username}/{download_id}`.

## Testes

```bash
uv run pytest
```
