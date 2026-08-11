# tests/test_bot_seguro.py
# Prova que importar bot.py nunca conecta no Discord -- bot.run(TOKEN) mora
# atrás de `if __name__ == "__main__"`. Antes desse cartão, DialogoView e
# PainelLuta só puderam ser verificadas à mão porque a suíte não conseguia
# importar bot.py sem contornar isso na marra (ver decisoes.md § Guarda de
# main + setup no nível do módulo).
import sys
from unittest.mock import patch

from discord.ext import commands


def test_importar_bot_nunca_chama_bot_run(monkeypatch):
    """Troca Bot.run por algo que estoura se for chamado -- se o guard
    falhar (regredir pra fora do `if __name__ == "__main__"`), o import
    quebra aqui em vez de tentar conectar de verdade."""
    monkeypatch.setenv("DISCORD_TOKEN", "token-fake-nunca-deveria-ser-usado")
    sys.modules.pop("bot", None)

    def _explode(self, *a, **kw):
        raise AssertionError("bot.run() foi chamado durante o import")

    with patch.object(commands.Bot, "run", _explode):
        import bot  # noqa: F401 -- o próprio import é a asserção
        assert bot.bot is not None


def test_importar_bot_de_novo_sem_nenhum_patch_tambem_e_seguro():
    """Sem truque nenhum -- é exatamente o que `python -c "import bot"`
    faria num shell (item 2 do checklist do card)."""
    sys.modules.pop("bot", None)
    import bot
    assert bot.bot is not None
