# MTG Proxy Printer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Ferramenta educacional para criação de proxies de Magic: The Gathering para playtesting.**

## Aviso Importante

Este projeto é **puramente educacional** e tem como único objetivo facilitar a criação de proxies para playtesting antes de investir em cartas originais. As cartas geradas por esta ferramenta **não devem ser usadas em competições oficiais** e não possuem valor como cartas autênticas.

O uso de proxies em torneios oficiais é **estritamente proibido** pela Wizards of the Coast. Esta ferramenta não apoia nem incentiva qualquer forma de falsificação ou uso fraudulento de cartas.

## Sobre o Projeto

O MTG Proxy Printer é uma ferramenta que gera PDFs prontos para impressão a partir de uma lista de cartas de Magic: The Gathering. Utiliza a API pública da [Scryfall](https://scryfall.com/) como fonte de dados e imagens.

### Funcionalidades

- Geração de PDFs com cartas em formato padrão (63mm x 88mm)
- Suporte a impressão duplex (frente e verso)
- Cache local de imagens para uso offline
- Páginas de teste para alinhamento e escala
- Configuração personalizável via arquivo YAML
- Interface de linha de comandos (CLI)

### Para que serve?

- **Playtesting**: Teste seus decks antes de investir em cartas originais
- **Aprendizado**: Ideal para novos jogadores que estão começando no Magic
- **Prototipação**: Crie e teste novos decks rapidamente
- **Preservação**: Mantenha suas cartas originais em bom estado

## Instalação

### Requisitos

- Python 3.11 ou superior
- Pip (gerenciador de pacotes do Python)

### Instalação via pip

```bash
# Clone o repositório
git clone https://github.com/Padokazzz/mtg-proxy-printer.git
cd mtg-proxy-printer

# Instale as dependências
pip install -e ".[dev]"
```

### Instalação via requirements.txt

```bash
# Clone o repositório
git clone https://github.com/Padokazzz/mtg-proxy-printer.git
cd mtg-proxy-printer

# Crie um ambiente virtual (recomendado)
python -m venv venv
venv\Scripts\activate  # Windows
# ou
source venv/bin/activate  # Linux/Mac

# Instale as dependências
pip install -r requirements.txt
```

## Uso

### Preparando sua lista de cartas

Crie um arquivo `deck.txt` com o nome das cartas, uma por linha:

```
Lightning Bolt
Counterspell
Sol Ring
Command Tower
```

### Gerando o PDF

```bash
python -m mtg_proxy generate --deck deck.txt --config config.yaml --output saida/
```

### Outros comandos disponíveis

```bash
# Validar o deck sem consultar a API
python -m mtg_proxy check --deck deck.txt

# Baixar e cachear imagens das cartas
python -m mtg_proxy download --deck deck.txt --config config.yaml

# Gerar página de teste de alinhamento
python -m mtg_proxy duplex-test

# Gerar página de teste de escala (50mm)
python -m mtg_proxy scale-test
```

## Configuração

Edite o arquivo `config.yaml` para personalizar as configurações:

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

## Estrutura do Projeto

```
mtg-proxy-printer/
├── src/mtg_proxy/         # Código fonte principal
│   ├── cli.py            # Interface de linha de comandos
│   ├── config.py         # Carregamento de configurações
│   ├── deck/             # Parser de decks
│   ├── images/           # Processamento de imagens
│   ├── layout/           # Layout das páginas
│   ├── pdf/              # Geração de PDFs
│   └── scryfall/         # Cliente da API Scryfall
├── tests/                # Testes unitários
├── docs/                 # Documentação
├── config.yaml           # Configurações padrão
└── requirements.txt      # Dependências
```

## Desenvolvimento

### Executando testes

```bash
pytest
```

### Contribuindo

1. Faça um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas alterações (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## Créditos

- [Scryfall](https://scryfall.com/) - API de imagens e dados de cartas
- [Magic: The Gathering](https://magic.wizards.com/) - Wizards of the Coast

## Aviso Legal

MTG Proxy Printer é um projeto independente e não é afiliado, endossado ou patrocinado pela Wizards of the Coast ou pela Hasbro, Inc. Magic: The Gathering é uma marca registrada da Wizards of the Coast.

Este software é fornecido "como está", sem garantia de qualquer tipo. O uso é responsável do usuário.

---

**Lembre-se**: Cartas geradas por esta ferramenta são apenas para fins de teste e aprendizado. Respeite sempre as regras dos torneios e compre cartas originais para uso em competições oficiais.
