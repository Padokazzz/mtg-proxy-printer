# Impressão de Proxies (MTG Proxy Printer)

Este guia evita o erro mais comum: **o PDF parece certo na tela, mas imprime
com tamanho ou alinhamento errado**.

## Antes de imprimir o deck

1. Imprima `saida/scale-test.pdf` e confira o **QUADRADO DE 50 MM** com uma régua.
   - Se não medir 50 mm, a impressora está aplicando zoom/redução: corrija antes.
2. Imprima `saida/duplex-test.pdf` **frente e verso** na sua impressora.
   - Verifique se os identificadores A–I do verso caem exatamente atrás dos da frente.
   - Se estiverem deslocados, ajuste `duplex.flip` no `config.yaml`
     (`long_edge` ↔ `short_edge`) conforme o comportamento da sua impressora.

## Configurando a impressão

Ao abrir o PDF (Adobe Reader, evince, navegador etc.):

- Selecione o tamanho de papel **A4**.
- Defina a escala como **100%**.
- **Desative** "Ajustar à página" / "Fit to page" / "Shrink to fit".
- Use impressão **frente e verso** (duplex) quando `duplex.enabled: true`.

> O tamanho físico deve ser preservado. Nunca selecione "ajustar".

## Ordem das páginas

`saida/deck-impressao.pdf` contém, em ordem:

```
página 1: frente
página 2: verso
página 3: frente
página 4: verso
...
```

Se preferir arquivos separados, use `saida/frente.pdf` e `saida/verso.pdf`.

## Recomendações

- Teste primeiro com papel comum.
- Verifique a orientação (retrato/paisagem em `page.orientation`).
- Só imprima no papel definitivo após confirmar alinhamento e escala.
