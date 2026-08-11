# Arquitetura — Vitre RPG

Onde as coisas moram e como os módulos se encaixam. Se este arquivo discordar
do código, o código venceu — corrija aqui.

## Visão geral

Bot Discord single-file-core: `bot.py` cria o `commands.Bot`, registra a
maioria dos comandos e depois **importa e liga** os módulos maiores no fim do
próprio arquivo. Não há pasta `cogs/` nem classes `commands.Cog` — a divisão é
por módulo Python simples, ligado via uma função `instalar(bot, contexto)`.

```
bot.py        núcleo: conexão Discord, comandos de jogador (perfil, caçar,
              explorar, loja, viajar, npc, respec, titulo, descansar...),
              helpers de combate puro (calcular_dano, aplicar_xp,
              rolar_drops...) e o on_ready/on_command_error
  ├─ database.py   schema SQLite + migrações + funções de acesso
  ├─ atributos.py  fórmulas puras (HP, mana, dano, defesa, regeneração)
  ├─ game_data.py  catálogo estático: ITENS, ANDARES (1-15), CLASSES,
  │                ASCENSOES, TITULOS, HABILIDADES, RAIDE_CHEFE,
  │                CONDICOES_ELEMENTO, xp_necessario()
  ├─ npcs.py       NPCs por andar, loja, ferreiro, taverneiro, guia, carroça
  │                do Bramm, custo de viagem; opcoes_do_dialogo() resolve
  │                opcoes+opcoes_por_estado pros NPCs de tipo "conversa"
  │                (importa dialogos.py e database.py)
  ├─ dialogos.py   sem instalar() — só DADO: dict DIALOGOS (abertura +
  │                opcoes/opcoes_por_estado) dos NPCs de tipo "conversa".
  │                DialogoView/BotaoOpcaoDialogo (a UI) moram em bot.py,
  │                perto do comando `falar` que as usa
  ├─ andares_altos.py  sem instalar() — conteúdo/regra dos andares 11-15
  │                (fala da Guia por mortes, ANDAR_ACIMA_DO_SELO); importado
  │                direto por bot.py e combate.py, não por último
  ├─ paginacao.py  sem instalar() — paginar()/PaginacaoView/enviar_paginado(),
  │                usado por todo comando que monta embed a partir de uma
  │                lista de tamanho variável (receitas, inventário, baú de
  │                guilda, loja, habilidades, títulos)
  ├─ condicoes.py  estado de combate por rodada — sangramento/regen/stun
  │                (jogador→chefe, skills) e Queimadura/Choque/Vendaval/
  │                Congelamento/Marca/Ferida Sombria (chefe→jogador, andar
  │                11+) — não persiste no banco
  ├─ combate.py    import tardio no fim de bot.py — luta de chefe por
  │                turnos e botões (Combatente, Luta, PainelLuta...)
  ├─ habilidades.py import tardio — infraestrutura de classe/skill, 8
  │                skills no catálogo (2 por classe)
  ├─ profissoes.py import tardio, opcional (try/except) — craft, melhoria
  │                (+1/+2) e desmanche de equipamento
  ├─ comercio.py   import tardio, depois de profissoes — Comprar/Vender/
  │                Forjar/Melhorar/Desmanchar dentro de `rpg falar` no
  │                mercador/ferreiro (MercadorView/FerreiroView). Não
  │                duplica lógica: ShimCtx chama `comprar`/`vender`/
  │                `craftar`/`melhorar`/`desmanchar` de verdade via
  │                `.callback()`. `rpg loja` foi removido em favor disso
  ├─ trocas.py     import tardio — `rpg pix` (transferência à distância,
  │                confirmação por botão) e `rpg trade` (troca presencial de
  │                item/moeda, UI de oferta com botões e modal); estado de
  │                troca em andamento vive em memória do módulo, nada no banco
  ├─ agenda.py     import tardio — task em loop que avisa a carroça do Bramm
  ├─ admin.py      import tardio — comandos do dono do bot (reset de
  │                temporada, reset individual de classe/profissão)
  ├─ guildas.py    import tardio — guildas: baú, cargo/canal no Discord,
  │                viagem grátis pra home
  ├─ raide.py      import tardio, depois de combate — chefe fixo de guilda,
  │                reusa Luta/PainelLuta de combate.py via subclasse
  └─ efeitos.py    NÃO importado em lugar nenhum — ver seção própria abaixo
```

