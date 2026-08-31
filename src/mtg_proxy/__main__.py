import sys
from pathlib import Path

# Garante que o pacote seja importável quando executado via `python -m mtg_proxy`
# a partir da raiz do projeto (sem instalação prévia com pip install -e).
_SRC = str(Path(__file__).resolve().parent.parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
