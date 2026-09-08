# keef

CLI para atualização segura de bibliotecas musicais via Soulseek (backend slskd).

## Stack

Python 3.13, uv, Rich, Pydantic, httpx, mutagen, pytest.

## Instalação rápida

```bash
git clone https://github.com/luanmtt/keef.git
cd keef
uv sync
```

## Configuração do slskd

O keef usa o [slskd](https://slskd.org/) como backend Soulseek.

### Docker (recomendado)

```bash
docker run -d \
  --name slskd \
  --restart unless-stopped \
  -p 127.0.0.1:5030:5030 \
  -p 127.0.0.1:5031:5031 \
  -p 127.0.0.1:50300:50300 \
  -e SLSKD_REMOTE_CONFIGURATION=true \
  -v "$HOME/.local/share/slskd:/app" \
  slskd/slskd:latest
```

Depois, abra `http://127.0.0.1:5030` e configure:

1. Credenciais Soulseek (usuário/senha)
2. API key local com permissão `readwrite`
3. Compartilhamentos (pasta de músicas para upload)

### Binário

Baixe o binário em https://github.com/slskd/slskd/releases e execute:

```bash
./slskd
```

## Configuração do keef

Crie `.env.local` na raiz do projeto (não versionado):

```bash
KEEF_SLSKD_URL=http://127.0.0.1:5030
KEEF_SLSKD_TOKEN=sua-api-key-aqui
```

### Wrapper script

Para evitar carregar variáveis manualmente, use o wrapper `./keef`:

```bash
./keef status
./keef scan songs --output-dir outputs
./keef preview outputs/08-19-35/metadata.json --online --verbose
./keef install --plan outputs/08-19-35/plan.json --execute
```

Alternativamente, com `direnv` instalado:

```bash
echo 'source .env.local' > .envrc
direnv allow
```

## Fluxo de uso

### 1. Preparar músicas

Coloque suas músicas em `songs/`:

```
songs/
├── track individual.mp3        ← busca individual
└── Nome do Álbum/              ← agrupado como álbum (💿)
    ├── 01 Faixa Um.flac
    └── 02 Faixa Dois.flac
```

### 2. Escanear

```bash
./keef scan songs --output-dir outputs
```

Gera `outputs/DD-HH-MM/metadata.json` com metadados de todas as faixas.

### 3. Preview (pesquisa no Soulseek)

```bash
./keef preview outputs/08-19-35/metadata.json \
  --online \
  --verbose \
  --policy higher \
  --search-timeout 15
```

O preview:

- Busca cada faixa individualmente no Soulseek
- Usa fallback automático: `Título - Álbum, Artista` → `Título - Álbum` → `Título`
- Mostra 💿 para faixas de álbum com fonte recomendada
- Gera `plan.json` com candidatos aceitos

Políticas de qualidade:

- `higher` — bitrate maior que o local (padrão)
- `lower` — bitrate menor que o local
- `exact` — bitrate exato (use `--target-kbps`)

### 4. Instalar (download)

```bash
./keef install --plan outputs/08-19-35/plan.json --execute
```

O download vai para o diretório de downloads do slskd, subpasta `keef/`:

```
~/.local/share/slskd/downloads/keef/
├── track individual.mp3
└── Nome do Álbum/
    ├── 01 Faixa Um.flac
    └── 02 Faixa Dois.flac
```

Para mudar o destino:

```bash
./keef install --plan plan.json --execute --staging-dir minha-pasta
```

O monitoramento mostra:

- Tempo decorrido
- Taxa de transferência
- Arquivos completos / total
- Bytes acumulados

## Testes

```bash
uv run pytest
```
