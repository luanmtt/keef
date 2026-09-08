# ideas.md

## Parser de nomes de arquivos baixados

Os arquivos baixados do Soulseek vêm com nomes variados (ex: `09 - What Do You See_.mp3`, `2.03 - Lluvia.flac`). Seria útil renomear automaticamente para um formato consistente.

### Formato desejado

**Faixa individual:**
```
{música} - {artista}.ext
```

Exemplo:
```
Lluvia - Analog Africa.flac
```

**Faixa em álbum:**
```
{número}. {música} - {artista}.ext
```

Exemplo:
```
02. Lluvia - Analog Africa.flac
09. What Do You See - Wire.mp3
```

### Implementação sugerida

1. Extrair metadados do arquivo baixado (mutagen)
2. Se `track_number` existe → formato álbum
3. Se não → formato individual
4. Sanitizar caracteres especiais no nome
5. Resolver conflitos de nome (adicionar sufixo)

### Comando CLI

```bash
./keef rename downloads/keef/         # renomeia todos os arquivos
./keef rename downloads/keef/ --dry   # apenas mostra o que faria
```

### Edge cases

- Arquivos sem metadados → usar nome original
- Nomes muito longos → truncar com limite
- Caracteres proibidos no filesystem → sanitizar
- Colisões de nome → adicionar (1), (2), etc.