## O padrão `instalar(bot, contexto)` e o dict `H`

`combate.py`, `habilidades.py` e `profissoes.py` não importam `bot.py`
diretamente — isso criaria import circular, já que `bot.py` é quem os importa.
Em vez disso, cada um desses módulos:

1. Declara um dict vazio no escopo do módulo: `H = {}`.
2. Expõe `def instalar(bot, contexto):`, chamada uma única vez no fim de
   `bot.py` com `contexto = globals()` — ou seja, `H` recebe uma cópia de
   **todo** o namespace de `bot.py` (funções como `pegar_jogador`, `stats`,
   `calcular_dano`, além de constantes como `COOLDOWN_BOSS`).
3. Dentro do módulo, em vez de chamar a função direto, chama por string:
   `H["stats"](j)`, `H["pegar_jogador"](ctx)`. É gambiarra proposital: dá pra
   reusar os helpers de `bot.py` sem reescrever nem criar import circular.
4. `instalar()` também é onde o módulo registra seus próprios comandos
   (`@bot.command`) e, quando precisa substituir um comando que `bot.py` já
   registrou, chama `bot.remove_command("nome")` antes (é o caso de `boss`,
   que `combate.py` substitui pela versão com botões).

Ordem de wiring no fim de `bot.py` (importa **depois** de todos os
`@bot.command` do arquivo, porque `contexto = globals()` só enxerga o que já
foi definido até aquele ponto):

```python
import combate
combate.instalar(bot, globals())      # também acrescenta o comando `party`

import habilidades
habilidades.instalar(bot, globals())  # combate.py já importa este módulo direto
                                       # (não via H) para condicoes/afinidade;
                                       # instalar() só liga o comando `rpg habilidades`

try:
    import profissoes
    profissoes.instalar(bot, globals())
except ModuleNotFoundError:
    print("profissoes.py ainda não está na pasta — craft desligado.")

import trocas
trocas.instalar(bot, globals())       # rpg pix e rpg trade — só usa
                                       # pegar_jogador/encontrar_item via H

import guildas
guildas.instalar(bot, globals())      # rpg viajar (definido acima) já chama
                                       # db.viagem_gratis_guilda por baixo

import raide
raide.instalar(bot, globals())        # precisa vir depois de combate.instalar():
                                       # usa combate.H, combate.Luta, combate.PainelLuta

import agenda
agenda.instalar(bot)                  # não usa H — só precisa do bot, task própria

import admin
admin.instalar(bot)                   # não usa H — comandos do dono do bot

bot.run(TOKEN)
```

`profissoes.py` é o único opcional — o `try/except ModuleNotFoundError`
existe para permitir jogar sem craft se o arquivo não estiver na pasta.
`atributos.py`, `database.py`, `game_data.py`, `npcs.py` e `condicoes.py` são
importados normalmente no topo de `bot.py`/`combate.py`, porque são só
funções e dados — sem risco de ciclo. `guildas.py` também importa
`database.py` direto (não só via `H`) pras próprias funções de guilda —
ele não precisa de nada exclusivo de `bot.py` além dos helpers de sempre
(`pegar_jogador`, `normalizar`, `encontrar_item`, `separar_quantidade`).

## `condicoes.py` — por que não usa o dict `H`

`condicoes.py` é diferente dos três acima: não declara `H` e não tem
`instalar()`. Ele só recebe o objeto `luta` (instância de `Luta`, definida em
`combate.py`) como argumento em cada função (`aplicar`, `tick`,
`pode_agir`...) e lê/escreve atributos nele diretamente. Não precisa do dict
de contexto porque não chama nada de `bot.py` — só manipula o estado da luta
que já recebeu.

## `efeitos.py` — módulo escrito, nunca ligado

