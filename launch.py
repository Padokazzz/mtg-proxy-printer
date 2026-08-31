import sys
from pathlib import Path

# Garante que o pacote seja importável em modo desenvolvimento.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mtg_proxy.cli import main

if __name__ == "__main__":
    sys.exit(main(["gui"]))
