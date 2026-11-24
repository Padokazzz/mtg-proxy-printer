# MTG Proxy Printer

Ferramenta de linha de comando em Python para gerar PDFs de cartas de **Magic: The Gathering** destinados a playtesting.

A partir de uma lista de cartas, o programa consulta dados e imagens na API pública da [Scryfall](https://scryfall.com/), organiza as cartas em páginas para impressão e permite ajustar dimensões, margens, espaçamento e configuração duplex.

> **Uso educacional e de playtesting.** Os materiais gerados não são cartas autênticas, não devem ser comercializados como tais e não são destinados a torneios oficiais.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

## Funcionalidades

- Geração de PDFs com dimensões de carta configuráveis.
- Layout para folhas A4.
- Suporte a impressão frente e verso.
- Cache local de imagens para reduzir consultas repetidas.
- Arquivo YAML para personalização das configurações.
- Comandos para validar listas e baixar imagens.
- Páginas de teste para conferir alinhamento e escala de impressão.

## Como funciona

```text
Lista de cartas
      │
      ▼
Parser e validação
      │
      ▼
Consulta à Scryfall
      │
      ▼
Cache e processamento de imagens
      │
      ▼
Cálculo do layout
      │
      ▼
Geração do PDF
```

## Tecnologias

- Python 3.11+
- Pillow para processamento de imagens.
- ReportLab para geração de PDFs.
- PyYAML para leitura das configurações.
- pytest para testes.

## Instalação

Clone o repositório:

```bash
git clone https://github.com/Padokazzz/mtg-proxy-printer.git
cd mtg-proxy-printer
```

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale o projeto e as dependências de desenvolvimento:

```bash
pip install -e ".[dev]"
```

## Uso

Crie um arquivo de texto com uma carta por linha:

```text
Lightning Bolt
Counterspell
Sol Ring
Command Tower
```

Gere o PDF:

```bash
python -m mtg_proxy generate --deck deck.txt --config config.yaml --output saida/
```

### Outros comandos

Validar a lista:

```bash
python -m mtg_proxy check --deck deck.txt
```

Baixar e armazenar imagens em cache:

```bash
python -m mtg_proxy download --deck deck.txt --config config.yaml
```

Gerar uma página para teste de impressão duplex:

```bash
python -m mtg_proxy duplex-test
```

Gerar uma página para conferir a escala:

```bash
python -m mtg_proxy scale-test
```

## Configuração

As opções de impressão ficam no arquivo `config.yaml`. Exemplo:

```yaml
print:
  paper: "A4"
  card_width_mm: 63
  card_height_mm: 88
  dpi_reference: 300

page:
  width_mm: 210
  height_mm: 297
  margin_mm: 5
  gap_mm: 2

duplex:
  enabled: true
  flip: "long_edge"
```

Ajuste as dimensões e a opção de inversão duplex de acordo com a impressora e o tipo de papel. Recomenda-se gerar e conferir uma página de teste antes de imprimir um conjunto completo.

## Estrutura do projeto

```text
src/mtg_proxy/
├── cli.py
├── config.py
├── deck/
├── images/
├── layout/
├── pdf/
└── scryfall/
tests/
docs/
config.yaml
requirements.txt
```

- `deck/`: leitura e validação das listas.
- `images/`: download, cache e processamento de imagens.
- `layout/`: cálculo da disposição das cartas nas páginas.
- `pdf/`: composição e exportação dos documentos.
- `scryfall/`: integração com a API de dados e imagens.

## Desenvolvimento

Execute os testes com:

```bash
pytest
```

Para contribuir:

1. Faça um fork do repositório.
2. Crie uma branch para sua alteração.
3. Implemente e teste a mudança.
4. Abra um Pull Request com a descrição do que foi alterado.

## Créditos e aviso legal

- [Scryfall](https://scryfall.com/): fonte de dados e imagens das cartas.
- [Magic: The Gathering](https://magic.wizards.com/): propriedade intelectual da Wizards of the Coast.

MTG Proxy Printer é um projeto independente, sem afiliação, endosso ou patrocínio da Wizards of the Coast ou da Hasbro. Magic: The Gathering é uma marca registrada de seus respectivos proprietários.

O software é fornecido "como está", sem garantias. O usuário é responsável por respeitar os direitos autorais, os termos dos serviços utilizados e as regras dos ambientes em que os materiais forem utilizados.

## Licença

Este projeto está licenciado sob a [MIT](LICENSE).