`efeitos.py` segue o mesmo padrão `H = {}` / `instalar(bot, contexto)` dos
outros, mas **nenhum lugar do código chama `efeitos.instalar()`** — não está
no fim de `bot.py` junto com `combate`, `habilidades`, `profissoes` e
`agenda`. Além disso, ele chama `db.get_efeitos(user_id)`, uma função que
**não existe** em `database.py`, e não há tabela `efeitos` no schema. É
buffs temporários contados em número de combates (não em minutos, comentário
no topo do arquivo explica: bot cai junto com o PC, buff por tempo evaporaria
sem uso) para os efeitos `furia` (ATK), `sorte` (drop) e `guarda` (DEF) — mas
é código morto até alguém escrever a tabela, o `db.get_efeitos`/`conceder` de
verdade e o `import efeitos` + `efeitos.instalar(bot, globals())` no
`bot.py`. Não assuma que esse sistema funciona só porque o arquivo existe.

## Banco de dados

SQLite (`aincrad.db`), acesso via `database.py` com um único helper de
conexão:

```python
@contextmanager
def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
```

**Exceção ao padrão "sempre passa por uma função de `database.py`"**:
`trocas.py` chama `db.conectar()` direto pra fechar o commit de `rpg trade`
(saldo, inventário e nível de melhoria dos dois jogadores revalidados e
movidos dentro de uma única conexão/transação) — nenhuma função nova
precisou entrar em `database.py` pra isso, `conectar()` já era pública. Ver
`decisoes.md` § Pix e trade.

Tabelas: `jogadores` (uma linha por `user_id`, a maior parte do estado),
`inventario` (`user_id, item` → `qtd`), `cooldowns` (`user_id, comando` →
`expira_em`, timestamp Unix — inclui o cooldown de `rpg descansar` desde
que ele passou a ser pago com preço fixo, ver `decisoes.md` § Preço do
descanso), `upgrades` (`user_id, item` → `nivel` de melhoria +1/+2, ver
`decisoes.md` § Melhoria e desmanche), as seis de guilda (`guildas`,
`guilda_membros`, `guilda_bau`, `guilda_log`, `guilda_raide`,
`guilda_convites` — convite pendente de guilda, `guilda_id, user_id` →
`convidado_por, expira_em`, ver `decisoes.md` § Convite de guilda vira
convite de verdade) e `chefes_derrotados` (`user_id, andar` → `vezes` — só
importa acima do andar 10, ver `decisoes.md` § Morte e reconquista).
Nenhuma dessas precisou de migração: são tabelas novas (`CREATE TABLE IF
NOT EXISTS` no `SCHEMA` direto), não coluna nova em tabela existente — só
isso último passa pela dança de migração abaixo. Não há tabela de
`efeitos` (ver acima). Party de `rpg boss`/`rpg party` é estado em memória
da luta, não persiste — só a *guilda* persiste.

### Padrão de migração

`init_db()` roda toda vez que o bot sobe (chamada em `on_ready`, `bot.py:272`,
não na importação do módulo). Primeiro `executescript(SCHEMA)` — cria as
tabelas só se não existirem. Depois uma sequência de blocos de migração, cada
um:

1. Lê `PRAGMA table_info(jogadores)` para saber quais colunas já existem.
2. Se a coluna que a migração precisa não existe, roda `ALTER TABLE ... ADD
   COLUMN` e faz o `UPDATE` de backfill pros jogadores que já estavam no
   banco.
3. Imprime uma linha de log (`print`) confirmando o que mudou — é o que
   aparece no console quando o bot sobe, único jeito de confirmar a migração
   sem abrir o `.db` na mão.

As migrações são numeradas em comentário (`# migração 1: ...` até `# migração
8: ...`, hoje — a 8 é `anel`/`colar`) e **nunca removidas nem reescritas** — é o histórico de como o
schema chegou ao estado atual, e rodar de novo em um banco já migrado é
sempre um no-op (o `if coluna not in colunas` protege). Ao mexer no schema:

- Nunca dropar ou renomear coluna existente com dado de jogador real dentro.
- Toda migração que tira poder de um build já feito (nerf de atributo, troca
  de fórmula) vem acompanhada de um jeito de devolver pontos — foi o padrão
  usado na migração 5 (`respec_gratis`) quando CON parou de dar defesa.
- `HANZO_USER_ID` (`database.py:86`) é um `user_id` hardcoded para um grant
  histórico único (título "Primeiro do Décimo Andar") — não é reconcedido em
  migrações futuras, só existe naquela migração 6 específica.

## Combate: dois motores diferentes

- **Caçar (`rpg cacar`) e explorar (`rpg explorar`)**: resolvidos
  instantaneamente em `bot.py`, sem UI de turno — rola dano, aplica, manda
  uma mensagem com o resultado. Usa `calcular_dano`, `aplicar_xp`,
  `rolar_drops`, `aplicar_regeneracao`, todos definidos direto em `bot.py`.
- **Chefe (`rpg boss` / `rpg party`)**: todo em `combate.py`, por turnos com
  botões (`discord.ui.View`/`discord.ui.Button`). `Combatente` empacota um
  jogador + seus stats calculados (`H["stats"]`) dentro da luta; `Luta` é o
  estado da sessão inteira (HP do chefe, lista de combatentes, condições
  ativas via `condicoes.py`); `PainelLuta` é a view com os botões de Atacar/
  Defender/Poção/Habilidade/Fugir; `SalaDeEspera` é a view de convite antes
  de uma `party` começar. `MenuPocoes`/`BotaoPocao` e `MenuHabilidades`/
  `BotaoHabilidade` são submenus abertos a partir do painel principal.

Só o chefe é por turnos — decisão de design deliberada (ver
`decisoes.md`), não limitação técnica: caçada em botão ia deixar o grind mais
lento sem ficar mais estratégico.

### Estender `PainelLuta` por subclasse (`raide.py`)

A raide de guilda usa o mesmo `Luta`/`PainelLuta`/`Combatente` de sempre —
`Luta` já calcula HP do chefe × número de participantes sozinha, então não
precisou de nenhuma mudança pra isso. O que muda é só a recompensa (pro
baú da guilda, não pro jogador) e a sala de espera (só membros da mesma
guilda). `raide.PainelRaide(combate.PainelLuta)` sobrescreve só
`fim_da_luta()` (decide o que é "vitória" e chama a recompensa certa) e
`_continuar(luta)` (o painel novo que substitui o anterior quando uma
rodada estoura o timeout).

`_continuar()` existe em `PainelLuta` especificamente pra isso: sem ele,
`on_timeout()` instanciava `PainelLuta(luta)` direto, hardcoded — uma
subclasse que precisasse de argumentos extras no `__init__` (como
`PainelRaide` precisa de `guilda_id`/`iniciador_id`) perderia esses dados
no meio de uma luta que atravessasse um timeout. `on_timeout()` também
resolve vitória/derrota chamando `self.fim_da_luta()` em vez de duplicar a
checagem inline — antes da raide existir, essa duplicação já era uma
fonte de bug potencial (as duas cópias podiam divergir), só ninguém tinha
esbarrado nela ainda porque nada subclassificava `PainelLuta`.

Se um sistema futuro precisar de outra variação de luta de chefe (não só
recompensa diferente, mas ex. regra de fuga diferente ou UI diferente),
esse é o ponto de extensão — subclasse, não fork do arquivo inteiro.

## Módulos auxiliares standalone

- `reset_boss.py` — script solto, roda fora do bot (`python reset_boss.py`),
  zera a linha de cooldown `"boss"` de todo mundo direto no banco. Usado
  manualmente durante desenvolvimento pra não esperar os 15 min.
- `teste_botao.py` — bot Discord mínimo e separado (prefixo `!`, próprio
  `commands.Bot`), só para testar se `discord.ui.View`/`Button` respondem
  antes de existir esse padrão em `combate.py`. Não referencia nenhum outro
  módulo do projeto.

## Configuração

`.env` (não versionado): `DISCORD_TOKEN`, `GUILD_ID`, `CANAL_TORRE_ID` (canal
onde `agenda.py` avisa a chegada da carroça do Bramm). Carregado via
`python-dotenv` no topo de `bot.py`. Dependências em `requiriments.txt`
(nome com o typo mantido — é assim que está no arquivo real):
`discord.py>=2.3.2`, `python-dotenv>=1.0.0`, `tzdata`.
