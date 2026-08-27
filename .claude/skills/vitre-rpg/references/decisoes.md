# Decisões de design — Vitre RPG

Registro do que já foi decidido, com o motivo — o porquê por trás de cada
escolha, não o status de implementação. Progresso, prioridade e o que ainda
está em aberto vivem no Kanban Vitre, no Notion.

## Comandos híbridos (leva 1) — `ajuda`, `perfil`, `classe`, `profissao`

Motivo é externo ao jogo: pra aparecer no Descobrir (App Directory) do
Discord, o app precisa usar slash command ou ter Message Content aprovado em
review — e a segunda rota está fechada (Discord recusa pedido cuja
justificativa é preferência por prefixo). Isso **substitui** o invariante
antigo "Prefixo `rpg`, não slash commands" registrado mais abaixo neste
arquivo (§ Invariantes de design do skill) — não foi revertido escondido, foi
essa decisão que o derrubou.

**`commands.hybrid_command`/`hybrid_group`, não slash em paralelo do
prefixo**: duas implementações do mesmo comando divergem sozinhas cedo ou
tarde (uma ganha um fix, a outra não) — hybrid usa o mesmo callback pra `rpg
X` e `/X`, então não tem como divergir. `Context.send`/`Context.defer`
decidem sozinhos entre resposta de interação e followup/typing conforme o
modo (`ctx.interaction`); nenhum comando desta leva tem branch manual pra
isso.

**Fatiado, não a base inteira de uma vez**: são ~30 comandos de prefixo no
bot. Converter tudo de uma vez e descobrir em produção que hybrid quebra algo
específico (ordem de parsing de argumento, um converter que não tem
Transformer equivalente, um Group cujo roteamento muda com subcomando de
verdade) significa depurar às cegas em meio a trinta candidatos. Essa leva é
só leitura pura (`ajuda`, `perfil`, `classe`, `profissao`) — sem escrita em
banco fora da troca de ofício, que já existia. Levas seguintes (combate,
economia, trade, guilda, admin) só entram depois desta validada em produção
de verdade (usuário real batendo `/perfil` no Discord, não só teste).

**`rpg perfil` ganhou `await ctx.defer()`**: é o único dos quatro que faz
IO de rede fora do SQLite — `avatar.obter_avatar_atualizado` chama
`canal.fetch_message()` quando o cache da URL do avatar já venceu, e isso
pode passar dos 3s que uma interação dá pra primeira resposta. `defer()` é
no-op fora de interação (código de verdade do discord.py,
`ext/commands/context.py`), então chamar sem checar o modo é seguro — mesmo
padrão de "não escrever branch manual" do `Context.send`. `ajuda`/`classe`/
`profissao` só leem SQLite (rápido) e constantes em memória — não precisam.

**`profissao` virou `hybrid_group` com `fallback="ver"`, `trocar` virou
subcomando de verdade**: grupo de slash não é invocável direto (API do
Discord não suporta), por isso o fallback. O corpo do callback do grupo
continua aceitando `rpg profissao trocar <nova>` como texto livre — não
porque é o caminho real de dispatch (não é mais: `HybridGroup` sempre liga
`invoke_without_command`, então `Group.invoke` casa a primeira palavra contra
`all_commands` **antes** de rodar o callback do grupo, e "trocar" agora bate
com o subcomando de verdade tanto por prefixo quanto por slash) — e sim
porque `tests/test_classe_profissao_wiki.py` chama
`bot.get_command("profissao").callback(ctx, argumento="trocar ...")`
direto, pulando o dispatch do discord.py inteiro. Pra não duplicar a lógica
de troca em dois lugares (e não editar aquele teste, que a validação desta
leva pede pra manter intocado), a troca em si virou `_executar_troca(ctx, j,
resto)`, chamada tanto pelo ramo de texto livre do fallback quanto pelo
subcomando `trocar` novo — texto do ramo velho fica tecnicamente inalcançável
via uso real, mas não é lógica duplicada, é a mesma função.

**Sync manual (`rpg sync [guild_id]` em `admin.py`, dono do bot), não
`tree.sync()` no `on_ready`**: sync global demora até 1h pra propagar nos
clientes — chamar isso toda vez que o bot reinicia (que acontece bastante
num bot rodando no PC de casa) seria rate-limit e demora sem necessidade.
Sync por guild com `copy_global_to` + `sync(guild=...)` (padrão do próprio
discord.py pra isso) é instantâneo — é como cada leva vai ser testada no
servidor de verdade antes de liberar globalmente.

**`on_command_error` não precisou de espelho em `tree.on_error`**: conferido
direto no código instalado (`discord/ext/commands/hybrid.py`,
`_invoke_with_namespace`) — erro de comando híbrido invocado via slash cai
em `command.dispatch_error(ctx, exc)`, a mesma `Command.dispatch_error` de
`ext/commands/core.py` que todo comando de prefixo já usa, que sempre termina
em `ctx.bot.dispatch('command_error', ctx, error)` num `finally`. Os dois
caminhos de invocação convergem pro mesmo `on_command_error` de sempre — a
guarda `has_error_handler()` que já existia continua valendo pros dois.
Prova em `tests/test_hybrid_commands.py::test_erro_em_comando_hibrido_convergiu_pro_mesmo_handler_nos_dois_modos`.

**`FakeCtx` de `tests/test_avatar.py` ganhou `self.defer = AsyncMock()`**:
não é mudança de asserção nem de comportamento testado — `rpg perfil` agora
chama `ctx.defer()` de verdade (ver acima), e uma `Context` de verdade sempre
tem esse método (é no-op fora de interação). O fake só passou a imitar a
interface real que já deveria ter; sem isso `test_fetch_message_falhando_
nao_quebra_perfil` quebraria com `AttributeError`, não por regressão de
comportamento.

## ATK dos chefes 11-15 reduzido em 60

Pedido direto do Rafael, sem diagnóstico prévio dele — só a conta de
confirmação depois. `game_data.ANDARES[11..15]["boss"]["atk"]`, e a
`fase2` do andar 15 junto (mesmo corte, pra manter a mesma folga entre fase
1 e fase 2 que já existia): 231→171, 257→197, 283→223, 309→249, 335→275
(fase1 do 15), 375→315 (fase2 do 15). Penetração de armadura
(`PENETRACAO_POR_ANDAR`), HP e DEF dos chefes não mudaram — só o ATK.

Dano resultante simulado com o motor de combate de verdade
(`combate.dano_do_chefe`, 200k amostras por andar — cobre a variância de
±15% e a chance de crítico), não conta na mão, contra a mesma build de
referência da calibração original dos andares 11-15 (nível 20, Guerreiro,
FOR 40/CON 22, `lamina_selo`+`manto_selo`, sem acessório/upgrade — DEF 56,
HP 470):

| Andar | ATK antes | ATK depois | Golpe normal (média) | % do HP |
|---|---|---|---|---|
| 11 | 231 | 171 | ~114 | 24% |
| 12 | 257 | 197 | ~133 | 28% |
| 13 | 283 | 223 | ~152 | 32% |
| 14 | 309 | 249 | ~171 | 36% |
| 15 (fase 1) | 335 | 275 | ~191 | 41% |
| 15 (fase 2) | 375 | 315 | ~219 | 47% |

Golpe carregado (30% de chance por rodada, ATK×3 e +25% de penetração)
continua desproporcional mesmo depois do corte — andar 12+ ainda passa de
100% do HP da build de referência num carregado médio (ex.: andar 12 ~483
de dano médio carregado contra 470 de HP). Não mexi nisso: não foi pedido,
e cortar o carregado junto teria sido uma segunda mudança de design não
autorizada — se isso também estiver puxado demais, é ajuste separado
(`MULTIPLICADOR_CARREGADO`/`PENETRACAO_CARREGADO`, `combate.py`).

`tests/test_andar15.py` tinha os valores antigos de ATK (335/375) hardcoded
como trava de regressão do rename do chefe — atualizados pros novos
(275/315) porque esse teste não era sobre o número em si, era sobre nome/
HP/def/drops sobrevivendo ao rename. Nenhum outro teste nem reference doc
tinha os números de ATK 11-15 hardcoded.

## Erro genérico escondia a mensagem certa — `has_error_handler()`

Bug descoberto investigando "`rpg aviso` sem argumento mostra a linha de uso
E, logo abaixo, 'a Torre engasgou'": **todo comando com `@comando.error`
próprio já sofria disso**, não só o `aviso`. `discord.py` sempre dispara o
`on_command_error` global depois de rodar o handler local — `dispatch_error`
(`discord/ext/commands/core.py`) chama `ctx.bot.dispatch('command_error', ...)`
num `finally`, com ou sem handler local registrado. Sem guarda, o handler
local mandava a mensagem certa e o global, sem saber que já tinha dono,
caía direto no ramo genérico ("engasgou" + `raise erro`) por cima. Confirmado
com um `commands.Bot` de teste isolado (sem rede) antes de mexer no código de
produção: sem guarda, dá as duas mensagens; com guarda, só uma.

- **Correção em `bot.py:on_command_error`**: primeira linha do handler agora
  é `if ctx.command is not None and ctx.command.has_error_handler(): return`.
  `has_error_handler()` é método do próprio discord.py (`Command`, desde a
  1.7) — exatamente pra essa checagem, não precisou de flag nem estado novo.
  Resolve de uma vez os quatro comandos de `admin.py` que já tinham handler
  local (`resetartemporada`, `resetarjogador`, `aviso`, `manutencao`), sem
  precisar tocar em nenhum deles.
- **`MissingRequiredArgument` ganhou ramo próprio no handler global** — pra
  todo comando SEM handler local (a maioria: `viajar`, `upar`, `comprar` etc.
  já usam parâmetro opcional com valor-padrão e tratam "sem argumento" dentro
  do próprio corpo, então na prática só `resetarjogador` — que tem handler
  local — dependia de `MissingRequiredArgument` de verdade antes desse
  cartão). Mensagem usa `ctx.command.qualified_name` + `ctx.command.signature`
  (`Uso: rpg <comando> <assinatura>`), sem "engasgou" nem "tenta de novo".
- **`BadArgument` já tinha ramo próprio antes desse cartão** — conferido a
  pedido, não precisou de correção, só ganhou teste de regressão junto dos
  outros dois.
- **`rpg aviso` sem categoria não vira erro nenhum**: `categoria` e `resto`
  passaram a ter `= None`, e o corpo do comando decide mostrar a ajuda em vez
  de deixar o discord.py levantar `MissingRequiredArgument` — o handler local
  de `aviso_cmd` perdeu o ramo desse erro porque ficou inalcançável (os dois
  parâmetros têm default agora). Ajuda (`texto_ajuda_aviso()`) monta a lista
  de categorias direto de `CATEGORIAS_AVISO` — mesma constante que
  `embed_aviso` já usava pra cor/ícone — em vez de escrever a lista a mão de
  novo, pra não desatualizar sozinha quando uma categoria mudar.
- Testado em `tests/test_manutencao_e_aviso.py`: `rpg aviso` sem argumento
  responde com as 5 categorias sem erro; a ajuda cai junto quando uma
  categoria some da constante (não é lista fixa em paralelo);
  `MissingRequiredArgument` fora do ramo genérico pra comando sem handler
  local; comando COM handler local não recebe mensagem duplicada (o bug
  original); `BadArgument` confirmado que já estava OK. As duas primeiras
  falham de verdade sem a guarda em `bot.py` (validado via `git stash`
  temporário no arquivo e restaurado em seguida).

## `rpg aviso` + modo manutenção

Dois comandos de dono em `admin.py`, restritos como o resto do cog já era
(`commands.is_owner()` — sem cargo de staff, sem lista de IDs nova).

### `rpg aviso <categoria> [--everyone] <mensagem>`

- **`CATEGORIAS_AVISO` é constante nomeada, acesso por `.get()`** — mesma
  regra do `PAPEL_NPC` (§ Padrão — mapa de domínio nunca é subscript
  direto, mais abaixo neste arquivo): a chave vem de texto digitado no
  Discord, então categoria desconhecida vira erro claro listando as
  válidas (`embed_aviso` levanta `ValueError` com a lista pronta pra
  mandar de volta), nunca `KeyError` derrubando o comando.
- **Cinco categorias fechadas**: manutencao (laranja), atualizacao (verde),
  evento (roxo), urgente (vermelho), recado (cinza) — cada uma com ícone e
  um texto de moldura fixo no rodapé do embed, tom da Torre falando
  ("🗼 A Torre vai fechar por um instante — nada é perdido.", etc.).
- **`@everyone` é opt-in explícito por chamada, nunca fixo por categoria**:
  flag `--everyone` como primeiro token depois da categoria
  (`rpg aviso urgente --everyone Caiu o servidor`). Padrão sem a flag é
  **não marcar** — marcar por engano é pior que esquecer, e a flag some do
  texto da mensagem antes de virar `description` do embed. Reusa o padrão
  de `agenda.avisar_carroca`: `allowed_mentions=discord.AllowedMentions(everyone=...)`
  explícito e `discord.HTTPException` tratada sem derrubar o comando.

### `rpg manutencao <minutos>` / `rpg manutencao fim`

- **Estado em memória no `travas.py`**, junto de `_em_luta` — nada de
  coluna nova no banco. Reiniciar o bot já limpa tudo sozinho, e esse é o
  comportamento certo: depois de um restart não deve sobrar manutenção
  "presa" ligada.
- **A trava (`travas.fora_de_manutencao()`) só barra abrir luta NOVA** —
  decorador a mais em `rpg boss`/`rpg party`/`rpg raide` (`combate.py`,
  `raide.py`), do mesmo jeito que `travas.fora_de_luta()` já existia pra
  `rpg boss`. Luta já em andamento nunca passa de novo pelo check do
  comando (o motor de combate não re-invoca `boss`/`party`/`raide`), então
  não precisou de nenhuma trava nova dentro de `combate.py`— trade, pix e
  convite de guilda continuam de fora de propósito, o pedido foi só sobre
  abrir luta.
- **`ninguem_em_luta()` reusa `_em_luta` como fonte única da verdade** —
  não abriu tabela nem contador novo. Quando `_em_luta` esvazia, a última
  luta ativa acabou de fechar.
- **Aviso de "pode reiniciar" por DM pro autor do comando, não pro
  application owner via `application_info()`**: quem roda `rpg manutencao`
  já passou por `commands.is_owner()`, então é o dono garantido — mais
  simples que resolver o dono do app e evita uma chamada HTTP extra.
- **Poll a cada 15s (`checar_fim_de_manutencao`, `admin.py`) em vez de
  gancho dentro de `combate.py`/`raide.py`.** Os pontos onde uma luta
  termina são vários — vitória, derrota, fuga, timeout, em dois arquivos
  diferentes (`combate.py` e `raide.py`, ver `travas.destravar_todos`
  espalhado em ~5 lugares). Encadear uma notificação em cada um desses
  pontos acoplaria `combate.py`/`raide.py` a `admin.py` em vários lugares
  pra um aviso que só interessa durante uma janela de manutenção — ler
  `len(_em_luta) == 0` a cada 15s é mais simples e não toca no motor de
  combate.
- **O loop só nasce se havia luta pra esperar.** Se `ninguem_em_luta()` já
  é verdade no instante em que `rpg manutencao <minutos>` roda, o aviso sai
  synchronous, na hora, dentro do próprio comando — o loop nunca precisa
  existir nesse caso. Se havia gente lutando, o loop começa e se auto-para
  (`self.stop()` de dentro do próprio corpo) assim que
  `travas.manutencao_ativa()` vira falso — por prazo vencido ou por
  `rpg manutencao fim`.
- **Se o prazo vence com luta ainda em andamento, não notifica.** A janela
  já desligou sozinha (`manutencao_ativa()` limpa o próprio estado ao
  expirar, mesmo padrão de `em_luta()`), então o aviso de "pode reiniciar
  com a manutenção ligada" deixou de fazer sentido — o dono só saberia que
  precisa religar a manutenção e esperar de novo. Não veio pedido explícito
  pra isso; fica de fora até aparecer.
- **A recusa (`ManutencaoAtiva`, tratada em `bot.py:on_command_error`) leva
  o tempo restante formatado** (`travas.fmt_restante`) — negar sem dizer
  quanto falta deixa quem tentou sem saber se tenta de novo em 1 minuto ou
  em 1 hora.
- Testado em `tests/test_manutencao_e_aviso.py`: predicado isolado E os
  `checks` reais de `boss`/`party`/`raide` (via `import bot`, confirma que
  o decorador está mesmo nos três comandos, não só que a função funciona
  solta); leitura (`rpg perfil`) passa reto; janela expira sozinha; `fim`
  corta antes do prazo; `em_luta` não é tocado pela janela; aviso dispara
  ao esvaziar `_em_luta` e dispara na hora quando não havia luta nenhuma;
  categoria desconhecida não derruba `rpg aviso`; `--everyone` só marca
  quando pedido. Confirmado que o teste de integração falha de verdade
  removendo o decorador de `combate.py`/`raide.py` (não é um teste que
  passaria de qualquer jeito).

## Guarda contra restart consumindo os backups recentes

`agenda._rotacionar_backups()` roda num `tasks.loop(hours=INTERVALO_BACKUP_HORAS)`,
e o discord.py executa a primeira iteração assim que o `before_loop` termina —
ou seja, todo restart do bot dispara uma rotação. Em produção isso é
desejável (backup fresco ao subir). Em desenvolvimento, com o bot
reiniciando a cada mudança, três restarts em 20 minutos sobrescreviam
`recente_1`, `recente_2` e `recente_3` — a janela de ~6h de profundidade da
escada 3/1/1 virava 20 minutos, justo a camada que cobre um acidente
recém-acontecido.

Correção: `GUARDA_RECENTE_SEG` (`agenda.py`, ao lado de
`INTERVALO_BACKUP_HORAS`) — se o mais novo dos três `recente_*.db` tiver
menos que isso, a rotação dos recentes é pulada naquela chamada.

- **A guarda vale só pros recentes, não pro diário/semanal.** Os dois já se
 protegem sozinhos (24h e 7 dias) comparando o próprio mtime contra a
 janela — a única camada sem guarda própria era a dos recentes, porque ela
 gira a cada chamada por design (é o que dá profundidade de ~6h).
- **`_mtime_ou_nunca` devolve -1 pra arquivo que não existe** — na pasta
 vazia (primeira execução) o "mais novo" também é -1, e a guarda não pode
 bloquear esse caso, senão o bot nunca criaria o primeiro backup. A guarda
 é sobre backup recente demais, não sobre ausência de backup.
- Testado em `tests/test_agenda_backup.py`, direto na função pura (não
 importa Discord de verdade) — `tmp_path`/`os.utime()` forjam mtime.
 Confirmado que sem a guarda o teste de "recente com 10 minutos" falha (os
 três recentes continuam sendo sobrescritos), e com a guarda ele passa sem
 quebrar round-robin nem diário/semanal.

## Rebalanceamento da defesa

Contexto: dois jogadores terminaram o andar 10 sem usar as armas de selo e sem
correr risco de morrer. O objetivo era a torre inteira ficar mais dura, do
andar 1 em diante. A penalidade de morte já estava boa — morrer devia
**acontecer** mais, não **doer** mais.

Diagnóstico original: CON dava HP e aparagem ao mesmo tempo, e a aparagem era
multiplicativa e sem teto por CON. Uma build de 29 CON tinha 540 de HP e 57%
aparado — ~1.256 de HP efetivo. Subir o ataque dos monstros só tornaria CON
mais obrigatório.

O que foi implementado (mais simples do que o esboço original abaixo):
- **CON dá só HP.** `defesa(bônus_armadura) = 2 + bônus_armadura` — o
 parâmetro de constituição saiu da fórmula (`atributos.py`). A curva de
 redução (`reducao_dano`, teto 60% em DEF~75) não mudou; só a fonte de DEF
 mudou, de CON+armadura para só armadura.
- **Em vez de fórmula de aparagem por andar**, o ajuste veio pelo lado do
 ataque: o ATK do chefe passou de `13 + 8*(andar-1)` para
 `13 + 13*(andar-1)` — anda 1 fica igual, andar 10 sai de 85 para 130. A
 ideia de "aparagem relativa ao andar" (`def / (def + 50 + 15*andar)`) foi
 descartada por enquanto — mais simples subir o ataque do que reescrever a
 curva de redução duas vezes.
- **Migração com respec grátis**: coluna `respec_gratis` em `jogadores`,
 `1` para todo mundo que já existia no banco na hora da migração. O comando
 `rpg respec` verifica a flag antes de cobrar — se estiver ligada, zera os
 atributos de graça e desliga a flag.
- CON **não** ganhou mais HP por ponto nesse commit — ficou pra depois, junto
 com dar função real à DES.

**O level up ainda cura 100%?** Não — cura 50% do HP máximo novo,
`CURA_LEVEL_UP` em `atributos.py`. Já era assim antes deste commit, não mudou
com o rebalanceamento.

## Consumíveis na luta de chefe

O limite de 3 poções por luta (`MAX_POCOES`) passou a valer só pra poção
comum (`pocao_p/m/g`, cura fixa). Elixir de Alquimia (`elixir_ervas`,
`elixir_vermelho`, `nectar_torre` — cura por porcentagem) ganhou contador
próprio, `MAX_ELIXIRES = 1`, em `combate.py`. Os dois contadores são
independentes: dá pra usar 3 poções **e** 1 elixir na mesma luta. Distinção é
por `"cura_pct" in ITENS[chave]` (`eh_elixir`), não por lista de nomes —
qualquer receita de Alquimia futura já cai automaticamente no contador de
elixir.

## Sistema de títulos

Cosmético por enquanto — nenhum título dá bônus de stat. Duas colunas em
`jogadores`: `titulo` (o equipado) e `titulos_possuidos` (CSV das chaves que o
jogador tem). Catálogo em `game_data.TITULOS`. `rpg titulo` lista os
possuídos, `rpg titulo equipar <nome>` troca, `rpg titulo remover` tira; o
equipado aparece no título do embed de `rpg perfil`.

Dois títulos concedidos na migração, de uma vez só — não é um sistema geral
de conquista automática ainda, cada novo título exige uma migração ou comando
de admin:
- `beta_tester` — todo `user_id` que já estava em `jogadores` na hora da
 migração.
- `primeiro_andar_10` — só o Hanzo (`user_id` hardcoded em `database.py` como
 `HANZO_USER_ID`), por decisão direta do Rafael, sem lógica de "quem chegou
 primeiro" no código (o banco não guarda histórico de quando cada jogador
 destrancou cada andar, então não dava pra calcular).

## Classes e habilidades

Este commit deixou tudo pronto pra receber skills, mas **nenhuma skill existe
ainda** — `game_data.HABILIDADES = {}`. É de propósito: calibrar dano, mana e
duração de condição sem ter uma skill de verdade pra testar é achismo. O
próximo passo é lançar a primeira e ajustar o motor em cima dela, não inventar
os 12 números de uma vez.

Decisões já tomadas, com o porquê:
- **Habilidade só na luta de chefe.** Caçada e exploração continuam
 instantâneas — o botão "Habilidade" só existe no painel do `rpg boss`.
- **Mana**: `mana_maxima = 20 + 5*INT` (já existia). Regenera **1 por minuto**
 fora de combate, mais devagar que o cooldown de 15 min do chefe de propósito
 — se enchesse mais rápido, a poção de mana (`pocao_mana`, loja, todo andar) e
 o elixir melhor (`elixir_mana`, Alquimia nível 4, 50% da mana) nasceriam
 mortos. HP e mana agora usam o mesmo núcleo de regeneração
 (`atributos._regenerado`), só muda o teto e a taxa.
- **Classe é escolha travada**: coluna `classe`, comando `rpg classe`, sem
 troca (nem por moeda) — mais rígido que profissão de propósito, porque
 profissão junta com craft (menos crítico) e classe vai virar identidade de
 combate. Migração deixa jogadores existentes sem classe; escolhem quando
 quiserem.
- **4 bases cadastradas em `game_data.CLASSES`**: Mago (INT), Guerreiro (FOR),
 Ladino (DES), Orador (INT no dano de habilidade, mas DES na arma — um
 caster que briga com as próprias mãos). Os 12 ramos estão em
 `game_data.ASCENSOES`, só como texto pro comando `rpg ascencao` — nenhum
 jogador pode escolher um ramo ainda, isso é fase depois desta.
- **Requisito de atributo por skill**: `("inteligencia", 15)` etc. Skill sem
 requisito é conhecida assim que a classe é escolhida. Uma trava extra,
 `"sidequest": True`, marca a skill que só entra via `habilidades_extras`
 (CSV na tabela `jogadores`) — a sidequest do NPC que concede isso **não
 existe ainda**, só a coluna que vai guardar o resultado dela.
- **Afinidade de arma**: `habilidades.fator_afinidade(classe, arma)` — 1.0 na
 arma certa, `0.5` fora dela (placeholder, calibrar quando a primeira skill
 usar isso de verdade). Nada é proibido, só rende menos.
- **Desarmado escala com DES agora**, não mais FOR (`ATRIBUTO_PADRAO_ARMA`).
 Orador brigando sem arma (ou de manopla) recebe metade do escalonamento —
 `ESCALONAMENTO_DESARMADO_ORADOR = 0.5` — até a ascensão pra Monge, que não
 existe ainda, mas já herda o valor cheio por não estar na exceção.
- **Equipamento novo**, 5 peças cada, um por ferreiro ímpar (1/3/5/7/9): 5
 cajados (INT, curva idêntica às espadas de Força) e 5 manoplas/faixas (DES,
 curva idêntica às adagas de Destreza, crítico 18%). A versão do andar 9 de
 cada uma é só craft, receita de Forja nível 9, mesmo padrão das outras
 peças de selo.
- **Condições de combate**: módulo novo `condicoes.py`. Estado por luta
 (não persiste no banco), com `alvo` (`"chefe"` ou um user_id), `tipo`
 (`dano_por_rodada`, `cura_por_rodada`, `pula_turno`, `redireciona`),
 `duracao` em rodadas e `valor` (fixo ou fração do HP máximo). O tick roda
 uma vez no início de cada rodada (`registrar_acao` e `on_timeout`, os dois
 lugares onde uma rodada resolve) e sempre loga no texto da luta — inclusive
 a aplicação inicial, pra quem levou a condição ver que pegou. Cobre os
 pedidos de sangramento/confusão/elemento genericamente: **decidi não
 pré-cadastrar fogo/gelo/raio/divino/sombrio/ar como entradas fixas do
 catálogo**, porque duração e potência de cada elemento são decisão de
 balanceamento de uma skill real, não do motor. Regeneração com alvo (item 5
 do pedido original, ~8%/rodada por ~2 rodadas) e Provocar (redireciona o
 alvo do chefe, sem efeito em luta solo porque só existe 1 alvo possível) já
 rodam nos testes manuais — só falta uma skill que chame `condicoes.aplicar`.

**O Ar não tem classe dona.** Guerreiro não tem elemento — vira a classe de
efeito físico puro (sangramento, quebra de armadura, o próprio Provocar).

## Primeira leva de skills — 2 por classe

`game_data.HABILIDADES` deixou de estar vazio: Mago (Dardo Arcano, Ruptura),
Guerreiro (Golpe Aberto, Pancada Atordoante), Ladino (Corte Rápido, Ponto
Cego), Orador (Palavra de Alento, Voto de Ferro). Todas neutras, sem
elemento, só lançáveis em `rpg boss`/`rpg party`.

- **Cada classe usa um recurso diferente, e só Mago/Orador usam mana.**
 Guerreiro usa Fúria (pool 100, começa **zerada**, sobe com dano causado:
 `15 + FOR/5` por golpe, crítico dá +50%, Defender gera metade). Ladino usa
 Energia (pool 100, começa **cheia**, regenera 20/turno, agindo ou não).
 Diferença chave pra mana: **Fúria e Energia são por luta** — resetam toda
 vez que `rpg boss`/`rpg party` começa, vivem só no `Combatente`
 (`combate.py`), não têm coluna no banco nem regen fora de combate. Zero
 migração precisou entrar por causa disso.
- **Dano de habilidade escala no `atributo_habilidade` da classe, não no
 `atk` da arma.** `habilidades.poder_base(jogador) = at.ataque(atributo) `
 (mesma fórmula do ataque normal, sem bônus de arma), multiplicado pelo
 fator de afinidade (`hab.fator_afinidade` — 1.0 na arma certa, 0.5 fora
 dela) e por um multiplicador específico da skill.
- **Dardo Arcano ignora a defesa do chefe de propósito** — é o nicho da
 skill sem requisito do Mago: fraco cedo (pouco DEF pra ignorar), mais forte
 tarde (andar 9 tem DEF 26, ~34% de redução que o Dardo simplesmente pula).
- **Pancada Atordoante tem teto de 25% de chance**, igual ao teto de
 `chance_esquiva` (`at.TETO_ESQUIVA`). Sem isso, uma build de FOR alta
 travaria o chefe rodada sim, rodada não — desfaria o rebalanceamento de
 dificuldade do commit anterior. Fórmula: `min(0.25, 0.05 + 0.01*FOR)`.
- **Pegadinha de timing que quase saiu errada**: `condicoes.tick()` desconta
 1 rodada de duração *antes* de qualquer ataque ou turno do chefe rolar
 naquela mesma rodada. Pra uma condição tipo "buff consultado depois"
 (`vulneravel`, `reduz_dano`, `bonus_critico`, `pula_turno`) durar N rodadas
 de efeito de verdade, a duração passada pra `condicoes.aplicar()` precisa
 ser **N+1** — Pancada Atordoante (1 rodada de stun) usa `duracao=2`,
 Ruptura e Ponto Cego (3 rodadas) usam `duracao=4`, Voto de Ferro (2
 rodadas) usa `duracao=3`. **Isso não vale** pra `dano_por_rodada`/
 `cura_por_rodada` (sangramento, regeneração) — esses aplicam o efeito
 dentro do próprio `tick()`, então a duração ali já é literal (Golpe Aberto
 e Palavra de Alento usam `duracao=3`/`duracao=2` sem ajuste). Documentado
 em comentário no topo da seção de efeitos, `combate.py`.
- **`H["calcular_dano"]` passou a devolver `(dano, foi_critico)`** em vez de
 só `dano` — precisava do booleano pra saber se o golpe do Guerreiro rendeu
 o bônus de +50% de Fúria. Os 5 lugares que chamavam a função (3 em
 `bot.py`, 2 em `combate.py`) foram atualizados juntos.
- **Palavra de Alento tem seletor de alvo manual** — dropdown novo
 (`MenuAlvoHabilidade`/`BotaoAlvoHabilidade`) que só aparece em party (mais
 de 1 combatente ativo); em luta solo o alvo é sempre quem lançou, sem UI
 extra. Cura por regeneração ao longo de 2 rodadas (~8%/rodada), não
 instantânea — mesmo valor que já tinha rodado em teste manual antes desta
 leva (ver "Classes e habilidades" acima).

## Reset de temporada — `rpg resetartemporada`

Zera o progresso de todo mundo agora que classes, habilidades e o sistema de
melhoria de equipamento estão no ar — ninguém deve escolher classe às cegas
nem carregar item de um balanceamento que não existe mais. Pensado pra
rodar de novo em toda temporada futura: é comando (`admin.py`), não script
solto tipo `reset_boss.py`.

- **Restrito ao dono do bot** via `commands.is_owner()` — checa contra o
 dono do app no portal do Discord, sem coluna nova nem ID hardcoded (ao
 contrário do `HANZO_USER_ID` em `database.py`, que é um grant histórico
 único, não um mecanismo de permissão).
- **Confirmação por botão antes de mexer em qualquer coisa**, com a lista
 completa do que é zerado/apagado/preservado na própria mensagem — 30s de
 timeout, cancela sozinho. Um wipe a uma tecla de distância é acidente
 esperando acontecer.
- **Backup do `.db` inteiro em `backups/aincrad_AAAAMMDD_HHMMSS.db`**
 (`database.backup_banco()`), rodando *antes* do reset. Se a cópia falhar
 (`shutil.copy2` levanta), o comando aborta e não chama `resetar_temporada()`
 — nada é alterado.
- **Tudo numa transação só** (`database.resetar_temporada()`): todos os
 `UPDATE`/`DELETE` acontecem dentro do mesmo `with conectar()`. Se algo
 levantar no meio, o `commit()` no fim do context manager nunca roda e o
 SQLite descarta a transação inteira ao fechar a conexão sem commit — isso
 já era garantido de graça pelo padrão existente de `conectar()`, não
 precisou de mecanismo novo. Testado manualmente: uma exceção forçada no
 meio de um `UPDATE jogadores` não deixou a mudança vazar.
- **`upgrades` é a tabela que mais importa apagar.** O nível de melhoria
 (`+1`/`+2` de `+12%` de atk/def cada) é preso ao par `(user_id, item)`, não
 ao slot equipado — sobrevive a desequipar/reequipar de propósito
 (`database.get_upgrade`, comentário no topo da seção de upgrades). Se a
 tabela sobrevivesse ao reset, o jogador recompraria a mesma arma inicial no
 ferreiro do andar 1 e ela já viria com o bônus antigo — como todo mundo
 passa pelas mesmas peças cedo, isso pegaria o servidor inteiro na primeira
 hora depois do reset.
- **`profissao` zera junto com `prof_nivel`/`prof_xp`.** Só apagar a
 profissão e deixar o nível de ofício sobreviver faria quem escolher Forja
 de novo começar destravado além de Couro Batido — a curva de craft que
 acabou de ser ajustada nunca seria testada do zero.
- **HP e mana resetam pro valor de nível 1 com atributos base**
 (`at.hp_maximo(1, at.BASE)`, `at.mana_maxima(1, at.BASE)`) mesmo o pedido
 original só tendo citado HP — deixar a mana como estava permitiria um
 valor acima do novo teto (já que INT volta pra `BASE`), o que quebraria o
 embed de perfil. HP e mana usam o mesmo raciocínio.
- **Preservado sem tocar**: a linha em `jogadores` (ninguém roda `rpg
 comecar` de novo), `titulo` equipado, `titulos_possuidos`, `criado_em`
 (alimenta o «Beta Tester», data de corte 13/08) e `mortes`.
- **Verificação pós-reset não é `rpg perfil` zerado** — é `rpg receitas` com
 Forja escolhida mostrando só Couro Batido (única receita de `nivel: 1` no
 catálogo de Forja, `profissoes.RECEITAS`) e uma arma comprada no ferreiro
 do andar 1 saindo sem bônus de upgrade em `rpg status`.

### Baú da guilda zera, a guilda sobrevive

Decisão explícita do Rafael, adicionada depois da primeira leva: guildas
**não** são apagadas no reset de temporada — `guildas`, `guilda_membros`,
`guilda_log`, `guilda_raide`, `guilda_home_cooldown` e `guilda_convites`
continuam intactos, mesma linha que "Cooldown de troca de home da guilda" já
tinha registrado pra `guilda_home_cooldown`/`guilda_raide`. Ninguém refunda
os 5.000 de fundação nem perde cargo do Discord só porque a temporada virou.

**A home NÃO entra mais nessa lista de "sobrevive intacta" — revertido no
cartão do Salão da Guilda.** Quando este parágrafo foi escrito, ainda não
existia tier de Salão puxando a home; depois que passou a existir,
`andar_home` também passou a zerar no reset, pelo mesmo motivo do Salão zerar
— ver § Salão da Guilda -- home reset, mais abaixo, pro raciocínio completo.

- **`DELETE FROM guilda_bau` e `UPDATE guildas SET moedas = 0`** entram em
 `resetar_temporada()`, dentro da mesma transação do resto (`database.py`).
 Sem isso, jogador nível 1 saca o caixa da guilda no minuto seguinte ao
 reset — quem tem guilda começa a temporada rico, quem não tem começa do
 zero.
- **Log, convites e cooldowns de guilda não entram** — só o caixa
 (item + moedas) é progresso de temporada de verdade; o resto é estado
 estrutural da guilda (quem é membro, quando pode viajar de novo pra home),
 igual à razão que já valia pra `guilda_raide`/`guilda_home_cooldown`.
- **`admin.py`**: `PRESERVADO` ganhou a linha da guilda sobrevivendo e
 `GUILDA_RESET` é um campo novo no embed de confirmação (`embed_confirmacao`),
 separado de `TABELAS_APAGADAS` porque metade do que muda é `UPDATE`
 (`moedas`), não `DELETE` de tabela inteira.

### `chefes_derrotados` zerar é intencional — quebra a regra de "vida da conta" de propósito

A regra normal (ver "Roguelike acima do Selo") é que os 100% de material de
chefe 11+ são únicos **na vida da conta**, nunca por temporada — farm depois
disso é o late game, de propósito. `resetar_temporada()` contraria essa regra
por decisão explícita: temporada nova devolve o drop cheio (100%) pra todo
mundo, mesmo quem já tinha matado aquele chefe antes do reset. Já estava
implementado (`TABELAS_APAGADAS` em `admin.py`, linha de `chefes_derrotados`
em `resetar_temporada()`) — este parágrafo só registra que é escolha, não
esquecimento: as duas regras coexistem porque olham pra relógios diferentes
("nesta conta, alguma vez" vs. "nesta temporada").

## Reset individual — `rpg resetarjogador`

Corrige a escolha de **um** jogador (classe e/ou profissão) sem tocar em
nível, atributos, equipamento ou andar — não é a mesma coisa que `rpg
resetartemporada` (esse zera todo mundo e mais tabelas, ver seção acima).
Motivo de existir separado: alguém escolhe classe errada, ou pede pra trocar
de ofício antes de existir troca paga, e não faz sentido apagar o progresso
de torre da pessoa só por causa disso.

- `database.resetar_classe_profissao(user_id)` zera `classe`, `profissao`,
 `prof_nivel` (volta a 1) e `prof_xp` (volta a 0) — mesmo raciocínio do
 reset de temporada: deixar o nível de ofício sobreviver faria quem
 reescolher a mesma profissão pular a curva de craft.
- Mesma `ConfirmarAcao` (botão Confirmar/Cancelar) do reset de temporada —
 generalizei a view em vez de duplicar, os dois comandos usam a mesma
 classe agora. Sem backup do `.db` aqui: o alcance é uma linha só, não o
 servidor inteiro, backup completo seria desproporcional.
- Recusa rodar se o jogador já está sem classe e sem profissão (nada a
 fazer) e se o alvo nunca rodou `rpg comecar`.
- Testado contra cópia isolada do banco: só as 4 colunas do alvo mudam,
 nível/atributos/equipamento/título do mesmo jogador e a linha de outro
 jogador ficam bit a bit iguais a antes.

## Profissões e craft

- **Cada jogador escolhe uma única profissão** entre Minerador, Forjador,
 Alquimista, Joalheiro e Arcanista.
- Isso torna o craft **dependente de trade entre jogadores**, que ainda não
 existe. Sem trade, Minerador acumula material que não usa e Forjador fica
 sem insumo — trade precisa voltar junto com o craft, não depois.
- Arcanista fica com encantamento (melhora equipamento pronto). Junto com o
 Joalheiro, vira a camada final de progressão defensiva — o que faz sentido
 agora que defesa só vem de equipamento.

## Rebalanceamento de craft — gates, custo e curva

Contexto: as receitas de Forja estavam altas demais pra quando o item
libera (Placas Polidas nível 5, Couraça nível 7, peças do Selo nível 9 —
quase o teto do ofício) e o material de andar custava x5 por craft, o que
deixava o grind de ofício mais lento que o grind de torre. A curva de XP de
ofício (`50 * nível^1.4`) também crescia mais rápido que a de personagem.

O que mudou, tudo em `profissoes.py` (`RECEITAS`, `xp_para_subir`):
- **Gates caíram**: Placas Polidas 5→3, Couraça de Cinzas 7→5, as quatro
  armas do Selo (Lâmina/Adaga/Cajado/Manoplas) 9→7, Manto do Selo 9→8 —
  o Manto ficou um nível acima das armas de propósito, pra não destravar
  tudo do Selo de uma vez só.
- **Material de andar caiu de x5 pra x3** em toda receita que usava x5
  (as quatro peças normais de Forja + Pena do Trovão nas receitas do
  Selo). Fragmento do Selo (drop de chefe, item separado) caiu de x3 pra
  x2 nas receitas do Selo.
- **XP de craft caiu bem**: Couro Batido 35→20, Malha Reforçada 120→45,
  Placas Polidas 260→80, Couraça de Cinzas 550→130, todo item do Selo
  900→180.
- **Curva de nível de ofício trocou pra `50 * nível`** (era `50 *
  nível^1.4`), substituindo a fórmula antiga por inteiro — vale pra Forja
  e Alquimia, as duas usam a mesma função. Isso é redução de custo, não
  perda de poder de build nenhuma: não precisou de compensação nem
  migração (`prof_xp` guarda progresso *dentro* do nível atual, não XP
  acumulado desde o início, então a troca de fórmula só muda o quanto
  falta pra próxima subida, sem zerar nada).

## Melhoria (+1/+2) e desmanche de equipamento

Dois comandos novos, `rpg melhorar` e `rpg desmanchar`, em `profissoes.py`.
O fork de arquitetura real aqui: `jogadores.arma`/`armadura` guardam só a
chave do item equipado (slot único) e `inventario` é só quantidade por
chave — não existe conceito de "cópia individual" de um item. Decisão:
**o nível de melhoria vive numa tabela nova, `upgrades(user_id, item,
nivel)`, chaveada por (jogador, item) — não pelo slot equipado nem por uma
instância de inventário.** Isso faz o upgrade sobreviver a desequipar e
reequipar (que só criar uma coluna por slot não faria — trocar de arma e
voltar perderia o nível). O preço: se o jogador tiver duas cópias do
mesmo item, elas compartilham o mesmo nível salvo — o jogo nunca teve
por que distinguir cópias, e forçar isso agora seria reescrever
`inventario` inteiro por uma mecânica que ninguém vai esbarrar (ter duas
cópias exatas do mesmo equipamento topo de linha não tem uso).

`stats()` em `bot.py` aplica o bônus lendo essa tabela antes de montar a
ficha de combate (`com_bonus_upgrade`), então o `+12%` por nível cai
sobre o `atk`/`def` *base* do item, não sobre o dano final calculado.

Decisões de quem ganha o quê, fechadas na conversa:
- **Desconto de Forjador em `rpg melhorar` é 25%**, em material e moeda,
  nos dois tiers (+1 e +2).
- **`rpg melhorar` funciona pra qualquer jogador** — o comando lê
  `arma`/`armadura` equipada e o ferreiro de qualquer andar serve. Mas o
  **XP de ofício (25/50 do upgrade, 40% do craft no desmanche) só é
  concedido a quem tem `profissao == "forja"`** — do contrário um
  Alquimista subiria nível de Forja sem nunca ter escolhido o ofício.
  Coerência com o resto do craft: XP de ofício sempre esteve atrelado a
  quem exerce o ofício, nunca a "quem pagou pela ação".
- **Peça comprada em loja (sem receita, ex. Espada de Ferro) desmancha
  pelo material do andar dela** — usa o mesmo andar→material da Forja
  (`ANDAR_MATERIAL`), com quantidade sintética de 3 (a mesma base das
  receitas pós-corte), 50% de volta. XP de craft nesse caso é 0 — a peça
  nunca foi craftada, não tem XP de craft pra devolver 40% de nada.

## Correção — desmanche furava o gate de escassez, melhorar elemental estourava KeyError

Dois bugs no mesmo par de funções (`custo_melhorar`/`refund_desmanche`,
`profissoes.py`), corrigidos juntos porque a correção de um exigia a mesma
mudança de arquitetura que o outro precisava pra existir.

- **`refund_desmanche` somava `+ nivel_upgrade` a *todos* os materiais da
  receita**, mas `custo_melhorar` só cobra **um** material por melhoria
  (`ANDAR_MATERIAL[andar_min]`). Nas peças do Selo, que têm dois materiais
  (`fragmento_selo` do chefe + `pena_do_trovao` do andar), isso fazia
  craftar → +1 → +2 → desmanchar devolver *mais* `fragmento_selo` do que o
  craft gastou — convertendo material farmável do andar 9 em material de
  chefe capado (100% na primeira vitória, 15% depois) a taxa fixa. Furava o
  próprio gate de escassez que o fragmento existe pra impor.
- **Correção: extraí `material_de_upgrade(item_chave)`**, fonte única que
  as duas funções chamam — `custo_melhorar` já usava essa lógica
  (`ANDAR_MATERIAL[ITENS[item_chave]["andar_min"]]`), só faltava
  `refund_desmanche` consultar a mesma chave em vez de reimplementar a
  expressão. `refund_desmanche` agora só soma `nivel_upgrade` ao material
  que bate com `material_de_upgrade` — os outros materiais da receita
  (material de chefe, nas peças de dois materiais) recebem só o refund de
  50% do craft, nunca o bônus de upgrade. Duplicar a expressão nos dois
  lugares foi o que criou o bug; um helper compartilhado impede o próximo
  item com dois materiais de reabrir o mesmo buraco sem ninguém perceber —
  é exatamente o que o teste `test_nenhuma_receita_tem_saldo_positivo_*`
  (`tests/test_profissoes.py`) trava.
- **`ANDAR_MATERIAL` só tinha chave pros andares 1/3/5/7/9** (só onde tem
  ferreiro). As 24 armas elementais (Pacote 2) têm `andar_min` 11-15;
  `rpg melhorar` numa delas levantava `KeyError` direto — ninguém tinha
  sentido ainda porque a receita é nível 9 de Forja + 10.000 moedas +
  material de chefe, provavelmente nenhuma tinha sido forjada. Corrigido
  adicionando as 5 chaves que faltavam: `pluma_eterea` (11),
  `farpa_eletrica` (12), `estilhaco_gelido` (13), `cinza_quente` (14),
  `po_de_estrela` (15) — o **drop de chão do próprio andar da arma**, não
  o material de chefe que já é o gargalo do craft dela. Mantém o padrão
  "material do andar melhora equipamento do andar" que já valia de 1 a 9;
  os índices são consecutivos (11-15) e não só ímpares porque acima do
  Selo não tem ferreiro — cada andar tem exatamente um drop de chão, sem
  precisar pular nenhum.
- Com as duas correções juntas, uma arma elemental cai no mesmo formato
  das peças do Selo — dois materiais, e só o de chão (o `material_de_upgrade`)
  participa da melhoria/desmanche. Testado (`test_custo_melhorar_e_refund_desmanche_funcionam_para_todo_equipavel`,
  cobre os 24 itens elementais + todo o resto de `ITENS` com
  `tipo in ("arma", "armadura")`) e nenhuma receita do catálogo sobra saldo
  positivo no ciclo craft→+2→desmanchar.

## Pacote 1 — Acessórios, Guildas, Taverna e Raide

Quatro sistemas de um pedido só, implementados nessa ordem porque a raide
depende dos slots de acessório existirem primeiro. Nenhuma migração de
`jogadores` além de `anel`/`colar` — Fúria, Energia e tudo de guilda são
tabelas novas ou vivem fora do banco de jogador.

### Acessórios (anel, colar)

- **Duas colunas novas**, `anel` e `colar` (migração 8, `database.py`) —
 mesmo padrão de `arma`/`armadura`: guardam a chave do item, `rpg equipar`
 e `rpg perfil` foram generalizados pra aceitar os dois tipos novos em vez
 de ganhar comandos separados.
- **Peça dá bônus de atributo (+FOR/+DES/+CON/+INT), não de ATK/DEF direto.**
 `bot.stats()` agora monta um dict de atributos *efetivos* (base + bônus de
 anel/colar) antes de chamar `at.ficha()` — então HP máximo, mana máxima e
 ataque sentem o acessório automaticamente, sem fórmula nova. `rpg upar` e
 o custo de respec continuam lendo a coluna crua (base), então nada disso
 muda o que os pontos livres compram.
- **Requisito de skill lê o atributo base, não o efetivo, de propósito** —
 `habilidades.conhecida()`/`poder_base()` recebem o `jogador` (linha do
 banco) direto, nunca o `s['atribs']` já somado. Sem isso: equipar um anel
 de INT pra bater o requisito de 15, aprender a skill, e desequipar de
 novo — o pedido original avisou exatamente esse buraco.
- **INT de acessório é capado mais baixo que FOR/DES/CON (+2 por peça,
 contra +4) — o único atributo com um teto diferente.** Motivo: INT
 alimenta mana (`MANA_POR_INT=5`) e mana alimenta lançamento de skill. Um
 anel+colar de INT (+4 no total) dá +20 de mana — com a skill mais barata
 custando 12 mana, isso é **+1 lançamento extra**, nunca +2. Testado
 isoladamente: INT base 15 (mana 95) com anel+colar de INT vira INT 19
 (mana 115), +20 de mana, `20 // 12 == 1`. Se algum acessório futuro de
 INT desse mais que isso, o bônus por peça é o que precisa baixar, não o
 `MANA_POR_INT`.
- **O upgrade (+1/+2) nunca toca acessório** — não por trava nova, mas
 porque `rpg melhorar` só aceita `arma`/`armadura` como argumento
 (`profissoes.py`), então `db.set_upgrade` nunca é chamado com uma chave
 de anel/colar.
- **Exclusivos de raide** (`loja: False`, sem receita de craft) — não tem
 Joalheiro fabricando ainda nesse pacote; isso é trabalho de um pacote
 futuro, junto com craft/trade.

### Guildas (`guildas.py` + `database.py`)

Cinco tabelas novas (`guildas`, `guilda_membros`, `guilda_bau`,
`guilda_log`, `guilda_raide`), direto no `SCHEMA` (não atrás de migração —
mesmo tratamento que `upgrades` já tinha: tabela nova não precisa do
`ALTER TABLE` com `PRAGMA table_info`, só banco existente ganhando coluna
precisa).

- **`rpg guilda <subcomando>`, um comando só** — não usei
 `commands.Group` do discord.py; o resto do projeto sempre fez parsing
 manual do primeiro token (`profissoes.py` é o precedente) e misturar os
 dois estilos ia destoar mais do que ajudar.
- **"Convidar" adicionava na hora, sem fluxo de aceitar/recusar — revertido.**
 Era proporcional pra um grupo de amigos pequeno até virar bug de verdade:
 dava cargo, canal e linha em `guilda_membros` sem a pessoa concordar.
 Convite pendente com aceite explícito entrou depois — ver § Convite de
 guilda vira convite de verdade, mais abaixo.
- **Interpretação de "a guilda só vale com 3 membros"**: o pedido não
 disse o que isso trava, então decidi que trava **a viagem grátis pra
 home** — abaixo de 3 membros a viagem continua cobrando normal mesmo com
 `andar_max` liberado. Não é redundante com o mínimo de 3 da raide (que já
 é garantido: só dá pra ter 3 participantes numa raide se a guilda tiver
 3 membros, já que só membro entra). **Se a intenção era outra, é uma
 troca de uma condição só** (`MEMBROS_PARA_VALER` em `guildas.py`).
- **Viagem grátis é checada por membro, não por guilda**:
 `database.viagem_gratis_guilda(user_id, andar_max, destino)` só retorna
 `True` se o destino é a home da guilda **e** esse jogador específico já
 destrancou até lá — alguém atrasado na torre paga o preço cheio pra
 chegar na home dos amigos, mesmo a guilda "valendo".
- **`rpg viajar` ganhou um segundo motivo de graça** (`custo_e_motivo_viagem`
 em `bot.py`), ao lado da carroça do Bramm — os dois são checados
 independentemente porque um é global (qualquer andar, só no horário) e o
 outro é por-destino (só a home, sempre que já destrancada).
- **Líder que sai transfere pro membro há mais tempo na guilda**
 (`entrou_em` mais antigo entre quem fica) — regra simples, sem votação;
 numa guilda de amigos o critério objetivo evita a política.
- **Cargo e canal são criados só na fundação**, reaproveitando o padrão de
 `rpg priv` (overwrites por cargo em vez de por pessoa, categoria "Guildas"
 criada se não existir). Adicionar/remover membro depois é só
 `add_roles`/`remove_roles` no cargo já existente — o canal nunca precisa
 de overwrite novo por pessoa.
- **Baú tem log público sem filtro de dono e sem limite de saque** — igual
 ao pedido. `guilda_log` grava toda ação (convidou/expulsou/depositou/
 sacou/raide) com timestamp, `rpg guilda log` mostra as 10 mais recentes.
- Testado contra cópia isolada do banco: fundar, somar 3 membros, viagem
 grátis só no destino=home e só pra quem já destrancou, depositar/sacar
 com e sem saldo suficiente, log ordenado, cooldown de raide por guilda,
 transferência de liderança, e apagar a guilda (bau e log juntos) quando
 o último membro sai.

### Taverna

`rpg descansar` funciona em **qualquer andar até o 10** — não só nos
andares 1 e 10 como na primeira versão. Revertido depois que os andares
11-15 do Pacote 2 criaram uma regra de "sem comércio acima do Selo": fazia
sentido `descansar` (que cobra moeda, é comércio igual a poção) parar
exatamente nessa fronteira, e não fazia sentido continuar limitado a só
dois andares abaixo dela. `andares_altos.ANDAR_ACIMA_DO_SELO` é o mesmo
limiar que bloqueia loja/ferreiro/carroça — acima disso, **sem descanso
pago nenhum**, mesma régua.

- Continuam existindo só dois taverneiros de verdade com fala própria
 (Sera no andar 1, Eco de uma Taverneira no andar 10, tipo `"taverneiro"`
 em `npcs.py`). Nos outros andares (2-9) o comando funciona sem exigir NPC
 físico — texto genérico ("Você monta acampamento...") no lugar da fala.
 `rpg npcs`/`rpg falar` continuam só reconhecendo os dois taverneiros
 nomeados; o comando `rpg descansar` é o único que não depende deles.
- **Preço derivado dos preços reais em `ITENS` — substituído depois.** A
 versão original cobrava por HP/mana faltando (`2 🪙/HP`, `12 🪙/mana`,
 sempre mais caro que a melhor poção por unidade). Na prática saía mais
 caro que várias poções pra quem voltava quase morto de uma luta de
 chefe — trocado por preço fixo + cooldown, ver § Preço do descanso —
 fixo, travado por cooldown, mais abaixo.
- **`rpg descansar` cura só o que falta** (HP e mana até o teto) — isso
 não mudou com o preço fixo, só deixou de afetar o custo (ver seção
 nova).

### Raide — «Sua Majestade do Andar Nenhum»

- **Reusa o motor de `combate.py` em vez de duplicar** — `Luta`/
 `Combatente` já fazem "HP × participantes" sozinhos (`hp_chefe = chefe["hp"]
 * len(combatentes)`), então o chefe da raide é só um dict novo
 (`game_data.RAIDE_CHEFE`, fora de `ANDARES` porque não destranca andar).
 `PainelRaide` é uma **subclasse** de `PainelLuta` que só troca o que
 acontece na vitória (recompensa pro baú, não pro jogador) — derrota e
 abandono chamam as funções de `combate.py` sem mudar nada, incluindo a
 penalidade normal de morte.
- **Descoberta ao encaixar a subclasse**: `PainelLuta.on_timeout()` não
 passava pelo `fim_da_luta()` — duplicava a checagem de vitória/derrota
 inline **e** chamava `finalizar_vitoria`/`PainelLuta(luta)` direto, sem
 indireção nenhuma. Isso significava que uma rodada de raide que
 estourasse o timeout (60s sem clique) ia cair na recompensa **individual**
 errada. Corrigido em `combate.py`: `on_timeout` agora chama
 `self.fim_da_luta()` (então a subclasse decide o que é vitória) e
 `self._continuar(luta)` no lugar de instanciar `PainelLuta` fixo — um
 método novo, `_continuar()`, que `PainelLuta` implementa retornando ela
 mesma e `PainelRaide` sobrescreve retornando ela mesma com
 `guilda_id`/`iniciador_id`. Sem essa correção o bug só apareceria em
 produção, numa rodada específica, difícil de reproduzir.
- **HP/ATK/DEF do chefe** (850/82/18) calibrados um pouco abaixo do chefe
 do andar 7 (890/91/20) de propósito — com HP multiplicado por
 participante e recompensa modesta, o risco tem que ficar baixo pra bater
 com "farma sem risco" do pedido.
- **Recompensa: 800 🪙 + 2 acessórios aleatórios, tudo pro baú**,
 nunca pra mochila individual. Vencedores recuperam HP e mana cheios (like
 uma vitória normal), mas **zero XP, moedas ou progresso de andar
 individual** — testado isoladamente: banco antes/depois idêntico em
 nível/xp/moedas/andar de cada jogador, só HP/mana mudam.
- **Sala de espera é uma classe própria** (`SalaDeEsperaRaide`), não
 subclasse de `SalaDeEspera` — `validar()` (checa guilda, não "mesmo
 andar que o anfitrião"), o mínimo de 3 pra começar, e o texto do embed
 são diferentes o bastante pra herança não economizar código de verdade.
 O botão "Entrar" só aceita quem é membro da mesma guilda do anfitrião.
- **`rpg raide` só abre dentro do canal da própria guilda** — compara
 `ctx.channel.id` com `guilda['canal_id']`.
- **Cooldown 1x/dia é por guilda** (`guilda_raide`, tabela própria), não
 usa o `cooldowns` de jogador — testado que o cooldown seta e reporta o
 tempo restante corretamente.
- **`Server Members Intent` precisa estar ligado** no portal do Discord
 (`bot.py` já pede `intents.members = True`) — sem isso, atribuir/remover
 cargo em `convidar`/`expulsar`/`sair` não resolve o `discord.Member` de
 forma confiável.
- **`rpg raide` não usa `raid` como apelido** — `combate.py` já registra
 `"raid"` como alias de `rpg party` (`party`/`grupo`/`raid`, de antes desse
 pacote). Só apareceu num teste de integração que sobe o `bot.py` inteiro
 de verdade (`discord.ext.commands` recusa registrar um alias duplicado) —
 nenhum teste isolado por módulo pegaria isso. `rpg raide`/`rpg audiencia`
 no lugar.

## Pacote 2 — Andares 11-15, condições no jogador, A Guia, reconquista

Acima do Selo (andar 10). Não depende do Pacote 1 (guildas/raide/acessórios),
mas foi combinado com ele: acessórios (anel/colar) e o padrão de bônus de
atributo por equipamento das armas elementais usam a mesma máquina.

### Condições no jogador — a inversa do que já existia

Até aqui, `condicoes.py` só via usado em uma direção: skill de jogador →
chefe (Ruptura deixa o chefe vulnerável, Pancada Atordoante trava o turno
dele). Esse pacote pediu a inversa: chefe → jogador. O motor genérico já
aguentava isso sem mudança (`alvo` sempre foi "chefe" **ou** um `user_id`) —
só faltavam 3 tipos de condição novos e os pontos de consulta certos:

- **`bloqueia_skill` (Choque)** — consultado no clique do botão Habilidade,
 antes do `MenuHabilidades` abrir (`condicoes.pode_lancar_habilidade`).
- **`chance_erro` (Vendaval)** — consultado no loop de ataque, antes de
 `H["calcular_dano"]`; se acerta, o golpe simplesmente não sai (sem ganho
 de Fúria, sem gasto de nada) — `condicoes.chance_de_erro`.
- **`reduz_cura` (Ferida Sombria)** — consultado tanto no uso de poção
 (`BotaoPocao`) quanto dentro do próprio `tick()` quando uma
 `cura_por_rodada` resolve (`condicoes.reducao_cura_recebida`). Só reduz
 cura de HP, não de mana — poção de mana não é afetada.

Queimadura, Congelamento e Marca **não precisaram de tipo novo** —
reaproveitam `dano_por_rodada`, `pula_turno` e `vulneravel`, que já
existiam pro sentido jogador→chefe. `multiplicador_dano_causado` (Marca) e
`reducao_dano_recebido` (Voto de Ferro) agora são consultados nos dois
pontos de dano de `turno_do_chefe()` também, não só no ataque do jogador.

**A pegadinha de timing do pacote anterior voltou, mas com uma exceção
nova**: a maioria das condições ainda é consultada *depois* do `tick()` da
própria rodada (mesmo padrão de Pancada Atordoante/Ruptura — duração
passada pra `condicoes.aplicar()` precisa ser N+1 pra durar N rodadas de
efeito). Mas **Choque e Ferida Sombria são diferentes**: são consultados no
*clique do botão* (Habilidade / poção), que acontece *antes* do tick da
rodada em que a ação está sendo escolhida — então **não levam o +1**.
Testei os 6 isoladamente pra confirmar o número de rodadas de efeito real:

| Condição | Elemento | Consulta | `duracao` no dict | Rodadas de efeito |
|---|---|---|---|---|
| Queimadura | Fogo | dentro do `tick()` | 3 | 3 (literal) |
| Congelamento | Ar → não, Gelo | pós-tick (loop de ataque) | 3 | 2 |
| Choque | Raio | clique do botão (pré-tick) | 2 | 2 |
| Vendaval | Ar | pós-tick (loop de ataque) | 3 | 2 |
| Ferida Sombria | Sombrio | clique da poção (pré-tick) | 2 | 2 |
| Marca | Divino | pós-tick (`turno_do_chefe`) | 4 | 3 |

### Telegraph — dois rolls independentes por rodada

Pedido explícito: o chefe já tinha um "golpe carregado" (recua, avisa,
acerta todo mundo na rodada seguinte — `CHANCE_CARREGAR=30%`). A condição
elemental **não substitui isso nem compartilha o roll** — é um segundo
mecanismo, checado à parte (`Luta._talvez_telegrafar_condicao`,
`CHANCE_TELEGRAFAR_CONDICAO=25%`), só pra chefes com a chave `"elemento"`
no dict (andares 1-10 não têm, nunca entram nesse sistema). Na mesma
rodada o chefe pode: resolver uma condição que telegrafou antes
(`_resolver_condicao_pendente`), **e** carregar/bater normal, **e** avisar
uma condição nova — os três não se cancelam. Isso foi decisão explícita
("dois rolls por rodada", não um XOR entre os dois) e é o que faz o chefe
"pender pra ATK" de verdade: mais coisa acontecendo por rodada, não só mais
dano por golpe.

- **Alvo do telegraph é sorteado e revelado na hora** (`Luta.embed()` mostra
 quem), não escondido — é isso que faz Defender virar decisão informada em
 vez de aposta cega, exatamente como o pedido descreveu.
- **Defender contra uma condição telegrafada corta a duração pela metade**
 (mínimo 1), não anula. Escolhi essa regra (em vez de negar por completo)
 porque "Defender anula" já é o que o golpe carregado faz — condição
 tendo o próprio efeito (mais fraco, não nulo) mantém os dois mecanismos
 distintos. Testado: sem defender a duração sai cheia, defendendo corta
 pela metade.

### Refino em `combate.py` que a raide já tinha exposto uma rachadura

Ao escrever o telegraph, percebi que `PainelLuta.on_timeout()` não
passava pelas mesmas checagens de vitória/derrota que `registrar_acao` usa
via `self.fim_da_luta()` — tinha lógica duplicada inline. Isso não
importava pra luta normal (as duas cópias concordavam), mas qualquer coisa
que dependesse do **estado da luta no momento exato da checagem** (como o
telegraph, que só existe em `self.preparando_condicao`) rodava o risco de
comportar diferente se uma rodada estourasse o timeout. Não achei um bug
de verdade dessa vez (diferente do `_continuar()` que a raide forçou no
Pacote 1) — mas como já tinha próxima ao ponto, simplifiquei
`on_timeout()` pra chamar `self.fim_da_luta()` também, removendo a
duplicação por completo.

### Andares 11-15 — sem paredes, sem loja

Cinco entradas novas em `game_data.ANDARES` (não um dict separado): isso
faz `ANDAR_MAXIMO = max(ANDARES)` virar 15 sozinho, e todo o motor de
`rpg boss`/`rpg party`/`rpg viajar` já existente funciona nos andares novos
sem tocar em uma linha desses comandos.

- **Curva dobrada, só em ATK e DEF, não em HP** — incremento por andar
 1-10 era `+13 ATK`/`+3 DEF`/`~+120 HP`. Nos andares 11-15: `+26 ATK`,
 `+6 DEF`, **HP manteve o incremento antigo** (~+120/andar) — literal do
 pedido, "o chefe pende pra ATK, não pra HP".
- **Calibração testada contra o alvo "~6 turnos pra matar um nível 20"**:
 simulei uma build nível 20 razoável (Guerreiro, FOR 40/CON 22, equipamento
 de craft do andar 9 — `lamina_selo` + `manto_selo`, o melhor disponível
 antes desse pacote) contra o chefe de cada andar, ignorando Defender/
 poção/esquiva (pior caso). Resultado: andar 11 fica bem perto do alvo
 (**4,9 turnos**); 12-15 ficam progressivamente mais rápidos pro **mesmo**
 personagem (4,2 → 3,6 → 3,2 → 2,8, fase 2 do 15 em 2,4) porque a curva
 dobrada empilha e a penetração de armadura (`PENETRACAO_POR_ANDAR`) já
 escalava com o andar antes desse pacote. Isso é o esperado, não um erro
 de conta: o alvo de "~6 turnos" vale pro andar de entrada (11); 12-15
 devem doer mais pro mesmo personagem — é o que empurra o jogador a
 melhorar nível/equipamento (armas elementais) pra continuar subindo. Se
 o playtest mostrar que ficou duro demais rápido demais, o ajuste é nos
 valores de ATK/DEF de `game_data.ANDARES[12..15]`, a fórmula de
 penetração não precisa mudar.
- **Monstros comuns (caçar/explorar) NÃO dobraram** — só o chefe usa a
 curva nova. Caçada/exploração continuam de baixo risco por design (ver
 "Combate: dois motores diferentes" em `arquitetura.md`); dobrar ali
 também tornaria o grind normal desproporcional ao que o pacote pediu.
- **Sem loja, ferreiro nem carroça acima do andar 10**: implementado de
 três jeitos diferentes, cada um no lugar certo —
 1. **Ferreiro**: simplesmente não cadastrei nenhum NPC tipo `"ferreiro"`/
    `"mercador"` nos andares 11-15 (só `"guia"`). `rpg melhorar`/`rpg loja`
    já falham sozinhos por não achar o NPC — nenhum código novo precisou.
 2. **Loja/comprar**: esses dois comandos vendiam poção "em qualquer
    andar" olhando `andar_max`, não o andar atual (comentário antigo em
    `npcs.py` confirma que isso é de propósito pros andares 1-10). Andar
    11+ precisou de uma checagem explícita no início de `loja()`/
    `comprar()` comparando `j["andar"]` (onde você está agora) com
    `andares_altos.ANDAR_ACIMA_DO_SELO`.
 3. **Carroça**: `gratis_carroca` também precisou de checagem — sem isso,
    quem já conhece o Bramm (andar 3+) viajaria de graça até o andar 15
    também, porque a graça da carroça nunca olhava o destino antes.
- **`ANDAR_ACIMA_DO_SELO = 10` mora em `andares_altos.py`**, não duplicado
 em cada arquivo que precisa dele (`combate.py`, `bot.py`) — os dois
 importam de lá. É o único número que aparece em três lugares diferentes
 do pacote (loja, carroça, reconquista), então ganhou um dono só.

### Fase 2 do andar 15

`ANDARES[15]["boss"]["fase2"]` é um dict parcial (`atk`, `def`, `elemento`,
`drops` novos) que `Luta.verificar_fase2()` mistura por cima do chefe
atual quando `hp_chefe` cruza 50% do máximo — chamado depois de toda fonte
de dano do jogador (ataque normal, golpe carregado não conta porque é dano
do chefe, e as 3 skills que acertam o chefe diretamente). **Nada relacionado
a jogador é resetado** (Fúria, Energia, poções usadas, condições ativas
continuam) — só o dict do chefe muda. O material da fase 1
(`sombra_dobrada`) é guardado em `luta.materiais_extras` *antes* de trocar
o dict, porque senão seria perdido quando `chefe["drops"]` virasse o da
fase 2 (`prego_de_luz`) — os dois caem juntos na vitória final. Testado:
troca exatamente em 50%, não troca de novo, os dois materiais chegam na
mochila juntos.

### Material de chefe acima do andar 10 — chefes_derrotados

Tabela nova, `chefes_derrotados(user_id, andar, vezes)`. Acima do andar 10,
`combate.recompensar()` ignora a chance fixa que o dict de drops declara e
usa **100% na primeira vitória daquele jogador naquele andar, 15% da
segunda em diante** — sem isso, morrer de propósito pra "resetar" e matar
nunca vira estratégia melhor que só continuar. Testado com 300 repetições
depois da primeira vitória: 14,7% de acerto (alvo 15%). A tabela também
entra no `rpg resetartemporada` (nova linha em `TABELAS_APAGADAS`) — senão
alguém que já tinha matado um chefe 11+ antes do reset voltaria já na taxa
reduzida, sem nunca ter matado de novo depois do reset.

### Morte e reconquista acima do andar 10

`processar_morte()` (chamado tanto por caçada/exploração quanto pela
derrota de chefe) ganhou uma checagem: se `andar > 10` no momento da
morte, `andar` **e** `andar_max` voltam pra 10 — não só o andar atual, o
progresso todo acima do Selo. É a penalidade mais dura do jogo até agora,
de propósito: bate com o tom "sem loja, sem rede de segurança" que o resto
do pacote já estabeleceu pros andares novos.

### A Guia

Único NPC dos andares 11-15 (`tipo: "guia"` em `npcs.py`, uma entrada por
andar). A fala muda com a contagem de mortes — 3 níveis por andar (0, 3+,
7+ mortes), ficando mais gentil e mais convincente a cada limiar
(`andares_altos.fala_da_guia`). **Falar com ela já executa a descida**: não
tem confirmação nem segundo comando — `rpg falar guia` num andar 11-15 já
teleporta pro andar 10 na mesma resposta. Decisão deliberada: ela "pede que
o jogador desista", então a ação de desistir sendo instantânea (sem
"tem certeza?") é consistente com o personagem — hesitar não é a régua
dela. Descer é sempre grátis; subir nunca (não existe comando pra ela levar
pra cima).

### Armas elementais — craft, não drop direto

24 itens (6 elementos × 4 tipos: FOR, DES, cajado, manopla), todos
`loja: False`. Confirmado antes de implementar: dão craft na Forja (andar
≤ 10, onde ainda existe ferreiro) usando o material de chefe do elemento —
não dropam prontas do chefe. Isso evita criar uma segunda forma de
conseguir equipamento que não passa por craft nenhum, e reaproveita
`profissoes.RECEITAS`/`bancada_no_andar` sem precisar de sistema novo:
`bancada_no_andar` só checa se o andar atual tem um NPC do ofício certo,
nunca olhou o `andar_min` do item, então as receitas novas (nível 9 de
Forja) funcionam em qualquer um dos 5 ferreiros existentes.

- **Distribuição de tipo**: espada/arco aparecem em Ar e Fogo; machado/
 adaga em Raio e Sombrio; martelo/foice em Gelo e Divino — 2 elementos
 cada, como pedido. Cajado e manopla não entram nessa distribuição
 (aparecem nos 6 elementos, são o slot INT e o slot Monge/Destreza fixos).
- **"+6 de atributo" reaproveita o mesmo mecanismo dos acéssorios do
 Pacote 1** (`"atributo"` + `"bonus"` no dict do item) — `bot.py` só
 precisou generalizar `bonus_acessorios(anel, colar)` pra
 `bonus_atributo_equipamento(*pecas)`, incluindo a arma na soma. Diferente
 do anel/colar de INT (capados em +2 no Pacote 1 por causa do teto de
 lançamento de skill), as armas elementais de INT (`cajado_*`) usam o
 mesmo +6 das outras — o cajado é único por personagem (não dá pra somar
 dois), então o pior caso é sempre +6 INT = +30 mana, e a skill mais
 barata continua sendo só +2 lançamentos no limite, não uma progressão
 descontrolada.
- **Requisito de skill lê o atributo base**, não o efetivo com a arma —
 mesma regra do Pacote 1, mesmo motivo (equipar, aprender, desequipar).
 Testado: FOR base 14 + espada_vento (+6 efetivo = 20) continua bloqueado
 pro requisito de Pancada Atordoante (15 FOR); só destrava com a base de
 verdade em 15.
- **Upgrade (+1/+2) não escala esse bônus** — `rpg melhorar` só aceita
 `arma`/`armadura` como *slot* (não filtra por item específico), mas o
 bônus de atributo não é `atk`/`def`, então `com_bonus_upgrade` nunca
 encosta nele de qualquer forma — mesma proteção que já existia pros
 acessórios, automática por construção.

## Rodada 1 sem chefe

Na primeira rodada de qualquer luta de chefe, o chefe fica totalmente
parado — não ataca, não rola carregar, e (andar 11+) não rola nenhum dos
dois telegraphs de condição. Rodada 2 em diante, tudo volta ao normal sem
mais nenhuma mudança.

- **Atrás de uma constante**, `combate.RODADA_1_SEM_CHEFE = True` — desliga
 voltando pra `False`, sem mexer em lógica nenhuma.
- **A checagem entra primeiro em `Luta.turno_do_chefe()`**, antes até do
 `condicoes.pode_agir` (stun): se é rodada 1, o chefe fica parado por essa
 razão, independente de qualquer condição que o jogador já tenha aplicado
 nele. Golpe carregado e os dois rolls de telegraph nem chegam a rodar —
 não é "rola e ignora o resultado", é "não rola".
- **A raide herda a parte de `turno_do_chefe()` de graça**, por causa da
 subclasse (`raide.PainelRaide` não sobrescreve `turno_do_chefe`, usa o de
 `combate.Luta` direto) — não precisou de nada em `raide.py` pra isso.
 **Mas o golpe de iniciativa por DES não herdou**: `raide.iniciar_raide`
 tem a própria cópia dessa lógica (não chama `combate.iniciar_luta`), então
 precisou do mesmo `if not RODADA_1_SEM_CHEFE:` duplicado lá também.
 Verificado isolando os dois: com `random.random()` forçado a sempre
 "acertar" o chefe, nem `combate.iniciar_luta` nem `raide.iniciar_raide`
 causam dano — os dois respeitam a regra.
- **Iniciativa por DES**: verificado antes de mexer, como pedido. Ela existe
 hoje na luta de chefe, mas só nesse um lugar — o golpe de abertura em
 `iniciar_luta`/`iniciar_raide` (`at.chance_iniciativa(mais_rapido,
 destreza_monstro)`, o chefe acerta alguém antes da rodada 1 sequer
 aparecer na tela, se ganhar o roll). **Não existe nenhuma ordem por DES
 dentro de uma rodada** — os jogadores sempre atacam primeiro e o chefe
 sempre age depois, incondicionalmente, então "o jogador vem primeiro" já
 era estrutural. Esse golpe de abertura foi desligado pelo mesmo motivo do
 resto: ele aconteceria *antes* da rodada 1 até começar de verdade, o que
 contradiz "a rodada 1 é toda do jogador". Nenhum sistema de prioridade
 novo foi criado — só o gate na iniciativa que já existia.
- **Mensagem**: `Luta.embed()` ganha um campo fixo ("🕯️ O chefe ainda não
 reagiu") enquanto `self.rodada == 1`, no mesmo padrão visual de
 "carregando"/"preparando_condicao" — desaparece sozinho na rodada 2
 porque a condição do campo é literalmente `self.rodada == 1`. O log
 também registra uma linha ("[chefe] ainda não reagiu à entrada de
 vocês.") quando a rodada 1 resolve, pra aparecer no recap da rodada 2.
- **Não rebalanceei nada além disso** — de propósito. Calculei o efeito:
 andar 11 estava em ~4,9 turnos contra o alvo de ~6 (ver Pacote 2 acima);
 uma rodada inteira de graça pro jogador desloca a média geral pra perto
 de ~5,9 turnos efetivos — corrige o exagero que a curva dobrada tinha
 introduzido, não cria um novo. Os outros 14 chefes ficam ~10-15% mais
 fáceis pelo mesmo motivo (uma rodada a menos de dano recebido, sobre um
 total de poucas rodadas de luta). Nenhum ATK/DEF/HP de `game_data.ANDARES`
 mudou.

## Paginação de embeds

`rpg receitas` quebrou em produção: `400 Bad Request (50035) — Must be 25
or fewer in length` em `embeds.0.fields`. Causa raiz: um field por receita
de Forja, e as 24 armas elementais do Pacote 2 empurraram o catálogo (33
receitas) além do teto de 25 fields do Discord. Correção não foi um cap
local — virou infraestrutura compartilhada, porque o mesmo padrão (`for
item in lista: e.add_field(...)`, ou `"\n".join(linhas)` num field/description
só) apareceu em mais lugares.

### `paginacao.py` — módulo novo

Guarda os três limites do Discord que importam aqui, num lugar só:
`MAX_FIELDS_POR_EMBED = 25`, `MAX_CHARS_POR_FIELD = 1024`,
`MAX_CHARS_POR_EMBED = 6000`. Três peças:

- **`paginar(entradas, titulo, descricao, por_pagina=9)`** — recebe uma
 lista de `(nome, valor)` e devolve páginas, cada uma já truncada/agrupada
 respeitando os três limites **ao mesmo tempo**. O motivo de checar os
 três juntos, não só o de 25 fields: 9 fields por página quase no teto de
 1024 caracteres cada somam ~9.216 — já estoura o teto de 6.000 do embed
 inteiro sozinho, antes de qualquer field chegar perto do limite
 individual. Testado com fields de ~900 caracteres cada: a função quebra a
 página em 6 entradas, não nas 9 pedidas, exatamente por causa do teto de
 6.000 — "agrupar resolve os fields mas não isso", como avisado.
- **`PaginacaoView`** — botões ◀ ▶ editando a mesma mensagem, rodapé
 "Página X de Y", `interaction_check` restrito ao autor (resposta efêmera
 pra qualquer outro clique). **No timeout, `self.mensagem.edit(view=None)`
 — remove os botões de verdade, não só desabilita** (`item.disabled =
 True` foi o padrão usado em `SalaDeEspera`/`SalaDeEsperaRaide`
 anteriormente; aqui foi pedido explicitamente o oposto). Testado que o
 clique de quem não é o autor recebe `ephemeral=True` e não avança a
 página, e que o timeout deixa `view=None` na mensagem.
- **`enviar_paginado(ctx, entradas, titulo, cor, ...)`** — a função que os
 comandos chamam. Se só existe 1 página, manda o embed sem view nenhuma
 (sem botão à toa numa lista de 3 itens). Aceita `pagina_inicial`
 (1-indexada, o que o jogador digita) — fora do intervalo é recortado pro
 mais perto, não vira erro.

### Onde entrou

- **`rpg receitas`** (`profissoes.py`) — o que estava quebrado. Mudou de
 comportamento, não só de cap:
 - **Por padrão mostra só o que dá pra fazer agora** (nível de ofício +
   material + moedas conferidos) — é o que resolve 90% das consultas sem
   precisar de página nenhuma na maioria dos casos.
 - **`rpg receitas tudo`** mostra o catálogo completo, paginado.
 - **Armas elementais agrupadas por elemento**: `game_data.ITENS[chave]`
   ganhou a chave `"elemento"` nas 24 armas (não existia antes — só o
   `"bonus"`/`"atributo"` do Pacote 2). Um field por elemento com as 4
   armas daquele elemento na lista, marcadas ✅/🔒/⬜ individualmente —
   6 fields no lugar de 24. Testado com um jogador em Forja nível 10,
   moedas e material de sobra: `rpg receitas tudo` fica em 2 páginas (9
   receitas normais + 6 grupos de elemento = 15 entradas), nenhum field
   passa de 1024 nem a página de 6000.
 - Aceita `rpg receitas <página>` e `rpg receitas tudo <página>`.
- **`rpg inventario`** (`bot.py`) — trocou de "tudo numa `description`
 só" (arriscava o teto de 4096 da description, não capturado pelos três
 limites de field que `paginacao.py` guarda) pra um field por item,
 paginado. Testado com as **91 chaves de `ITENS`** todas na mochila de um
 jogador: 11 páginas, nenhuma quebra.
- **`rpg guilda bau`** (`guildas.py`) — mesma troca, de um field só com
 `"\n".join` pra um item por field. Moedas do baú viraram parte da
 `descricao` (repete em toda página) em vez de um field à parte. Testado
 com baú cheio das 91 chaves: 11 páginas.
- **`rpg loja`** — os dois fields fixos ("🧺 mercador", "🔨 ferreiro" com
 lista de itens dentro) viraram um item por field, com o nome de quem
 vende cada seção movido pra `descricao` (não perde o "quem vende" ao sair
 do agrupamento). Risco real era baixo hoje (catálogo por andar é
 pequeno), mas segue o mesmo modelo pra não repetir o problema se o
 catálogo por andar crescer.
- **`rpg habilidades`** e **`rpg titulo`** — achados na varredura pedida
 ("procure no código por montagem de embed dentro de laço"), não
 quebrados hoje (catálogo de habilidades por classe e de títulos ainda são
 pequenos), mas é **o mesmo padrão estrutural exato** do bug relatado:
 catálogo filtrado por categoria (classe / títulos conquistados) que só
 cresce com o tempo. Convertidos pro mesmo modelo agora, antes de
 quebrarem — que era justamente o pedido de não fazer "gambiarra que volta
 a quebrar no próximo conteúdo".
- **Avaliados e não alterados**, por serem coleções de tamanho fixo pequeno
 (não "lista de tamanho variável", o critério do pedido):
 `rpg profissao` (2 profissões), `rpg classe`/`rpg ascencao` (4 classes),
 `rpg status` (4 atributos), os fields de `Luta.embed()`/salas de espera
 em `combate.py`/`raide.py` (capados por `MAX_PARTY=4` + um punhado de
 campos condicionais fixos), `rpg guilda log` (já limitado a 10 no SQL),
 e os `add_field` estáticos de `embed_ajuda`/`admin.embed_confirmacao`
 (um por seção fixa do jogo, não por item de uma lista).

### Teste

Simulado exatamente o cenário que passou batido: um jogador com Forja
nível 10, moedas de sobra, **as 91 chaves de `game_data.ITENS` na
mochila** (então nenhuma receita fica bloqueada por material) e classe
escolhida com atributos altos (todas as habilidades da classe
destravadas). Chamando os comandos de verdade (`bot.bot.get_command(...).
callback`, o mesmo objeto que o Discord chamaria) contra esse jogador:
`rpg receitas`, `rpg receitas tudo`, `rpg inventario`, `rpg loja`, `rpg
titulo`, `rpg habilidades` e `rpg guilda bau` (baú também cheio das 91
chaves) — todos os embeds gerados ficaram dentro dos três limites, em
todas as páginas. Também testado: `rpg receitas 2`/`rpg inventario 2`
abrem direto na página pedida; clique de quem não é o autor da lista é
recusado com resposta efêmera; timeout tira os botões da mensagem.

## Dano de skill abaixo do ataque básico

Dado real reportado: nível 14, andar 5, «Corte Rápido» (2 golpes, 30
energia, gasta o turno) rendeu 48 de dano total contra 43 de um ataque
básico — a skill inteira valia 1,1 ataque, e um único golpe dela valia
pouco mais da metade (~24) de um ataque básico sozinho. Diagnóstico feito
**antes** de qualquer alteração, como pedido.

### 1. Fórmula de cada uma das 8 skills, como estava

Base comum: `habilidades.poder_base(jogador) = at.ataque(atributo_da_classe)
= 5 + 2*atributo` — **sem o bônus de atk da arma** (`at.ataque(valor,
bonus_arma=0, ...)`, chamado sem o segundo argumento). `combate.
_rolar_dano_habilidade(c, multiplicador, critico_extra=0)` monta
`base = poder_base * multiplicador * fator_afinidade`, aplica variação
±15% e crítico, e devolve o bruto — quem chama decide se passa por
`aplicar_defesa` ou não.

| Skill | Classe | O que fazia | Dano? |
|---|---|---|---|
| Dardo Arcano | Mago | `mult=1.0`, ignora defesa | Sim |
| Ruptura | Mago | condição (+20% dano recebido no chefe) | Não |
| Golpe Aberto | Guerreiro | `mult=0.9`, passa por `aplicar_defesa` + sangramento | Sim |
| Pancada Atordoante | Guerreiro | condição (chance de travar o chefe) | Não |
| Corte Rápido | Ladino | 2× `mult=0.6` (+10pp crítico), cada um por `aplicar_defesa` | Sim |
| Ponto Cego | Ladino | condição (+45pp crítico próprio, 3 rodadas) | Não |
| Palavra de Alento | Orador | condição (cura por rodada em aliado) | Não |
| Voto de Ferro | Orador | condição (-20% dano recebido na party) | Não |

Só 3 das 8 causam dano direto — as outras 5 são controle/buff/cura puros,
calibradas com a própria régua delas (chance, duração, %) no pacote
anterior, e **não entraram nesse conserto** (não têm "dano" pra comparar
com ataque básico).

### 2. Crítico se aplica a dano de skill?

**Sim — já se aplicava**, ao contrário da suspeita. `_rolar_dano_habilidade`
rola `random.random() < (c.s["critico"] + critico_extra)` toda vez que é
chamada, usando o crítico da **arma equipada** (10% em arma de Força/
cajado, 18% em arma de Destreza/manopla) mais o bônus da própria skill
(só Corte Rápido tem, +10pp). O motivo de "nenhum crítico saiu na
amostra" é simplesmente sorte pequena numa amostra pequena — 18% de
chance por golpe não sair em 2 tentativas é ~67% de probabilidade, nada
incomum.

### 3. Em Corte Rápido, cada golpe rola crítico separado?

**Sim.** O `for _ in range(2):` chama `_rolar_dano_habilidade` duas vezes,
cada chamada com o próprio `random.random()` — sempre foi assim, não
precisou mudar.

### 4. Tabela antes do conserto

Simulação (não a amostra real, que é ruído demais pra 1-2 golpes):
personagem nível 14 com **investimento máximo no atributo da classe**
(base 5 + todos os 39 pontos livres = 44 — o melhor caso possível, pra não
dar desconto de "o jogador não upou direito"), arma de cada tier de andar
(1/5/9), 20.000 repetições por linha, dano médio já passando por defesa
onde a skill passa:

| Skill | Andar | Ataque básico (média) | Skill (média) | Razão |
|---|---|---|---|---|
| Dardo Arcano | 1 | 104,3 | 100,3 | **0,96** |
| Dardo Arcano | 5 | 108,2 | 99,8 | **0,92** |
| Dardo Arcano | 9 | 123,9 | 100,0 | **0,81** |
| Golpe Aberto | 1 | 104,2 | 86,5 | **0,83** |
| Golpe Aberto | 5 | 108,2 | 70,0 | **0,65** |
| Golpe Aberto | 9 | 123,9 | 59,0 | **0,48** |
| Corte Rápido (2 golpes) | 1 | 108,4 | 130,4 | **1,20** |
| Corte Rápido (2 golpes) | 5 | 106,8 | 105,7 | **0,99** |
| Corte Rápido (2 golpes) | 9 | 115,6 | 88,9 | **0,77** |

O dado real (razão ~1,1 no andar 5) bate com a simulação (0,99 no andar 5,
com investimento máximo — um personagem real, com pontos espalhados em
mais de um atributo, tende a ficar um pouco abaixo disso, então a conta
fecha). **A piora com o andar confirma a causa**: nenhuma das 3 skills de
dano usa o atk da arma, que é o que mais cresce (+8 no andar 1 → +82 no
andar 9) — Dardo Arcano (que ignora defesa, a única vantagem estrutural
que tinha) já nasce empatado ou perdendo até pro andar 1; Golpe Aberto,
que já entrega menos por levar sangramento junto, cai pela metade do
andar 1 pro andar 9. **FOR e INT não estavam "quebrados" fora disso** — o
problema é estrutural e único: falta o bônus de arma em `poder_base`, e
afeta as 3 skills de dano igualmente (Mago, Guerreiro e Ladino).

### A correção

**`habilidades.poder_base(jogador, bonus_arma=0)`** ganhou o parâmetro
que faltava — `at.ataque(atributo, bonus_arma)`, a mesma fórmula do
ataque normal. `combate._rolar_dano_habilidade` agora calcula
`_bonus_arma_de(c)` (o `atk` do item em `c.jogador["arma"]`) e passa pra
`poder_base` antes de multiplicar pelo multiplicador da skill.
**Consequência direta**: como skill e ataque normal passam a somar a
*mesma* base (`atributo` + `atk_arma`), o multiplicador da skill vira
**literalmente a razão skill/ataque-básico**, em qualquer nível e com
qualquer arma — não precisa mais recalibrar a cada andar novo, o problema
que motivou o pedido ("a fórmula precisa acompanhar o ataque total").

Multiplicadores novos, nomeados em `combate.py` (constantes, não números
soltos no meio da função):

- **`MULTIPLICADOR_GOLPE_ABERTO = 1.3`** — dano + sangramento (o efeito).
 Como Golpe Aberto passa pelo mesmo `aplicar_defesa` do ataque normal, a
 razão fica **exatamente 1,3 em qualquer andar** — testado: 1,306 / 1,300
 / 1,301 nos andares 1/5/9, a variação é só ruído de amostra.
- **`MULTIPLICADOR_CORTE_RAPIDO = 1.0`** por golpe — dois golpes somam 2,0
 ataques, como pedido ("cada golpe passa a valer perto de um ataque
 básico"). Testado: 2,14 nos três andares (constante, mas ~7% acima de
 2,0) — a diferença é o bônus de +10pp de crítico que a skill já tinha
 antes (`BONUS_CRITICO_CORTE_RAPIDO`, mantido: não é o crítico da arma
 subindo, é um bônus da própria skill, e o pedido foi só não mexer no
 crítico da arma).
- **`MULTIPLICADOR_DARDO_ARCANO = 2.0`** — dano puro. Como a skill ignora
 defesa e o ataque normal não, a razão **não fica travada em 2,0**: sai
 mais forte que 2,0 contra chefe com mais DEF (3,05 no andar 9) e um
 pouco abaixo de 2,0 contra DEF baixa (2,10 no andar 1) — o mesmo padrão
 "fraco cedo, mais forte tarde" que já era intencional pra essa skill
 antes desse conserto (ver "Primeira leva de skills" acima). Escolhi
 manter `mult=2.0` mesmo assim, em vez de compensar a fórmula pra fixar
 a razão em 2,0 sempre: complicaria a fórmula pra manter uma vantagem
 (ignorar defesa) que é o motivo da skill existir.

**Testado**: mesma simulação Monte Carlo (20.000 repetições/linha, mesmos
3 andares, mesmo personagem nível 14 com atributo no máximo) rodada de
novo com a fórmula nova — tabela acima "depois": Golpe Aberto trava em
1,30; Corte Rápido em 2,14; Dardo Arcano varia de 2,10 a 3,05 conforme o
DEF do chefe, como esperado.

### Regra registrada pra skills futuras (inclusive ascensões)

- **Skill de dano puro deve valer ~2 ataques básicos.**
- **Skill com efeito relevante (debuff, condição, control) junto do dano
 deve valer ~1,3 ataque + o efeito.**
- **A base do cálculo tem que ser a mesma do ataque normal**
 (`hab.poder_base(jogador, bonus_arma)`, não só o atributo) — qualquer
 skill nova de dano que só use `at.ataque(atributo)` sem o bônus de arma
 repete esse bug. As 12 ascensões (`game_data.ASCENSOES`, ainda sem
 skills próprias) precisam seguir essa mesma base quando ganharem
 catálogo.
- **Skill que ignora defesa (tipo Dardo Arcano) foge da regra dos "2,0
 exatos" de propósito** — a razão sobe com o DEF do alvo. Isso é aceito,
 não é bug: é a vantagem estrutural que justifica a skill.

## Convite de guilda vira convite de verdade

Contexto: `rpg guilda convidar @pessoa` adicionava na hora — cargo, canal,
linha em `guilda_membros`, sem a pessoa concordar com nada. Reportado como
bug, não feature: ninguém pode ser metido numa guilda sem aceitar.

- **Tabela nova `guilda_convites(guilda_id, user_id, convidado_por,
 expira_em)`, PK composta** — igual ao padrão das outras tabelas de
 guilda (`database.py`), direto no `SCHEMA`, sem migração numerada (é
 tabela nova, não coluna em tabela existente — mesmo raciocínio do resto
 das tabelas de guilda, ver `arquitetura.md`). A PK composta é o que
 impede duplicar convite: convidar de novo a mesma pessoa da mesma
 guilda vira `ON CONFLICT ... DO UPDATE`, renovando prazo e
 `convidado_por` em vez de criar uma segunda linha.
- **Sem agendador — expiração é checada na leitura.** Toda função de
 `database.py` que toca `guilda_convites` (`get_convite`,
 `convites_do_jogador`, `contar_convites_pendentes_guilda`,
 `criar_ou_renovar_convite`) chama `_limpar_convites_vencidos()` primeiro,
 que só faz `DELETE ... WHERE expira_em <= agora`. Convite vencido nunca é
 mostrado nem contado, e é apagado na próxima vez que qualquer coisa tocar
 a tabela — não precisa do bot estar de pé no momento exato do vencimento.
- **`rpg guilda convidar` só cria a linha pendente** — nenhum `add_roles`,
 nenhum `adicionar_membro_guilda`. `rpg guilda aceitar [nome]` é o único
 lugar que concede cargo de verdade (`_efetivar_entrada` em
 `guildas.py`), e só aí grava em `guilda_membros`.
- **Limite de 5 convites pendentes por guilda** (`LIMITE_CONVITES_GUILDA`)
 — só conta contra convite *novo*; renovar um convite existente (mesma
 pessoa, mesma guilda) nunca esbarra no limite, porque não é uma linha
 nova.
- **Nome da guilda em `aceitar`/`recusar` é opcional só quando a pessoa
 tem exatamente 1 convite aberto** — com 2+, o comando recusa e lista os
 nomes; é obrigatório então porque o mesmo jogador pode ter convite de
 mais de uma guilda ao mesmo tempo.
- **DM é o canal principal do convite, não o canal da guilda.** Detalhe
 que quase passou batido: o convidado ainda não tem o cargo da guilda
 quando o convite é criado, então ele não enxerga o canal privado dela
 (`view_channel=False` pra `@everyone`) — mandar a mensagem lá seria
 invisível pra quem mais precisa ver. `alvo.send(...)` manda DM com os
 detalhes e o botão; o canal onde `rpg guilda convidar` foi rodado só
 recebe uma confirmação curta pro líder. Se a DM falhar (`Forbidden`/
 `HTTPException` — DM fechada), o comando avisa isso no canal e lembra
 que o comando (`rpg guilda aceitar <nome>`) funciona de qualquer forma.
- **Botão "Aceitar" na DM é atalho, não o caminho oficial** — `timeout=None`
 na view, mas isso só evita o timeout *durante* aquele processo do bot;
 como o bot roda no PC do Rafael e reinicia com frequência, a view some
 da memória de qualquer forma bem antes das 24h do convite. Por isso a
 mensagem sempre cita o comando também, e o clique do botão roda
 exatamente as mesmas checagens do comando (guilda ainda existe? pessoa
 já está em outra guilda? convite ainda válido?) — nenhuma lógica
 duplicada de verdade, só o disparo é diferente.
- **`_guild_discord(guilda)` acha o servidor a partir do `canal_id`
 salvo** (`bot.get_channel(...).guild`), não de um `GUILD_ID` global —
 o projeto nunca guardou isso em lugar nenhum (só está documentado no
 `.env` de exemplo, nunca lido no código). Necessário porque o clique do
 botão acontece na DM, onde `interaction.guild` é sempre `None`.
- **Ao aceitar, todos os OUTROS convites pendentes da pessoa são
 apagados** (`db.apagar_convites_do_jogador`) — não só o da guilda que
 ela entrou. Ela só pode estar em uma guilda por vez, então convites de
 outras guildas ficariam órfãos (nunca puderam ser aceitos, já que
 `acao_aceitar` recusa se a pessoa já tem guilda).
- **Guilda desfeita com convite pendente**: `apagar_guilda` agora também
 limpa `guilda_convites` daquela guilda (junto com baú/log/raide, que já
 limpava). Então um convite pra guilda que não existe mais só sobrevive
 se a checagem rodar entre o desfazimento e a expiração natural — coberto
 mesmo assim por `acao_aceitar`/o botão checando `db.get_guilda(...)`
 antes de efetivar, e apagando o convite órfão se vier vazio.
- **Quem convidou saiu da guilda → convite continua valendo.** Não há
 checagem de "convidado_por ainda é membro" em lugar nenhum — o convite é
 da guilda, não da pessoa que mandou. `convidado_por` só é lido pra
 mostrar quem chamou, nunca pra validar o convite.
- **Log da guilda ganhou dois eventos em vez de um**: `guilda_log` grava
 `"convidou"` (líder manda o convite, como já era) e agora também
 `"entrou"` (na aceitação de verdade, ator é quem entrou). Antes só
 existia `"convidou"`, disparado no que hoje seria o momento de aceite —
 separar os dois deixa o log dizer a verdade: quem foi chamado nem
 sempre vira membro.

## Preço do descanso — fixo, travado por cooldown

Contexto: o preço derivado (2x o melhor custo-por-unidade de poção,
`decisoes.md` § Taverna, agora removido) cobrava rápido demais de quem
saía de uma luta de chefe quase morto — o descanso ficava mais caro que
comprar várias poções, ao contrário do que a taverna deveria ser (a opção
cômoda, não a mais barata, mas também não proibitiva).

- **Preço fixo de `CUSTO_DESCANSAR = 150` 🪙** (`bot.py`), substituindo o
 cálculo por HP/mana faltando. `game_data.MELHOR_CUSTO_POR_HP`/
 `MELHOR_CUSTO_POR_MANA`/`MULTIPLICADOR_DESCANSO`/
 `CUSTO_POR_HP_DESCANSO`/`CUSTO_POR_MANA_DESCANSO` foram removidos —
 nada mais lia essas constantes fora do próprio comando.
- **Preço fixo sozinho ficaria barato demais pra quem sempre está no
 talo de vida** — por isso ganhou `COOLDOWN_DESCANSAR = 2 * 60 * 60` (2h),
 mesmo padrão de cooldown de `cacar`/`explorar`/`boss` (tabela
 `cooldowns` já existente, `db.checar_cooldown`/`db.set_cooldown` — não
 precisou de coluna nem tabela nova).
- **Ordem das checagens importa**: já cheio → cooldown → moedas → cobra e
 seta cooldown, nessa ordem. Cooldown só é consumido no descanso que
 realmente acontece — checar moedas *antes* de setar o cooldown evita
 queimar as 2h de um jogador que não tinha os 150 🪙 na hora (ele tenta de
 novo assim que tiver dinheiro, sem esperar o cooldown à toa).
- **Continua curando só o que falta** (não é heal parcial proporcional ao
 preço) — com preço fixo, `rpg descansar` cura HP e mana até o teto de
 qualquer jeito, então o "só o que falta" agora só importa pro texto do
 embed (`Recuperado: HP +X · Mana +Y`), não pro cálculo de custo.

## Ajuda de veterano na party

Contexto: `rpg party` só deixava entrar quem tinha o mesmo `andar_max` do
anfitrião — um veterano nunca conseguia ajudar um amigo mais atrasado na
torre. A trava saiu, mas sem abrir brecha pra farmar chefe de andar baixo
usando gente de nível alto.

- **"Dono do andar" é `jogador["andar_max"] == andar_do_chefe`, calculado
 na hora que a luta começa — sem coluna nova no banco.** `Luta.__init__`
 ganhou um parâmetro `donos_ids` (default: todo mundo é dono) e marca
 `Combatente.dono` em cada participante. `iniciar_luta` (`combate.py`)
 calcula o conjunto certo pra `rpg boss`/`rpg party`; `raide.py` continua
 chamando `Luta(...)` sem esse parâmetro, então todo participante da raide
 segue contando como dono — comportamento dela não mudou.
- **Quem abre a sala continua precisando `andar == andar_max`** (regra
 velha, intocada) — o novato sempre hospeda. **Quem entra só precisa estar
 fisicamente no andar do chefe** (`SalaDeEspera.validar()` trocou a
 checagem de `andar_max` por `andar == self.andar_num`) — sem olhar
 `andar_max` nem nível de quem entra.
- **HP do chefe multiplica só pelos donos ativos** (`chefe["hp"] *
 max(1, nº de donos)`, não mais `len(combatentes)`) — veterano entra sem
 inflar o chefe, é ajuda pura. Isso continua valendo — é a ÚNICA coisa que
 `Combatente.dono` ainda controla (ver revisão abaixo).
- **Cooldown de chefe (15 min) já era consumido por todo `combatente` em
 `iniciar_luta`, sem distinção** — não precisou de mudança nenhuma pra
 valer também pra quem entra só de ajuda. Fugir continua sem queimar
 (`encerrar_por_abandono` só reseta cooldown de quem `fugiu`); sumir por
 timeout continua queimando — nenhum dos dois foi tocado.

### Revisão — vitória de chefe: todo participante leva tudo igual

Dois relatos de jogadores terminando luta em party sem subir de andar
mostraram que a versão original desta decisão (recompensa reduzida pra
ajuda, nada pra quem caiu, luta sem vencedor se os donos caíssem) tinha
efeito rejeitado na prática. Decisão do Rafael: se a party venceu, todo
mundo que estava lá — dono ou ajuda, caído ou de pé — leva tudo igual. Só
quem fugiu (`c.fugiu`) ou saiu por timeout (`c.saiu`) fica de fora.

- **`c.caiu` não filtra mais quem `recompensar()` paga.** `finalizar_vitoria`
 monta `vencedores` como `[c for c in luta.participantes if not (c.fugiu or
 c.saiu)]` — antes era só `c.ativo` (excluía quem caiu). Caído recebe XP,
 moedas, drop e sobe de andar igual a quem ficou de pé; a cura de HP/mana
 cheios em `recompensar()` sobrescreve o HP 0 que a queda gravou (a guarda
 `_estado_final_salvo` de `Combatente.salvar_estado()` já impede qualquer
 laço de regravar por cima depois — nenhum laço chama `salvar_estado()`
 depois que o embed de vitória já foi montado).
- **`fator_recompensa_ajuda()` saiu inteira**, com as constantes
 `REDUCAO_RECOMPENSA_POR_ANDAR_AJUDA`/`FATOR_MINIMO_RECOMPENSA_AJUDA` e os
 testes dela. XP e moedas não têm mais desconto de "ajuda" — `recompensar()`
 paga o valor cheio do dict do chefe pra todo mundo.
- **O `if combatente.dono` em volta de drop/tesouro (1-10) e do material por
 `chefes_derrotados` (11+) saiu.** As duas rotas de `recompensar()` agora
 rodam pra todo participante que chega até ali. Acima do Selo isso inclui
 `a_registrar_vitoria_chefe` — sem chamar pra ajuda também, ela ficaria pra
 sempre em 100% de chance (o dela nunca seria registrado), e como o andar
 11 é alcançável por `rpg viajar`, isso vira farm infinito.
- **Progressão de andar (`novo_andar`/`novo_max`) roda pra todo mundo.**
 `novo_max = max(j["andar_max"], novo_andar)` já cobre o caso de quem
 ajudou com `andar_max` mais alto — ela só se desloca, não perde progresso.
 O reset do andar 15 (roguelike, volta pro `ANDAR_ACIMA_DO_SELO`) também
 deixou de ser só do dono.
- **`encerrar_sem_donos()` saiu inteira**, junto com `Luta.donos_ativos` e o
 branch em `PainelLuta.fim_da_luta` que checava `not luta.donos_ativos`
 antes de `hp_chefe <= 0`. Sem dono gateando recompensa, "os donos caíram e
 só a ajuda terminou a luta" é só uma vitória normal — não precisa mais de
 caminho especial.
- **O que fica:** `donos_ids`/`Combatente.dono` continuam existindo, só
 pra escalar `hp_chefe` nos andares 1-10 (`chefe["hp"] * max(1, nº de
 donos)`) — descrito acima, intocado por esta revisão. `raide.py` não
 muda: lá todo participante já era dono por padrão.
- **A penalidade de morte não mudou.** Cair numa luta VENCIDA nunca paga
 `a_processar_morte` — só `finalizar_derrota` (derrota total) cobra, igual
 a antes desta revisão.

## Pix e trade

Contexto: craft sempre dependeu de trade pra fazer sentido (Minerador
acumula material que não usa, Forjador fica sem insumo — ver § Profissões e
craft acima, "trade precisa voltar junto com o craft, não depois"). Módulo
novo, `trocas.py`, com dois comandos.

- **`rpg pix @pessoa <valor>` funciona à distância; `rpg trade @pessoa`
 exige o mesmo `andar`.** Pix é só um número trocando de dono — não tem
 nada pra revalidar fisicamente. Trade move item, e a checagem de "mesmo
 andar" é o que dá função a estar junto na torre, além de já ser uma trava
 barata contra combinar trocas por fora enquanto um dos dois está preso em
 luta de chefe em outro lugar.
- **Sem taxa no pix, sem trava de "parking" de moedas antes de morrer** —
 decisão explícita: a penalidade de morte (20% das moedas) fica mais fraca
 se alguém puder mandar tudo pra um amigo antes de arriscar um chefe difícil
 e pedir de volta depois. Aceito por enquanto — não é sistema fechado, é
 uma lacuna conhecida.
- **Pix usa confirmação por botão (`ConfirmarAcao`-like, mas dedicado:
 `ConfirmarPix`), saldo revalidado de novo depois do clique, não só no
 comando.** Quem manda o comando já teve o saldo checado ali (pra não
 mostrar botão à toa), mas o clique em Confirmar dispara uma segunda leitura
 de `db.get_jogador` — se o saldo caiu no meio (outro pix, uma compra) o
 pix é cancelado mostrando o saldo atual, nunca deixa a moeda ficar
 negativa. Um pix pendente por vez por autor (`PIX_PENDENTES`, set em
 memória) — não tem sentido empilhar dois pix não confirmados do mesmo
 jogador.
- **Timeout do pix (60s) remove os botões (`view=None`), não só desabilita**
 — igual ao padrão de `paginacao.py`, diferente do `ConfirmarAcao` de
 `admin.py` (que desabilita mas deixa visível). Também corrigi ali uma
 ambiguidade que o `ConfirmarAcao` original tem: lá, `confirmado` vira
 `False` tanto no clique em Cancelar quanto no timeout, então o texto
 "Tempo esgotado" nunca aparece de verdade (a checagem `is False` sempre
 bate primeiro). Em `ConfirmarPix`, timeout deixa `confirmado = None` e só
 o clique em Cancelar seta `False` — os dois textos ficam alcançáveis.
 **Não toquei no `ConfirmarAcao` de `admin.py`** (fora do escopo pedido:
 só a trava do `equipar` e a linha de import deviam mudar em arquivo
 existente) — se algum dia sobrar tempo, vale corrigir lá também.
- **Trade não move item com melhoria (+1/+2).** Motivo estrutural, não
 escolha: `upgrades` é `(user_id, item, nivel)`, o bônus é preso ao par
 jogador+item, não a uma unidade dentro do inventário — não existe "qual
 cópia" transferir. Bloqueado com mensagem explicando e sugerindo `rpg
 desmanchar` ou oferecer uma cópia sem melhoria. Mesmo raciocínio de
 § Melhoria (+1/+2) e desmanche acima, agora aplicado numa direção nova.
- **Fragmento do Selo continua intransferível** — reusa a flag `vendavel:
 False` que já bloqueava a venda (`decisoes.md` não tinha essa flag
 documentada antes fora do contexto de loja; trade é o segundo lugar que
 lê ela, nenhuma flag nova precisou existir).
- **Item equipado não entra na troca de graça** — `rpg equipar` já tira o
 item do inventário, então a oferta (que só lê `db.get_inventario`) nunca
 vê a peça equipada. A única coisa que precisou de código foi a mensagem:
 se o nome digitado no modal bate com o que está equipado, a resposta diz
 "desequipe antes" em vez do genérico "você não tem esse item" — sem essa
 checagem extra a pessoa ia achar que é bug.
- **Interface do trade: uma mensagem, cinco botões (Item, Moedas, Limpar,
 Pronto, Cancelar), sem passo de convite/aceite separado.** Diferente do
 convite de guilda (que tem aceitar/recusar explícito): aqui não precisa,
 porque nada se move até os dois clicarem Pronto ao mesmo tempo — só
 participar da tela não compromete a nada. `Item`/`Moedas` abrem
 `discord.ui.Modal` (nome + quantidade / valor); é o primeiro uso de Modal
 no projeto.
- **Qualquer alteração na oferta (Item, Moedas, Limpar) derruba os dois
 ✅ de volta pra ⏳** — é a trava contra o golpe óbvio (confirmar uma
 oferta, trocar o conteúdo, torcer pro outro não reparar). `Pronto` em si
 é um toggle e não derruba a prontidão do outro lado — só mexer na oferta
 derruba.
- **Revalidação fica inteira no clique final do segundo `Pronto`, dentro de
 um `with db.conectar()` só** (`_commitar_troca` em `trocas.py`): saldo dos
 dois, quantidade de cada item no inventário de cada um, `andar` dos dois
 ainda igual, nível de melhoria de cada item ainda zero. Se qualquer coisa
 falhar, nada é escrito (a transação não commita) e a mensagem explica o
 motivo — testado isolado (cópia do banco): andar mudou no meio, saldo
 gasto no meio e item melhorado no meio das ofertas cancelam a troca inteira
 sem mover nem moeda nem item de nenhum dos dois lados.
- **`andar_max` de quem recebe não bloqueia nada** (mesma regra de compra
 em loja/craft: guardar sempre foi permitido) — só vira uma nota
 informativa no embed de conclusão ("🔒 «Espada de Brasas» só destrava lá
 no andar 7") quando a peça recebida está acima do `andar_max` de quem
 recebeu. A trava de verdade é em `rpg equipar` (ver abaixo).
- **Máximo de 8 itens distintos por lado**, checado só quando uma chave
 *nova* entraria na oferta — reduzir a quantidade de um item já ofertado
 ou zerar ele (0 remove da oferta) nunca esbarra no teto.
- **Um trade aberto por jogador** (`TROCAS_ATIVAS`, set em memória, cobre
 os dois participantes) — igual ao pix, sem tabela nova, porque se o bot
 cair no meio o estado só evapora (nenhuma troca "trava" um jogador depois
 de reiniciar).
- **Timeout de 3 minutos remove a view inteira** (`view=None`) igual ao
 pix — mensagem final avisa que expirou.

### Trava de andar no `rpg equipar`

Faltava desde sempre: `andar_min` só era checado na compra (loja/ferreiro),
então craft (que já ignorava loja) e agora trade davam volta na progressão —
alguém recebendo `espada_brasa` (andar 7) podia equipar no andar 1. Fechado
com uma checagem a mais em `equipar` (`bot.py`): se `ITENS[item]["andar_min"]
> j["andar_max"]`, recusa e diz o andar que falta destrancar. **Guardar
continua liberado** — só usar (equipar) trava. Testado isolado: item
recebido acima do `andar_max` entra na mochila sem erro, `rpg equipar`
recusa citando o andar certo, e destrancando o andar o mesmo comando passa a
funcionar sem mudar mais nada.

## Chefes 11-15 acertaram fraco demais, e guildas estavam morando acima do Selo

Contexto: jogadores batendo ~200 de dano por golpe nos chefes do andar 11+,
esvaziando o HP calibrado no Pacote 2 (que assumia uma build nível 20) rápido
demais. No mesmo período, líderes de guilda estavam usando `rpg guilda home`
pra fixar a home acima do andar 10 — andar sem loja/ferreiro/carroça, então
"morar" lá não tinha razão de ser e provavelmente era exploit de viagem
grátis.

- **HP do chefe 11-15 triplicou** (ex.: andar 11 foi de 1380 pra 4140).
 Só o campo `hp` — `atk`/`def` seguem a curva dobrada que o Pacote 2 já
 tinha estabelecido, não mexi de novo nisso.
- **ATK do chefe 11-15 subiu +75 uniforme em todos os 5 andares (+ fase2 do
 15)**, pra garantir que um golpe normal (não carregado) contra o jogador
 mais bem equipado possível acima do Selo (sem armadura nova lá — teto é
 `manto_selo`, def 54) sempre passe de ~150 de dano médio. Simulei os 5
 andares com a fórmula real de `combate.dano_do_chefe` (penetração por
 andar incluída): andar 11 fica mais justo (~154 de dano médio), 12-15
 sobram bem acima (174 → 262 na fase 2 do 15) porque a penetração cresce
 com o andar e o alvo de defesa é fixo — mesmo padrão de "fica mais forte
 andar a andar pro mesmo personagem" que o Pacote 2 já usava. Golpe
 carregado (×3 de dano, +25% de penetração) já passava de 150 antes disso,
 não precisou de ajuste. **Só ATK, não DEF** — o problema era o chefe
 morrendo rápido/batendo fraco, não o jogador acertando pouco.
- **`rpg guilda home` agora recusa andar acima de `andares_altos.
 ANDAR_ACIMA_DO_SELO` (10)** — mesma checagem que já existia pra andar
 inválido/não destrancado, em `guildas.acao_home`. Migração 10 em
 `database.init_db()` zera qualquer `andar_home` de guilda já preso acima
 do Selo de volta pro andar 1 (padrão de guilda nova) — sem isso, quem já
 tinha fixado lá continuaria com viagem grátis pro topo depois do fix.
- **A Guia agora fala periodicamente, não só quando o jogador fala com
 ela.** A cada `GUIA_A_CADA_ACOES` (3) comandos executados enquanto
 `andar > ANDAR_ACIMA_DO_SELO`, um `bot.after_invoke` global
 (`falar_guia_acima_do_selo`) reusa `andares_altos.fala_da_guia` e manda a
 fala como mensagem avulsa, contador zera e recomeça. **De propósito só
 fora de luta de chefe**: os botões do `PainelLuta` são interações do
 `discord.ui`, não passam por `@bot.command` nenhum, então nunca chegam
 nesse hook — uma luta de 5-7 turnos não ganha uma fala extra por clique.
 O contador (`jogadores.acoes_andar_alto`, migração 9) persiste no banco,
 não em memória, pra sobreviver a restart do bot. `rpg falar guia` continua
 com o comportamento antigo (teleporta na hora); como isso já baixa
 `andar` pra 10 antes do hook rodar, o after_invoke vê `andar <=
 ANDAR_ACIMA_DO_SELO` e não dispara — não precisou de exceção explícita.

## Comando de texto travado durante luta de chefe

Contexto: a luta de chefe é por turnos com botão (Atacar/Defender/Habilidade/
Mochila/Fugir na View), mas o canal continuava aceitando comando de texto
normalmente — dava pra `rpg comprar`, `rpg upar`, `rpg equipar` etc. no meio da
luta, o que anula o planejamento de recurso que é o ponto do turno. Furo real
em produção, ~10 jogadores.

- **Módulo novo, `travas.py`, registro em memória** (`user_id -> timestamp`),
 não coluna no banco. Motivo: a `Luta`/`PainelLuta` também só existem em RAM
 — se o bot cair no meio de uma luta, ela já não sobrevive ao restart, e uma
 trava sobrevivendo sozinha soft-lockaria quem estava lutando quando o bot
 caiu. Sem migração, sem tabela nova.
- **`commands.check` (`travas.fora_de_luta()`) em cada comando travado**, não
 `if travas.em_luta(...)` espalhado por dentro de cada função — o pedido
 explícito foi decorator, porque a lista de comandos vai crescer e um `if`
 por comando é fácil de esquecer de adicionar num comando novo. O predicado
 levanta `travas.EmLutaDeChefe` (subclasse de `commands.CheckFailure`), que
 `bot.on_command_error` já pega e responde com a mensagem padrão — um ponto
 só pra editar o texto do bloqueio no futuro.
- **`rpg guilda` não entrou como decorator** — é um único `@bot.command` que
 despacha várias sub-ações por string (`criar`, `bau`, `log`, `depositar`...),
 e só 3 delas de fato movem recurso: `criar` (gasta 5000 moedas pessoais),
 `depositar` e `sacar` (movem item entre mochila e baú). Decorar o comando
 inteiro travaria também `rpg guilda log`/`bau`/`status`, que são só leitura.
 Pra essas 3, `travas.bloqueado(ctx)` é chamado manualmente na primeira linha
 da função da ação — mesma checagem por baixo do capô, só que aplicada por
 sub-ação em vez de por comando.
- **Trava em todo mundo que entra na luta, no momento em que ela começa**
 (`travas.travar_todos([c.id for c in combatentes])`, logo no topo de
 `combate.iniciar_luta` e `raide.iniciar_raide`) — cobre solo, party (quem
 hospeda e quem só ajuda) e raide de guilda, porque os três passam pelas
 mesmas duas funções. Quem só está na sala de espera (`SalaDeEspera`, antes
 de clicar Começar) não está travado ainda — a trava é da luta, não da fila.
- **Liberação em 4 pontos, não só um** — não dá pra usar `try/finally` porque
 a luta atravessa vários cliques assíncronos ao longo de minutos, não é uma
 chamada síncrona só:
  1. `PainelLuta.encerrar()` — libera todo mundo que ainda estava na luta.
     Cobre vitória, derrota e abandono (todos os caminhos que passam por
     `registrar_acao` → `fim_da_luta` → `encerrar`).
  2. `PainelLuta.on_timeout()`, no branch que resolve a última rodada e a
     luta termina de vez — **não** passa por `encerrar()` (tem o próprio
     `travar()` + `mensagem.edit()`, refino já documentado em "Refino em
     combate.py..." acima), então precisou do próprio `destravar_todos()`.
  3. Botão Fugir, só no sucesso — libera só quem fugiu, na hora, sem esperar
     a luta acabar pros outros.
  4. `on_timeout()`, no loop que marca `c.saiu = True` (quem não clicou na
     rodada) — libera só esse jogador, também sem esperar o resto da party.
  Os 4 pontos são idempotentes (`destravar`/`destravar_todos` só faz `pop`
  com default) — não tem problema um `user_id` já ter sido liberado
  individualmente (pontos 3/4) quando o release em grupo (pontos 1/2) roda
  depois pra ele de novo.
- **`PainelRaide` (raide.py) não precisou de nenhum dos 4 pontos próprios** —
 é subclasse de `PainelLuta` e só sobrescreve `fim_da_luta()`; herda
 `encerrar()`, `on_timeout()` e o botão Fugir como estão.
- **Expiração de segurança, 20 minutos** (`travas.EXPIRACAO_SEGUNDOS`) — bem
 acima do pior caso plausível (`TIMEOUT_RODADA` de 60s × poucas dezenas de
 rodadas). É rede de segurança, não o caminho normal de saída: só entra em
 jogo se uma View morrer por exceção não tratada no meio de um callback, sem
 passar por nenhum dos 4 pontos de liberação acima.
- **Testado** com um harness que sobe o `bot.py` inteiro (módulos instalados,
 sem conectar no Discord) contra uma cópia do banco: trava aparece assim que
 `iniciar_luta` roda, some depois de `encerrar()` forçando vitória, fuga
 bem-sucedida libera só quem fugiu (o outro combatente continua travado), e
 os 18 comandos da lista aparecem com o check anexado (`Command.checks`)
 depois do wiring completo — os não-listados (`perfil`, `status`, `party`,
 `raide`, `descansar` etc.) confirmadamente continuam sem o check.

### `rpg descansar` ficou de fora da lista, de propósito (por enquanto)

Não travei — não estava na lista que o pedido enumerou. Mas vale registrar o
risco pra decisão futura: `descansar` escreve `hp`/`mana` direto no banco
(`db.atualizar_jogador`), e durante uma luta o HP "de verdade" do jogador só
existe em `Combatente.hp` (RAM), sincronizado pro banco em pontos específicos
(`salvar_estado()`). Descansar no meio de uma luta ativa desincroniza os dois:
o banco mostra HP cheio, mas a `Combatente.hp` da luta em andamento continua
com o valor de antes, e é ela que decide quem cai. Se isso aparecer como furo
na prática, a correção é a mesma receita: `@travas.fora_de_luta()` em cima do
`@bot.command(name="descansar", ...)`.

### Loja/comprar acima do andar 10: já bloqueado, não era um bug de código

O pedido também descrevia "a loja funciona acima do andar 10" como furo ativo.
Conferido no código atual: `loja()`, `comprar()` e `descansar()` (`bot.py`) já
têm a checagem `if j["andar"] > andares_altos.ANDAR_ACIMA_DO_SELO: recusa` —
implementada no Pacote 2 (commit `ed82aa6`, já na branch antes desta sessão).
Não achei nenhum caminho de compra que escape dela. Se o furo ainda aparece no
servidor real, o suspeito mais provável é o processo do bot rodando uma cópia
anterior ao commit `ed82aa6` — um restart depois do deploy mais recente resolve
sem precisar de código novo.

## Cooldown de troca de home da guilda

`rpg guilda home <andar>` mudava a home na hora, sem limite — dava pra trocar
toda hora. Agora é **1 troca a cada 3h, por guilda** (`COOLDOWN_HOME_SEGUNDOS`
em `guildas.py`), não por jogador — faz sentido junto com "só o líder muda a
home": é uma propriedade da guilda, não de quem está no comando dela num dado
momento.

- **Tabela nova, `guilda_home_cooldown(guilda_id PK, expira_em)`**, mesmo
 padrão de `guilda_raide` (cooldown por guilda já existente pra `rpg raide`)
 em vez de reaproveitar a tabela genérica `cooldowns` (que é chaveada por
 `user_id`, não `guilda_id`) ou generalizar as duas num table só — só duas
 instâncias desse padrão até agora, cedo pra abstrair.
 `checar_cooldown_home`/`set_cooldown_home` espelham
 `checar_cooldown_raide`/`set_cooldown_raide` linha a linha.
- **Não entra em `resetar_temporada()`** — mesma linha que `guilda_raide` já
 seguia: cooldowns e estrutura de guilda não zeram no reset de temporada,
 só progresso individual (inventário, cooldown pessoal, upgrades, chefes
 derrotados) e o caixa da guilda (baú + moedas — ver "Baú da guilda zera, a
 guilda sobrevive", que veio depois desta decisão e é a exceção).
- **A primeira troca depois de fundar a guilda não é bloqueada** — a home
 nasce em andar 1 direto em `criar_guilda()`, não passa por `acao_home`,
 então não existe linha em `guilda_home_cooldown` até a primeira troca de
 verdade. O cooldown só entra em jogo a partir da segunda.

## `rpg classe <classe> info` — prévia das habilidades base antes de escolher

Faltava jeito de ver as 2 habilidades base de uma classe sem escolher — e a
escolha trava pra sempre, sem troca depois (`classe_cmd` em `bot.py`), então
era escolha às cegas de verdade.

- **Entrou no `rpg classe` que já existia**, não em `rpg habilidades` (que só
 mostra as SUAS skills já destravadas) nem em 4 comandos novos por classe —
 opção escolhida entre as três justamente por ficar junto de onde o jogador
 já vai olhar antes de decidir. `rpg classe <classe> info` funciona **mesmo
 pra quem já tem classe** (o check de "info" vem antes do check de "você já
 é X" em `classe_cmd`) — é só consulta, não escolhe nem troca nada.
- **`embed_info_classe()` reaproveita `habilidades.habilidades_da_classe()`
 e `habilidades.NOME_RECURSO`** (import novo, `import habilidades as hab` no
 topo de `bot.py`) em vez de duplicar a lógica de filtrar `HABILIDADES` por
 classe — já existia em `habilidades.py`, sem risco de circular (esse módulo
 não importa nada de volta de `bot.py`).
- **Parsing é só `split()` e checar se a última palavra é "info"** — nomes de
 classe são todos de uma palavra só, não precisou de parser mais esperto.

## Teto de `rpg viajar` acima do Selo — 11 é o único andar 11+ que se viaja

Pedido explícito, contra o que o Pacote 2 tinha decidido ("todo o motor de
`rpg viajar` já existente funciona nos andares novos sem tocar em uma linha")
— revertido de propósito por instrução direta: **`rpg viajar` nunca alcança
acima do andar 11, mesmo que `andar_max` já esteja em 12, 13, 14 ou 15.**
Andar 12+ só se chega **lutando pra cima a partir do 11**, nunca de
teleporte — nem tendo derrotado aquele chefe antes.

- **`LIMITE_VIAJAR = andares_altos.ANDAR_ACIMA_DO_SELO + 1` (11)** em
 `bot.py`, checado em `viajar()` depois do check de `andar_max` (que
 continua existindo — quem não destrancou nem o 11 ainda vê a mensagem de
 "não destrancou", não a de teto).
- **Consequência que o pedido implica e vale registrar**: se o jogador sai
 do andar 12+ (viaja pra baixo, ou fala com a Guia, que já teleporta pra 10)
 sem morrer, ele **não recupera** o andar onde parou via `viajar` — só
 chegando lá de novo lutando, andar por andar, a partir do 11. `andar_max`
 continua marcando até onde ele já chegou (não é penalidade de progresso,
 só de acesso rápido) — diferente de morrer acima do andar 10, que já reseta
 `andar_max` pra 10 (ver "Morte e reconquista acima do andar 10"). Isso
 também tranca `rpg boss`/`rpg party` de reabrir no andar de origem: exige
 `andar == andar_max` pra hospedar (`checar_sala_do_chefe`), e sem `viajar`
 chegando lá, essa igualdade só volta subindo de novo a pé.
- **A listagem de `rpg viajar` sem argumento também respeita o teto** — só
 lista até `min(andar_max, 11)`. Se o jogador estiver fisicamente acima
 disso (chegou lá lutando, ainda não desceu), o andar atual aparece no fim
 da lista com uma nota, não como destino comprável — evita listar como
 "grátis (guilda)"/"X moedas" um andar que na real não dá pra comprar de
 volta.

## Roguelike acima do Selo — morte e vitória no 15 resetam a posição, não o histórico

Pedido explícito: os andares 11-15 viram uma "corrida" — nem morrer nem
terminar o andar 15 deixa vantagem de **posição** acumulada pra próxima
tentativa. `andar`/`andar_max` voltam pro andar 10 nos dois casos (morte
acima do 10, já documentado em "Morte e reconquista acima do andar 10"; e
agora também vencer o chefe do 15, que antes deixava o jogador parado lá em
cima sem fazer nada).

**`chefes_derrotados` (contagem de vitórias por andar, controla a chance de
material — 100% na primeira vez, 15% nas repetições) NÃO reseta em nenhum
dos dois casos.** Regra: a torre esquece onde o jogador estava, nunca quem
ele matou. Os 100% são únicos na vida da conta, por chefe — o farm longo
depois disso é intencional, é o late game.

- **Versão anterior desta decisão zerava os dois** (`db.
 resetar_chefes_andares_altos`, chamada em `processar_morte()` e
 `recompensar()`) — **errada, corrigida na mesma sessão antes de qualquer
 jogador real ser afetado**. Zerar o histórico junto com a posição fazia
 toda escalada nova recomeçar "como se fosse a primeira vez" pra todo
 chefe — o material caía sempre a 100%, e a faixa de 15% da repetição
 virava código inalcançável (nenhum jogador chegaria nela, porque nenhuma
 conta jamais teria uma segunda vitória registrada num chefe 11+). A
 correção foi só remover as duas chamadas e apagar a função — nenhuma
 mudança de schema, `chefes_derrotados` nunca devia ter sido tocada por
 esse reset.
- **Vencer o chefe do 15 força `novo_andar`/`novo_max` pro andar 10** em vez
 do avanço normal (`min(andar+1, ANDAR_MAXIMO)`, que pro 15 ficava parado
 ali sem fazer nada) — variável `completou_torre` em
 `combate.recompensar()`, mesmo destino da morte, mas continua **passando
 por `registrar_vitoria_chefe()` normalmente** antes disso (a vitória do 15
 conta pro histórico como qualquer outra).
- **Só afeta o `dono` da luta** — mesma regra de sempre (`combatente.dono`):
 quem entrou só de ajuda não perde posição nem histórico, só quem é dono é
 que sofre o reset de posição. Testado com uma party dono+ajuda: o dono
 morre no andar 12, o ajudante mantém andar/andar_max e histórico intactos.
- **`finalizar_vitoria()` tinha texto de flavor errado desde o Pacote 2** —
 o campo "🌑 Décimo Selo" ("a porta abre, tem uma escada que não acaba")
 era de quando `ANDAR_MAXIMO` era 10; ficou órfão apontando pro andar
 errado depois que o 15 virou o topo. Texto novo ("🌌 O topo, outra vez")
 é explícito nas duas metades da regra: a torre **guarda** as vitórias
 (por isso o material cai na chance baixa a partir daqui), e **não guarda**
 a posição (por isso `andar`/`andar_max` voltam pro 10 e a escalada
 recomeça em `rpg viajar 11`).
- **Achado no caminho, removido no cartão da guarda de main (ver § Guarda de
 main + setup no nível do módulo)**: `bot.py` tinha um `@bot.command(name="boss", ...)`
 inteiro (resolução instantânea, motor de `simular_combate`, o mesmo de
 `cacar`/`explorar`) que fazia sua própria conta de `novo_andar`/XP/drop e
 também citava "Décimo Selo". Era código morto — `combate.instalar()` chama
 `bot.remove_command("boss")` antes de registrar o `boss` de verdade (por
 turnos), então esse ali nunca rodava. `simular_combate` continua vivo
 (usado por `cacar`/`explorar`) — só o comando morto saiu.

## Ciclo 1 — "o banco fica seguro": WAL, backup de verdade, escada 3/1/1

Fechou os dois cartões Críticos do Kanban num pacote só, de propósito: os
dois mexem no mesmo `conectar()`/`backup_banco()` e resolvem a mesma
categoria de risco (perda ou corrupção silenciosa de save). Não mexeu em
`asyncio.to_thread` nem em conexão longa — isso fica pro próximo cartão, pra
não misturar "o banco resiste a colisão" com "o banco não trava o bot".

- **`conectar()` ganhou três `PRAGMA`**, sempre nessa ordem, entre o
 `connect` e o `row_factory`: `journal_mode=WAL`, `busy_timeout=5000`,
 `synchronous=NORMAL`. Motivo: modo `DELETE` (padrão do SQLite) não dá
 nenhuma folga pra uma escrita concorrente — a primeira colisão (raide de 3
 escrevendo quase junto, ou o backup automático lendo enquanto alguém
 escreve) já devolve `database is locked` na hora. WAL deixa leitor e
 escritor trabalharem ao mesmo tempo; `busy_timeout` dá 5s de espera antes
 de falhar; `synchronous=NORMAL` é o ajuste recomendado pra WAL (mais
 rápido que `FULL`, ainda seguro porque o WAL é append-only). `journal_mode`
 é persistente no arquivo, mas `busy_timeout`/`synchronous` são por conexão
 — os três ficam em `conectar()`, não num script de migração à parte, pra
 valer em toda abertura sem exceção (são 48 pontos de chamada, nenhum
 precisou mudar de assinatura).
- **Verificado empiricamente que o `aincrad.db-wal` é transiente com o
 padrão de conexão deste projeto** (abre e fecha uma conexão nova por
 chamada): o arquivo `-wal` só existe enquanto pelo menos uma conexão está
 aberta; quando a última fecha, o SQLite faz checkpoint automático e o
 `-wal` some de novo. Isso é comportamento normal do SQLite, não bug — só
 significa que "olhar se `aincrad.db-wal` existe" no checklist de
 verificação é uma foto de um instante, não um estado permanente. O que
 importa (e foi testado) é `PRAGMA journal_mode` respondendo `wal` e
 `PRAGMA busy_timeout` respondendo `5000` depois de qualquer `conectar()`.
- **`backup_banco()` trocou `shutil.copy2` pela API de backup do próprio
 SQLite** (`sqlite3.Connection.backup`), numa função nova,
 `backup_banco_para(destino)`, que `backup_banco()` (o backup manual do
 `rpg resetartemporada`) e o backup automático (`agenda.py`) chamam os
 dois. Motivo: com WAL ligado, uma cópia crua do arquivo `.db` pode
 simplesmente não conter uma transação que já foi confirmada (ela pode
 estar só no `.db-wal` ainda) — um backup assim falha silenciosamente, o
 que é pior que não ter backup, porque alguém confia nele. Testado direto:
 com uma conexão mantendo uma escrita fora do checkpoint, `conn.backup()`
 sempre trouxe o dado; a cópia crua só teria essa garantia por sorte de
 timing. O contrato de `backup_banco()` não mudou — ainda deixa a exceção
 subir, ainda devolve o caminho do arquivo; `rpg resetartemporada`
 (`admin.py`) não precisou de nenhuma alteração.
- **Backup automático em escada 3/1/1, não 5 cópias iguais de 2 em 2h.**
 5 cópias todas de 2 em 2h dariam só ~10h de profundidade — se alguém só
 percebe um problema (corrupção silenciosa, escolha errada, bug de
 economia) um dia depois, as 5 já rotacionaram e o estado bom já foi
 sobrescrito. A escada troca alcance por densidade: `recente_1/2/3.db`
 cobrem as últimas ~6h com granularidade fina, `diario.db` estende a
 cobertura até 24h, `semanal.db` até 7 dias — sem multiplicar o número de
 arquivos gravados a cada disparo (ainda são no máximo 3 backups por
 disparo, geralmente 1).
- **Rotação decidida pelo `mtime` do arquivo em `backups/`, nunca por
 estado no banco ou em memória do processo.** Um contador em memória (ou
 uma tabela nova) se perderia — ou pior, ficaria dessincronizado do que
 realmente está em disco — se o bot reiniciasse no meio do ciclo. Lendo o
 `mtime` de disco, o esquema se autocorrige sozinho depois de qualquer
 reinício, sem precisar de tabela nova nem de código de recuperação.
 Testado com ciclos simulados (`agenda._rotacionar_backups()` chamado
 repetidamente com mtimes manipulados): os três slots `recente_*` giram
 round-robin (preenche o que falta primeiro, depois sempre sobrescreve o
 mais velho dos três), e `diario`/`semanal` só regravam quando o arquivo
 existente passa de 24h/7 dias.
- **Task de backup registrada em `agenda.instalar()` antes do `return`
 antecipado por falta de `CANAL_TORRE_ID`.** Esse `return` já existia pra
 desligar o aviso da carroça quando o `.env` não tem canal configurado —
 mas o backup não depende de canal nenhum, então ficar depois do `return`
 faria um servidor sem `CANAL_TORRE_ID` rodar sem proteção de banco
 nenhuma, silenciosamente. `instalar()` agora registra os dois loops
 (`backup_automatico` e, condicionalmente, `avisar_carroca`); `iniciar()`
 dá `start()` nos dois.
- **Falha de backup automático loga e segue** (`try/except Exception` em
 volta de `_rotacionar_backups()`), mesmo raciocínio já comentado em
 `avisar_carroca`: se uma falha derrubasse a task inteira, os disparos
 seguintes (inclusive o `diario`/`semanal` do dia certo) também sumiriam.
- **Backup automático ainda roda de forma síncrona dentro do loop
 assíncrono** (sem `asyncio.to_thread`) — de propósito, é o próximo
 cartão. Isso significa que o disparo do backup bloqueia o event loop
 pelo tempo da cópia; não é ideal, mas misturar essa mudança aqui tornaria
 impossível isolar o que quebrou se algo der errado em produção.
- **Caso default de `on_command_error` agora responde ao jogador** (mensagem
 curta, sem stack trace) além de continuar deixando o traceback subir pro
 console — hoje isso passa por `raise erro` (que já era a única linha do
 caso default) e o `on_error` padrão do discord.py que já imprimia o
 traceback antes dessa mudança; só ganhou o `await ctx.send(...)` na
 frente, sem trocar o mecanismo de log. É a diferença entre o jogador ver
 "a Torre engasgou, tenta de novo" e achar que o bot travou — motivo
 direto de entrar nesse ciclo: um `database is locked` sem essa mudança
 ficava completamente invisível pra quem jogou o comando.
- **Testado sem subir o bot inteiro**: cópia isolada do `aincrad.db` real
 (13 jogadores) num diretório à parte — `conectar()` respondendo
 `journal_mode=wal`/`busy_timeout=5000`; `backup_banco()`/
 `backup_banco_para()` produzindo cópias com a mesma contagem de
 `jogadores` que o banco vivo; `agenda._rotacionar_backups()` chamado em
 sequência simulando vários disparos de 2h (com `os.utime` forçando
 arquivos "velhos") pra confirmar o giro round-robin dos 3 recentes e o
 refresh de `diario`/`semanal` só quando vencem. Não existe suíte
 automatizada no projeto (nenhum `pytest`/`unittest` hoje) — a verificação
 real com tráfego de Discord de verdade (raide simultânea, backup
 disparando no meio de um comando) ainda depende do checklist manual.

## Cartão 2 — conexão longa em vez de conexão por chamada

Parte A do cartão "Acesso ao banco bloqueia o event loop" (o ciclo 1, WAL +
backup, foi o commit anterior). Escopo travado de propósito: só a conexão
compartilhada. **Não** entrou `asyncio.to_thread` nem mudança em nenhum
chamador — isso é a parte B, decidida separadamente, porque misturar "o
banco não perde escrita" com "o banco não trava o bot" tornaria impossível
isolar o que quebrou se algo desse errado em produção.

- **Por que conexão longa**: com WAL ligado, o SQLite faz checkpoint
 completo e apaga o `-wal` quando a *última* conexão do banco fecha. Como
 `conectar()` abria e fechava uma conexão nova a cada chamada, toda
 chamada *era* a última conexão — então todo `conectar()` terminava em
 checkpoint completo. Pagávamos o custo de manter o WAL sem receber o
 ganho de concorrência que é o motivo dele existir. Uma conexão de módulo
 (`database._conn`, criada preguiçosamente no primeiro uso, nunca
 fechada em uso normal) resolve isso e também tira o custo de abrir/fechar
 arquivo ~47 vezes por fluxo de comando.
- **`check_same_thread=False`** porque a conexão passa a ser acessada por
 chamadas vindas de contextos diferentes (comandos, a task de backup do
 `agenda.py`) — sem isso o sqlite3 recusa qualquer uso fora da thread que
 criou a conexão.
- **Por que `RLock` e não `Lock`**: verificado antes de trocar — hoje não
 existe `conectar()` aninhado em lugar nenhum do projeto (grep confirmou
 um único `with db.conectar()` fora de `database.py`, em `trocas.py:143`,
 nível único; as quatro chamadas internas de convite de guilda recebem
 `conn` por parâmetro em vez de reabrir). Mesmo assim, `RLock` custa zero
 a mais que `Lock` comum e transforma um `conectar()` aninhado acidental
 futuro (fácil de escrever sem perceber, ex. uma função nova que chama
 outra função de `database.py` já dentro de um `with conectar()`) de
 "deadlock silencioso — o bot trava inteiro, sem erro, sem log" pra
 "funciona, porque é a mesma thread reentrando". Testado: uma reentrância
 forçada (`with conectar(): with conectar():`) devolve a mesma instância
 de conexão e não trava.
- **O `rollback()` explícito no `except` é a mudança que mais importa desta
 entrega.** Com conexão por chamada, um erro no meio de um `with
 conectar()` era descartado de graça: o `finally: conn.close()` fechava a
 conexão suja e a *próxima* chamada abria uma conexão nova, sem histórico
 nenhum da transação que falhou. Com conexão compartilhada isso deixa de
 ser verdade — não existe mais "fechar e abrir de novo" entre chamadas.
 Sem `rollback()` explícito, uma exceção no meio de uma função que escreve
 duas coisas (o padrão de `trocas._commitar_troca`, `resetar_temporada`, e
 qualquer futuro `with conectar()` de múltiplas escritas) deixaria a
 transação parcial pendurada na conexão, e a *próxima* chamada — de outro
 comando, de outro jogador — herdaria e poderia commitar a escrita parcial
 junto da dela. Numa economia com troca direta entre contas (`rpg trade`),
 isso é o pior bug possível: dinheiro ou item pode nascer ou sumir sem
 nenhuma das duas pontas da troca ter completado de verdade. Testado
 direto: uma função que escreve dois `UPDATE` na mesma conexão e depois
 levanta uma exceção não deixou nenhum dos dois valores mudar, e a escrita
 seguinte (chamada normal, sem relação com a que falhou) funcionou sem
 herdar nada — sem esse teste passar, a entrega não estava pronta.
- **`backup_banco_para()` continua abrindo conexões próprias** (origem e
 destino), não a `_conn` compartilhada — de propósito, `Connection.backup()`
 já funciona entre conexões distintas e isso mantém o backup independente
 do lock da conexão principal. Testado com a conexão longa aberta ao mesmo
 tempo: a cópia sai com a mesma contagem de `jogadores` do banco vivo.
- **`fechar_conexao()`** — nova função, chamada só no encerramento
 (`bot.py`, `try/finally` em volta de `bot.run(TOKEN)`), fecha a `_conn` e
 zera a referência. `conectar()` em si nunca fecha nada em nenhum caminho
 — normal, exceção, ou `return` antecipado dentro do `with` (que só
 encerra o generator sem exceção, então ainda passa pelo `commit()`, igual
 já acontecia antes).
- **`init_db()`, `resetar_temporada()` e o `_commitar_troca` de
 `trocas.py`** não precisaram de nenhuma mudança de código — os três já
 faziam todas as escritas dentro de um único `with conectar()`, sem
 aninhar. Passam a rodar na conexão compartilhada e sob o lock automaticamente,
 só por usarem `conectar()` como sempre usaram.
- **Testado sem subir o bot inteiro**, mesma cópia isolada do `aincrad.db`
 real (13 jogadores): mesma instância de conexão devolvida entre chamadas
 sucessivas; PRAGMAs corretos (`wal`/`5000`/`1`) lidos da conexão única;
 o teste do rollback descrito acima; reentrância de `RLock` sem travar;
 `backup_banco_para()` íntegro com a conexão longa aberta; `fechar_conexao()`
 zerando `_conn` e uma chamada seguinte reabrindo sozinha. Não existe
 suíte automatizada no projeto ainda (cartão seguinte) — `rpg trade` de
 ponta a ponta entre duas contas reais e a sequência completa do checklist
 (item 1 da Definition of Done) dependem de rodar no servidor de verdade.

## Cartão 3 — suíte pytest e os cinco primeiros testes

Parte B do cartão "Acesso ao banco bloqueia o event loop" (`asyncio.to_thread`)
mexe no mesmo lugar que a conexão longa (cartão 2) de novo — daí a suíte vir
agora, não antes: WAL e conexão longa foram os dois verificados só à mão. Sem
mudança de comportamento de jogo neste cartão; um bug real apareceu no meio do
trabalho e foi anotado, não consertado (ver abaixo).

- **Isolamento — por que `":memory:"` só passou a funcionar depois da conexão
  longa**: com conexão-por-chamada (antes do cartão 2), cada `conectar()`
  abria um `sqlite3.connect(":memory:")` novo — um banco em memória vazio,
  sozinho, que morria no fim da própria chamada. Nada persistia entre duas
  chamadas dentro do mesmo teste. Agora que `database._conn` é uma conexão de
  módulo reaberta preguiçosamente e nunca fechada em uso normal, o banco em
  memória sobrevive durante o teste inteiro — a mesma razão pela qual o WAL
  passou a valer a pena.
- **Fixture `banco_de_teste` (`tests/conftest.py`), `autouse=True`**: antes de
  cada teste chama `db.fechar_conexao()` (descarta qualquer conexão/estado do
  teste anterior), aponta `db.DB_PATH = ":memory:"`, e roda `db.init_db()` do
  zero. Depois do teste, `fechar_conexao()` de novo — sem isso o próximo
  teste herdaria a conexão (e o banco em memória) do anterior, já que a
  conexão agora é de módulo, não por chamada. `_garantir_nao_e_producao()`
  falha alto se `db.DB_PATH` alguma hora apontar pro `aincrad.db` real
  (comparação por caminho absoluto) — trava de segurança, nunca deveria
  disparar com `":memory:"` fixo, mas cobre um fixture futuro que troque para
  `tmp_path`/arquivo real por engano.
- **Bug real encontrado e anotado aqui, corrigido depois** (não neste
  cartão — o `xfail(strict=True)` original em
  `tests/test_profissoes.py::test_refund_desmanche_nao_deveria_exceder_material_raro_de_chefe`
  foi removido e o teste passa de verdade agora):
  `profissoes.refund_desmanche()` somava `+nivel_upgrade` a **cada** material
  da receita, sem checar se aquele material específico era realmente gasto na
  melhoria (`custo_melhorar` sempre gasta `ANDAR_MATERIAL[item.andar_min]`,
  um material só). Para peças cujo material de craft é diferente do material
  de melhoria — caso das armas do Selo, que craftam com `fragmento_selo`
  (drop de chefe, capado) **e** `pena_do_trovao`, mas melhoram só com
  `pena_do_trovao` — desmanchar uma peça +2 devolvia mais `fragmento_selo` (3)
  do que foi gasto no craft (2). Ver § Correção — desmanche furava o gate de
  escassez, melhorar elemental estourava KeyError, mais abaixo, pro conserto.

## Cartão 4 — `asyncio.to_thread` no caminho quente do combate (parte B)

Parte B do cartão "Acesso ao banco bloqueia o event loop" (parte A — conexão
longa + `RLock` + rollback — subiu no commit `d26767a`). As chamadas ao
banco dentro de corrotinas de comando são síncronas: enquanto uma consulta
roda, o event loop inteiro para — heartbeat do gateway, cliques de botão e
comandos de outros jogadores incluídos.

- **Wrappers `a_*` em vez de converter as 47 funções de `database.py`.**
  Cada wrapper é só `async def a_x(*a, **k): return await
  asyncio.to_thread(x, *a, **k)`, adicionado ao lado da função síncrona, que
  continua existindo sem mudar uma linha. Três motivos, nessa ordem de peso:
  os 20 testes da suíte chamam as funções síncronas direto — convertê-las
  quebraria a suíte inteira só pra migrar oito call sites; a migração fica
  incremental, dá pra parar no meio (ou reverter um bloco) sem deixar nada
  quebrado; `agenda.py` e o backup automático não são corrotina de comando e
  continuam chamando a versão síncrona sem cerimônia nenhuma. Criei wrapper
  só pras 9 funções que o combate usa (`get_jogador`, `atualizar_jogador`,
  `marcar_combate`, `vezes_derrotado_chefe`, `registrar_vitoria_chefe`,
  `add_item`, `remove_item`, `checar_cooldown`, `set_cooldown`), não pras 47.
- **O ganho é o event loop livre, não paralelismo de consulta — e isso
  precisa ficar registrado porque é contraintuitivo.** Com a conexão única
  e o `RLock` do cartão 2, as operações de banco continuam serializadas
  entre si: `to_thread` não faz duas consultas rodarem ao mesmo tempo.
  O que muda é que a *espera* por esse lock acontece numa thread do
  executor, não no event loop — então o heartbeat do gateway, outro clique
  de botão, outro comando, continuam sendo processados enquanto uma
  consulta está parada esperando a vez dela. Não dá pra medir isso como
  "consulta mais rápida" (não fica); o sintoma que desaparece é o bot
  engasgar/o discord.py logar `heartbeat blocked` durante luta com party.
- **Combate primeiro, e nada mais nesta etapa.** É onde mais dói: cada
  rodada de `rpg boss`/`rpg party` lê e escreve enquanto os outros
  participantes (e o resto do servidor) esperam. Migrei só as chamadas que
  já estão dentro de `async def` em `combate.py` — `recompensar`,
  `encerrar_por_abandono`, `BotaoPocao.callback`, `SalaDeEspera.validar`/
  `entrar`, `montar_combatentes`, `iniciar_luta`, os comandos `boss`/`party`.
- **Três helpers síncronos ficaram de fora de propósito**: `salvar_estado`
  (chama `atualizar_jogador`), `embed` ×2 (chama `get_jogador`) e
  `pocoes_na_mochila` (chama `get_inventario`). Converter qualquer um deles
  obriga a converter todos os chamadores — `embed` é chamado a cada render
  de painel de luta, então é provavelmente o que mais paga, mas é também o
  que mais mexe em código. Fica anotado pro próximo cartão, não misturado
  com este.
- **`trocas.py` não foi tocado.** `_commitar_troca` faz toda a revalidação e
  escrita dentro de um único `with db.conectar()` — se fosse migrado, teria
  que ir inteiro pra dentro de um `to_thread` só (uma thread segurando o
  lock do início ao fim), nunca pedaço por pedaço. Migrar as consultas de
  dentro dele separadamente destruiria a atomicidade que o teste de
  condição de corrida cobre. Não entrou nesta etapa — nem risco de tentar.
- **Risco anotado, não observado**: com a migração parcial, uma chamada que
  continua síncrona (os três helpers acima, ou qualquer código fora do
  combate) pode ficar esperando o `RLock` que uma thread do `to_thread`
  está seguranco — e essa espera *bloqueia* o event loop, o oposto do que a
  mudança busca. Com operações sub-milissegundo o risco é baixo, mas é por
  isso que a migração foi por bloco coerente (combate inteiro de uma vez),
  não função solta aqui e ali — mistura de síncrono e assíncrono no mesmo
  fluxo é onde esse risco realmente aparece.
- **Nenhum teste mudou.** Os 20 testes continuam chamando as funções
  síncronas de sempre — é o próprio sinal de que a migração ficou restrita
  aos wrappers e não vazou pra dentro de `database.py`.

### Sobra do Cartão 4 — `processar_morte`

O cartão fechou sem migrar `processar_morte(j, s)` (`bot.py`), que é síncrona
e chama `db.atualizar_jogador` síncrono, chamada de dentro de corrotina em
cinco lugares: `cacar`, `explorar`, `boss` (bot.py) e `encerrar_sem_donos`/
`finalizar_derrota` (combate.py). Morte em caçada é o caminho mais frequente
dos cinco — caçada é o comando mais usado do jogo.

- **`a_processar_morte` mora em `bot.py`, não em `database.py`.** É o único
  wrapper `a_*` fora de `database.py`, porque `processar_morte` em si não é
  uma função de banco — é lógica de penalidade que só termina com um
  `db.atualizar_jogador`. Mesmo padrão (`async def a_x(*a, **k): return
  await asyncio.to_thread(x, *a, **k)`), lugar diferente.
- **A armadilha do `H["processar_morte"]` era real.** `combate.py` acessa a
  função pelo dicionário de injeção `H`, montado em `combate.instalar(bot,
  globals())` — `H.update(contexto)` copia o namespace de `bot.py` no
  momento da chamada. Registrar só `a_processar_morte` em `bot.py` bastou:
  como `H` guarda os dois nomes, `combate.py` passou a chamar `await
  H["a_processar_morte"](...)` em vez de `H["processar_morte"](...)` sem
  esperar. Errar essa troca quebra em runtime (primeira morte em `rpg boss`
  ou `rpg party`), não na subida do bot — é o custo conhecido desse padrão.
- **Teste novo em `tests/test_morte.py`, e ele precisou importar `bot.py`
  pela primeira vez na suíte.** Nenhum teste tinha feito isso até agora
  porque `bot.py` chama `bot.run(TOKEN)` no nível do módulo, sem guarda de
  `__main__` — um import direto tentaria abrir uma conexão de verdade com o
  Discord. A saída foi trocar `commands.Bot.run` por um no-op (via
  `unittest.mock.patch.object`) só durante o import, e cachear o módulo
  importado em `sys.modules["bot"]` pra qualquer teste futuro reusar sem
  reimportar. Registro de comando (`combate.instalar()` e companhia) roda
  normalmente nesse import — só não toca rede porque `on_ready` (onde
  `agenda.iniciar()` liga os loops de fundo) nunca dispara. Se algum
  `instalar()` novo passar a tocar banco ou rede no nível do módulo em vez
  de só registrar, esse import quebra silenciosamente virando falso
  positivo — vale checar isso antes de outra função de `bot.py` precisar
  do mesmo tratamento.
- **Trava os quatro invariantes de morte**: 20% das moedas, HP a 30% do
  máximo, contador de mortes, e o `andar`/`andar_max` caindo pro 10 quando a
  morte foi acima do Selo sem zerar `chefes_derrotados` (tabela separada,
  por andar — testado via `db.registrar_vitoria_chefe`/
  `vezes_derrotado_chefe`, não uma coluna de `jogadores`). 25 testes agora.

## Baratear a entrada da Forja

**Superado pelo cartão seguinte, § Rebalancear a escada da Forja + devolutiva
aos jogadores** — o ajuste abaixo só mexeu em «Couro Batido» e deixou as
outras três receitas de subida como armadilha de XP/moeda; o cartão seguinte
equalizou as quatro e pagou a diferença pra quem já tinha subido. Fica aqui
como histórico do primeiro passo.

A escada de craft+desmanche (só quem é Forjador desmancha com XP de volta,
40% do XP + metade do material) até o nível 9 custava 47.600 moedas / 68
crafts na Forja contra 21.200 / 58 na Alquimia — 2,2x mais caro pra chegar
no mesmo lugar, mesmo com material parecido nas duas. A causa era a receita
de entrada: «Couro Batido» cobrava 700 moedas por 20 XP, «Elixir de Ervas»
cobra 200 por 20 XP — mesma XP, preço bem diferente, e é a receita de
entrada que domina o custo total porque é a mais martelada.

- **«Couro Batido»: 700 → 450 moedas, 20 → 25 XP.** As 3 Presas de Javali
  não mudam — o gargalo era moeda, não material. Resultado: 24.750 moedas /
  55 crafts até o nível 9, ao lado da Alquimia. Nível 7 (peças do Selo) e
  nível 9 (armas elementais) ficam intocados — o gargalo deles é Fragmento
  do Selo e material de chefe, moeda não compra isso.
- **O piso é 350, não pode ir mais baixo sem mexer no preço do item
  junto.** «Couro Batido» vale 700 no `ITENS` e equipamento revende por
  metade (`bot.py:vender`, `preco * 0.5`). Se o craft caísse abaixo de 350,
  fabricar e vender viraria lucro puro — impressora de moeda, o jogador
  fabrica e desfaz em loop sem nunca equipar nada. 450 deixa 100 de margem
  acima desse piso. Qualquer ajuste futuro nessa receita (ou em qualquer
  outra de armadura/arma) precisa checar essa mesma margem antes de descer
  o preço — ver `balanceamento.md` § Profissões e craft.
- **A frase do Guia da Torre estava errada, corrigida no mesmo cartão.**
  "Receita mais cara dá mais XP — não adianta martelar a mais barata" nunca
  foi verdade: «Couro Batido» rendia 0,029 XP por moeda contra 0,012 de
  «Couraça de Cinzas» mesmo antes deste ajuste. O caminho ótimo sempre foi
  martelar a receita de entrada do zero ao nível 9; a mudança aqui barateia
  esse caminho ótimo pra Forja, não cria um novo.

## Rebalancear a escada da Forja + devolutiva aos jogadores

O ajuste anterior (§ Baratear a entrada da Forja) só resolveu o preço de
«Couro Batido» — deixou o defeito estrutural intacto: `xp_para_subir` é
linear (`50 * nível`) mas o XP de cada receita não acompanhava o preço
dela. «Couro Batido» rendia 0,029 XP/moeda, «Couraça de Cinzas» rendia
0,012 — a receita cara era **matematicamente pior** pra subir de nível, não
só mais cara. O caminho ótimo sempre foi martelar o mesmo sapato de couro
68 vezes; nenhuma peça mais forte compensava fabricá-la em vez disso.
Confirmação no banco em 10/08: ninguém passou do nível 6 de Forja, e 2 dos
5 forjadores nunca fabricaram nada (nível 1, 0 XP).

- **Princípio: as quatro receitas de subida rendem o mesmo XP por moeda
  (~0,055).** `couro_batido` 700→400 moedas / 20→22 XP, `malha_reforcada`
  2400→1400 / 45→75, `placas_polidas` 5200→3000 / 80→165, `couraca_cinzas`
  11000→6200 / 130→340. Materiais de cada receita intocados — o ajuste é só
  em moedas e XP. Nível 7/8 (peças do Selo), nível 9 (armas elementais) e
  as três receitas de Alquimia ficam de fora: o gargalo do Selo é
  Fragmento do Selo e material de chefe, moeda não compra isso, e Alquimia
  não fazia parte do escopo do cartão (continua com XP/moeda levemente
  desigual entre as três receitas dela). Escada 1→9 cai de 47.600 para
  ~25.200 moedas — quem quer subir rápido faz muita peça barata, quem quer
  a armadura boa faz poucas peças caras e paga o mesmo total; o
  diferencial vira o item, não a eficiência.
- **Piso: craft nunca abaixo de 50% do `preco` do item no `ITENS`.**
  Equipamento revende por `preco * 0.5` (`bot.py:vender`) — craft abaixo
  disso vira impressora de moeda (fabrica e desfaz em loop, lucro puro,
  nunca equipa nada). As quatro receitas ficam com folga: 400/700 (piso
  350), 1400/2400 (piso 1200), 3000/5200 (piso 2600), 6200/11000 (piso
  5500). Checar essa mesma margem em qualquer receita nova — ver
  `balanceamento.md` § Profissões e craft.
- **Devolutiva: `devolutiva_forja.py`, script one-off separado do bot.**
  Só quem tem `profissao = 'forja'` recebe — Alquimia não mudou. Fórmula:
  `(25 * prof_nivel * (prof_nivel - 1) + prof_xp) * 12` por jogador — o
  termo `25*N*(N-1)` é o XP das levas já completadas até o nível atual
  (soma de `50*k` pra k=1..N-1, que é exatamente `xp_para_subir`), somado
  ao `prof_xp` em progresso no nível corrente; `12` é a diferença de custo
  por ponto de XP entre o modelo velho (25 moedas/XP) e o novo (13). É
  **XP acumulado desde o nível 1**, não só o progresso do nível atual — quem
  já subiu mais níveis recebe proporcionalmente mais, por ter pago o preço
  velho mais vezes. Roda direto com `sqlite3` (mesmo padrão de
  `reset_boss.py`), sem passar pelo `database.py` do bot — não precisa
  estar rodando. **Sem flag só mostra o preview**; só credita moedas de
  verdade com `--aplicar`. Rodar `--aplicar` duas vezes paga duas vezes —
  não existe tabela de controle de migração neste projeto, a proteção é
  puramente operacional (rodar uma vez, depois de backup do `aincrad.db`).
  Valores conferidos no banco em 10/08 batem exatamente com a fórmula:
  Cauê nv6/818 XP acumulado → 9.816, mands nv3/286 → 3.432, Positions
  nv3/249 → 2.988, Russo e Léozin nv1/0 → 0. TOTAL 16.236.
  **Execução: 10/08/2026, `devolutiva_forja.py --aplicar`, backup prévio em
  `backups/pre_devolutiva_forja_20260810.db`. Cauê +9.816 (10.047→19.863),
  mands +3.432 (2.214→5.646), Positions +2.988 (35.717→38.705), Russo e
  Léozin +0 (nível 1, sem XP). TOTAL pago: 16.236 moedas.**
- **Guia da Torre corrigido no mesmo cartão.** A frase "receita mais cara
  dá mais XP — não adianta martelar a mais barata" virou "as quatro
  receitas de subida da Forja rendem o mesmo XP por moeda — a escolha é
  sobre qual armadura você quer, não sobre qual dá nível mais rápido" (e a
  tabela de custo das quatro receitas foi atualizada). Página "Tabela de
  Itens" também atualizada (mesma tabela + callout do piso de revenda).

## Sistema de diálogo com NPC — alicerce do 0.3

Primeiro corte, só os 9 NPCs de `tipo: "conversa"` (Pip, Lenhador, Homem de
Sal, Pescadora, Capataz, Cavaleiro, Corista, Cartógrafo, A Porta). Mercador,
ferreiro, carroceiro, taverneiro e a Guia continuam exatamente como estavam
— cada um migra na carta própria dele, depois. É o alicerce dos próximos
cortes (comprar dentro do diálogo, sidequests, novo início do jogo), então
o contrato de dado importa mais que o conteúdo.

- **Público com `ctx.send`, mas só o dono clica — mesmo padrão do
  `PainelLuta`.** Rafael quer que o canal veja que existe conteúdo ali
  (`DialogoView.interaction_check` compara `interaction.user.id` com
  `ctx.author.id`; quem não é dono recebe recusa ephemeral). A alternativa
  óbvia — mandar a conversa ephemeral pro autor — esconderia o próprio
  ponto do sistema: um NPC de conversa hoje "não faz nada" pra quem só olha
  o canal passar; ver os botões aparecendo é o que sinaliza que tem
  conteúdo pra descobrir ali, mesmo que só uma pessoa esteja jogando aquela
  conversa agora.
- **A tabela `sidequests` e `opcoes_por_estado` nasceram um cartão inteiro
  antes da primeira quest existir.** Motivo: `dialogos.py` é DADO — se o
  formato do dado mudasse depois que os 9 diálogos já estivessem escritos
  (pra caber `opcoes_por_estado`, `quest_id`, o mapeamento
  ativa/concluida→durante/depois), os 9 seriam reescritos, não só
  estendidos. Nascendo agora, uma sidequest nova só soma um bloco no dict
  do NPC dela — nunca toca no motor. `database.estado_sidequest(user_id,
  quest_id)` devolve `'antes'` sem linha na tabela (todo mundo, hoje) e
  traduz `'ativa'/'concluida'` (colunas da tabela) pra `'durante'/'depois'`
  (vocabulário do diálogo) — dois vocabulários de propósito: a tabela
  descreve o estado da quest em si, o diálogo descreve o que o NPC fala
  sobre ela, e nem todo estado de quest precisa virar uma fala diferente.
  `npcs.opcoes_do_dialogo()` só chama `estado_sidequest` se o NPC declarar
  `opcoes_por_estado` — nenhum declara ainda, então a função nunca toca no
  banco neste corte (coberto em `tests/test_dialogo.py` com um NPC
  fixture, já que nenhum real usa o campo pra testar contra).
- **`dialogos.py` é só dado; a UI mora em `bot.py`, não em `npcs.py`.**
  `npcs.py` não tinha dependência de `discord` antes disso — só ganhou
  `opcoes_do_dialogo()` (lógica pura: mistura `opcoes` com o bloco do
  estado atual). `DialogoView`/`BotaoOpcaoDialogo` ficam em `bot.py`, perto
  do comando `falar` que os usa, no mesmo espírito de `trocas.py`/
  `guildas.py` terem a própria UI perto do próprio comando — só que `falar`
  já vive em `bot.py`, então a View fica ali também, sem criar módulo novo
  só pra isso.
- **Diálogo nunca é consumido — nada de "já ouviu isso".** `rpg falar`
  duas vezes mostra as mesmas opções as duas vezes. O timeout (120s)
  desabilita os botões em vez de apagar a mensagem — a conversa registrada
  no canal continua legível, só para de aceitar clique.
- **As respostas de cada opção foram escritas por mim (Claude), não pelo
  Rafael.** O card dizia que o texto "vinha junto do briefing", mas a
  página "Lore Vitre RPG" só tinha o tópico de cada opção (ex.: Pip —
  "perguntar em qual número ele parou"), não a fala em si; os quatro NPCs
  sem nenhuma lista de tópicos (Capataz, Cavaleiro, Cartógrafo, A Porta)
  não tinham nem isso. Perguntei e o Rafael autorizou escrever no tom já
  estabelecido pela `abertura` de cada um. Vale revisão de conteúdo depois
  — é texto novo, não uma transcrição.
- **Teste sem Discord de verdade**: `tests/test_dialogo.py` cobre
  `estado_sidequest` (sem linha/ativa/concluida, por jogador e por quest) e
  `opcoes_do_dialogo` (NPC sem quest nunca toca o banco; NPC fixture com
  `opcoes_por_estado` soma o bloco certo por estado), mais consistência de
  dado (os 9 conversa têm `dialogo` válido, todo `DIALOGOS[...]` tem
  abertura e opções com label+resposta, nenhum NPC fora do escopo ganhou o
  campo `dialogo`). `DialogoView`/`BotaoOpcaoDialogo` foram verificados à
  mão fora da suíte (interaction_check aceita dono e nega o resto com
  ephemeral, clique edita a descrição mantendo os botões, timeout desabilita
  sem apagar a mensagem) — discord.py não conecta de verdade sem subir o
  bot, então isso não virou teste automatizado; falta rodar no Discord real
  pra ver os 8 passos do checklist do card de ponta a ponta.

## Pronomes do jogador + botão Sair do diálogo

### Pronomes

- **Default `'elu'`, não `'ele'` nem uma escolha forçada.** A coluna nasce
  `NOT NULL DEFAULT 'elu'` pelos 13 jogadores que já existiam antes dela —
  eles não escolheram nada, e `'ele'` como default atribuiria gênero
  masculino por omissão pra gente que nunca decidiu isso. `'elu'` é o único
  dos três que não é a escolha de ninguém em particular; lê com terminação
  em "o" (mesma concordância de `'ele'`) até que a pessoa troque com `rpg
  pronome`.
- **Concordância resolve em DOIS, não em três.** `'ele'` e `'elu'` usam a
  mesma terminação ("cansado", "pronto") — só `'ela'` diverge ("cansada",
  "pronta"). Não existe uma terceira forma gramatical neutra em português
  que não seja já uma dessas duas (ou uma reescrita de frase inteira, fora
  de escopo aqui); marcar um terceiro slot no `{opcao|opcao}` seria dado
  morto em todo marcador do jogo. Onde os três pronomes SÃO todos
  diferentes é no de terceira pessoa — `sujeito()`/`possessivo()` sujeito
  ele/ela/elu e dele/dela/delu, os três valores literais da coluna.
- **`pronomes.py` é função pura, sem banco nem discord** — cabe teste
  completo (`tests/test_pronomes.py`, 13 casos: marcador simples nos dois
  sentidos, marcador no fim da palavra, vários marcadores na mesma string,
  marcador vazio antes da barra, texto sem marcador, três variações de
  marcador malformado, pronome/texto `None`, os dois resolvedores de
  terceira pessoa com fallback pro default).
- **O exemplo do card tinha um erro de digitação, corrigido no código.** O
  card escreveu `"Você foi o{|a} únic{o|a} a sair de pé."` — com "o"
  literal colado antes do marcador vazio. Resolvendo isso literalmente (uma
  troca simples de `{opcao1|opcao2}` por uma das duas opções, sem lógica
  extra) dá `"...oa única..."` pra `'ela'` — errado. A regra em prosa do
  card ("primeira opção pra ele/elu, segunda pra ela", sem menção a apagar
  caractere nenhum) é a que faz sentido, e é a que o resolvedor implementa;
  o exemplo certo é `"Você foi {o|a} únic{o|a} a sair de pé."`, sem o "o"
  solto — é o que está em `tests/test_pronomes.py` e é o padrão a seguir em
  texto novo (nunca escrever letra literal colada bem antes de um marcador
  com primeira opção vazia).
- **Marcador nunca entra dentro de f-string.** `{opcao|opcao}` colide com a
  sintaxe de interpolação do Python (`f"cansad{o|a}"` tentaria avaliar `o|a`
  como expressão e quebraria). Todo texto marcado neste cartão foi escrito
  como string comum, resolvido via `pronomes.concordar(texto, j["pronome"])`
  ANTES de entrar em qualquer f-string com valor dinâmico (HP, nome de NPC
  etc.) — ver `bot.py` (`rpg boss`/`rpg party`, `rpg descansar`),
  `combate.py` (`checar_sala_do_chefe`, `Combatente.barra()`).
- **Varredura cobriu `bot.py`, `combate.py`, `dialogos.py` — não achei nada
  pra marcar em `npcs.py`, `andares_altos.py` nem `raide.py`** (texto de
  NPC sobre si mesmo, não sobre o jogador, ou sem adjetivo que varie por
  gênero). Achei também um caso fora da lista de arquivos do card:
  `guildas.py`, "`{alvo.display_name} foi expulso da guilda`" — terceira
  pessoa sobre OUTRO jogador (quem foi expulso), resolvido com o pronome
  dELE, não do líder que expulsou. Entrou porque bate exatamente com "log
  de guilda" citado no card como um dos lugares onde pronome de terceira
  pessoa aparece — provavelmente um esquecimento na lista de arquivos, não
  uma exclusão de propósito.
- **`rpg pronome` era PROVISÓRIO e saiu.** Removido junto com `PronomeView`
  quando o novo início (patch 0.3) nasceu e a escolha migrou pra lá — ver
  § Despertar (patch 0.3).

### Botão Sair do diálogo

- **Sair deixou de ser uma opção de `dialogos.py` e virou botão fixo da
  `DialogoView`**, acrescentado por conta própria depois das opções do NPC
  (`bot.py`, não mais dado). Motivo: antes, clicar em Sair só rodava a
  mesma lógica de qualquer opção — trocava a descrição pela resposta e
  deixava os botões ativos, como se a conversa continuasse. Agora
  `BotaoSairDialogo` troca a descrição pela linha de despedida E desabilita
  todos os botões (`self.view.stop()` + `item.disabled = True` em cada um)
  — mesmo efeito visual do timeout, só que com texto em vez de silêncio.
- **`saida` é campo novo em cada NPC de `dialogos.py`**, com
  `SAIDA_PADRAO` como fallback pra quem não tiver (nenhum NPC de hoje cai
  nesse caso — os 9 ganharam a própria linha, migrada do que já era a
  opção "Sair"/"Ir embora" de cada um). O fallback existe pro próximo NPC
  que nascer sem `saida` escrita ainda, não travar o diálogo dele.
- **Resto da `DialogoView` intocado**, como pedido: `interaction_check`,
  timeout de 120s, opções normais continuando a conversa — só o
  comportamento do Sair mudou.

## Guarda de main + setup no nível do módulo

Fecha a fase de fundação do patch 0.3. `bot.py` tinha `bot.run(TOKEN)` solto
no fim do arquivo — importar o módulo conectava no Discord de verdade. Já
rodou por engano com o token real, e já custou cobertura duas vezes:
`DialogoView` e `PainelLuta` só puderam ser verificadas à mão porque a
suíte não conseguia importar `bot.py` sem contornar isso.

- **`bot.run(TOKEN)` (com o try/finally do `db.fechar_conexao()`) foi pra
  dentro de `if __name__ == "__main__":`.** É a mudança mínima que resolve
  o problema descrito: só `python bot.py` de verdade conecta.
- **As chamadas `combate.instalar(bot, globals())`, `habilidades.instalar()`,
  `trocas.instalar()`, `guildas.instalar()`, `raide.instalar()`,
  `agenda.instalar(bot)` e `admin.instalar(bot)` CONTINUAM no nível do
  módulo — não viraram uma função de setup separada.** Duas razões pra
  escolher a opção menos invasiva:
  1. **Nenhuma delas toca banco ou rede.** `instalar()` só registra
     comandos no `bot` e popula o dict `H` de cada módulo (`H.update(contexto)`)
     — é registro de função, não I/O. `agenda.instalar(bot)` também só
     registra os loops, não os inicia (`iniciar()` é quem faz isso, chamado
     só em `on_ready`). Confirmado na prática: as 58 chamadas de `import bot`
     que a suíte já fazia (test_morte.py, test_dialogo.py indiretamente via
     bot.py, e agora test_andar15.py) sempre rodaram essas oito chamadas
     de `instalar()` sem nunca precisar de rede — o único problema real
     sempre foi o `bot.run()` no fim.
  2. **Extrair um `setup_modulos()` só adicionaria indireção sem resolver
     nada a mais.** O sintoma do card ("importar CONECTA no Discord") tem
     uma causa única e pontual — um guard resolve ela inteira. Uma função
     de setup faria sentido se algum `instalar()` precisasse rodar
     condicionalmente (só em testes, ou só em produção), o que não é o
     caso hoje: todo `instalar()` precisa rodar sempre que o módulo `bot`
     existir, testes inclusos, porque `combate.H`/`habilidades.H`/etc.
     precisam estar populados pra qualquer teste que chame uma função
     desses módulos (ex.: `tests/test_andar15.py::test_finalizar_vitoria_*`
     usa `combate.finalizar_vitoria()`, que lê `H['barra_hp']`).
  Se algum `instalar()` futuro passar a tocar banco ou rede no nível do
  módulo, essa decisão precisa ser revisitada — ver o mesmo aviso já
  registrado em § Sobra do Cartão 4 sobre esse risco.
- **`tests/test_bot_seguro.py`** prova a guarda de duas formas: troca
  `commands.Bot.run` por algo que estoura `AssertionError` se for chamado
  (determinístico, não depende de rede/DNS/timeout) e, separado, um import
  sem patch nenhum — o item 2 do checklist do card ("importar bot num
  shell") literalmente. `tests/test_morte.py` perdeu o workaround de
  `patch.object(commands.Bot, "run", ...)` que precisava antes — virou
  `import bot` direto.
- **Limpeza de brinde**: o `@bot.command(name="boss", ...)` morto (nunca
  rodava — `combate.instalar()` chama `bot.remove_command("boss")` antes
  de registrar o de verdade) saiu junto, porque o rename do chefe do 15
  passava perto do texto errado "Décimo Selo" que esse comando morto
  carregava. `simular_combate()` continua vivo — é usado por `cacar` e
  `explorar`, não só pelo comando morto.

## Rename do chefe do andar 15

- **Nome do ANDAR continua "Trono Vazio" — só o chefe mudou.** Fase 1
  «Espectro do rei» (sombrio), fase 2 «A Ruína do Rei» (divino, nome
  definido pelo Rafael em 10/08). HP/ATK/DEF/XP/moedas/drops das duas
  fases intocados — só `"nome"` mudou em cada dict, e a fase 2 ganhou
  `"fala_derrota"`.
- **`fala_derrota` é campo genérico em `combate.py`, não um `if` pro andar
  15.** `finalizar_vitoria()` checa `luta.chefe.get("fala_derrota")` e
  soma um field "🗡️ Últimas palavras" se existir — qualquer chefe futuro
  ganha a mesma revelação só escrevendo o campo, sem tocar código. Hoje só
  o andar 15 tem: *"De novo não, como você está aqui, se já subiu essa
  torre"* — a linha que entrega que alguém (o Herói que selou a torre, ver
  Lore) já subiu antes.
- **Duas armas do andar 15, duas decisões diferentes, ambas do Rafael:**
  `cajado_divino` («Cajado do Desperto» → **«Cajado da Ruína»**, "Desperto"
  deixou de existir como nome de ninguém) e `adaga_sombria` (**mantida**
  «Adaga do Trono Vazio» — ela é nomeada pela sala, não pelo chefe, e o
  andar continua se chamando Trono Vazio, então o nome dela continua
  literalmente correto). As outras seis armas do andar (nomeadas por
  material ou condição — Sombra Dobrada, Ferida Sombria, Silêncio
  Ajoelhado, Prego de Luz, Juízo Suspenso, Marca) não têm nada a ver com o
  nome do chefe e ficaram como estavam.
- **Guia da Torre**: nada a mudar — a seção "Acima do Selo" esconde nome e
  stats de chefe de 11-15 de propósito ("você descobre subindo"), e a
  seção de armas elementais nunca listou as 24 individualmente. Lore
  Vitre RPG (Notion) atualizada: tabela do elenco de chefes (fase 2 com
  nome próprio), callout de "cargo, não pessoa" (pendência fechada), e a
  frase sobre «Sua Majestade do Andar Nenhum» que fazia trocadilho com o
  nome antigo do chefe ("o Trono Vazio, ocupado por si mesmo") reescrita
  pra apontar pro nome novo sem o trocadilho quebrado.

## Comércio dentro do diálogo

Primeira carta grande do 0.3 — mexe no que todo mundo usa todo dia. `rpg loja`
morreu, `rpg comprar`/`rpg vender` sobreviveram, e mercador/ferreiro ganharam
painel próprio dentro de `rpg falar` (`comercio.py`, novo módulo).

- **Por que `rpg loja` morria e `rpg comprar`/`rpg vender` não.** `rpg loja`
  era a contradição: juntava mercador e ferreiro numa lista paginada só, como
  se fossem um mercado único, quando a ficção sempre foi "cada NPC vende o
  seu". Os comandos de atalho não têm esse problema — eles não fingem que
  existe um mercado central, só executam uma compra que você já decidiu.
  Cortar os dois juntos economizaria uma migração, mas ia contra o motivo
  explícito do card: quem compra poção 15x por sessão não pode virar refém
  de dois cliques (abrir o menu, escolher o item) toda vez.
- **`rpg loja` não desapareceu silenciosamente — vira redirecionamento.**
  `rpg loja`/`shop`/`store` continuam registrados, só que agora respondem
  apontando pro `rpg falar <nome>` (menu) e pro `rpg comprar` (atalho). Um
  comando que simplesmente some vira "bot quebrado" pra quem já tinha o
  hábito digitado; um que explica pra onde foi é uma migração.
- **Onde vender equipamento: só no ferreiro (decisão do Rafael).** `rpg
  vender` (o comando) continua ambiente — vende qualquer coisa vendável,
  igual antes. Mas no MENU, arma/armadura só aparece no painel do ferreiro;
  o mercador só compra/vende consumível. Motivo: "o ferreiro cuida do que é
  seu" — comprar, vender e a oficina inteira (forjar/melhorar/desmanchar)
  no mesmo balcão, em vez de espalhar equipamento em dois NPCs diferentes.
- **Select em vez de paginação por botão (decisão minha, pro card).** Dentro
  da conversa a lista de itens é um `discord.ui.Select` (até 25 opções),
  não a paginação de `paginacao.py` que `rpg receitas`/`rpg inventario`/a
  antiga `rpg loja` usam. Paginação faz sentido quando o objetivo é LER uma
  lista grande inteira; aqui o objetivo é ESCOLHER um item pra agir — um
  menu suspenso resolve isso em um clique a mais (abrir o dropdown) contra
  os N cliques de "próxima página" até achar o item. O teto de 25 nunca é
  um problema real: poção por andar são no máximo ~3 opções, equipamento
  por ferreiro são ~3, e receita "pronta pra fazer agora" (não o catálogo
  inteiro) raramente passa de um punhado — ver a seguir.
- **Nenhuma lógica de negócio foi duplicada — os botões chamam os comandos
  de texto de verdade.** `comercio.ShimCtx` é um bridge mínimo (`.author` +
  `.send()`) que deixa `comprar`/`vender`/`craftar`/`melhorar`/`desmanchar`
  rodarem sem mudar uma linha deles: o botão monta `"{chave} 1"` (ou só o
  slot, pro melhorar) e chama `comando.callback(shim_ctx, argumento=...)`
  direto — o mesmo parsing (`encontrar_item`, `separar_quantidade`), a
  mesma validação de moedas/andar_min/nível/desconto de Forjador, a mesma
  resposta. `encontrar_item` já casa a CHAVE do item normalizada antes de
  tentar por nome, então passar a chave exata (o que o `value` de um
  `SelectOption` sempre é) resolve sem ambiguidade. `craftar`/`melhorar`/
  `desmanchar` não são atributos de módulo em `profissoes.py` (vivem dentro
  do closure de `instalar()`), por isso passam por
  `H["_bot"].get_command(nome).callback` em vez de import direto — `comprar`/
  `vender` já chegam prontos em `H` porque `bot.py` os define no nível do
  módulo, então `comercio.instalar(bot, globals())` os pega direto do
  `contexto`.
- **Depois de cada ação, o painel principal volta sozinho** (com moedas
  atualizadas) — `PainelComercioBase._executar` reabre `self.embed(j)` na
  MESMA mensagem depois que o `ShimCtx` manda a resposta do comando como
  mensagem nova. Comprar 15 poções pelo menu custa 2 cliques cada
  (Comprar → escolher) porque o painel nunca fecha.
- **Menu compra/vende 1 unidade por clique, de propósito.** O card já
  reserva `rpg comprar <item> <qtd>` pra quem quer comprar em lote; o menu
  é "a porta da frente pra quem está descobrindo" — pedir quantidade dentro
  do select (um segundo prompt, ou um modal) complicaria a UI sem servir
  esse público. Quem quer 10 poções de uma vez já sabe digitar o comando.
- **A fileira de oficina fica sempre habilitada — nunca `disabled=True`.**
  Um botão desabilitado no Discord não gera interação: o clique não chega
  no bot, e não tem como responder nada. O ponto do design é justamente
  ensinar que a profissão existe pra quem não tem — um botão cinza e mudo
  não ensina nada, só esconde a funcionalidade de quem mais precisaria
  descobrir ela.
- **Só "Forjar" recusa por ofício errado — "Melhorar" e "Desmanchar" não.**
  Conferido no código antes de inventar uma regra nova: `craftar` exige
  literalmente ter escolhido Forja como profissão (senão a receita nem
  aparece nas suas); mas `melhorar` e `desmanchar` sempre funcionaram pra
  QUALQUER jogador — só o desconto de 25% (melhorar) e o XP de ofício
  (melhorar e desmanchar) dependem de ser Forjador. Copiar a recusa
  ephemeral pra essas duas teria sido reimplementar uma trava que não
  existe no comando de texto — o card proíbe isso explicitamente ("não
  reimplementar a lógica"). O checklist do próprio card também só testa
  Forjar pra esse caso (itens 6-7), o que confirma a leitura.
- **Select do "Forjar" mostra só receita PRONTA agora (`pode_fazer`), não
  o catálogo inteiro.** Um Forjador nível 10 tem acesso a ~33 receitas
  (9 do Selo pra baixo + 24 armas elementais) — passa do teto de 25 do
  Discord se listar tudo. Mostrar só o que dá pra fazer AGORA (nível
  liberado + material + moedas em mãos) resolve o teto pro caso realista
  E é mais útil: as outras já apareceriam com erro de material se
  escolhidas. Sem nada pronto, a mensagem aponta pra `rpg receitas` (o
  catálogo completo, com paginação, pra quem quer planejar o que falta).
- **Teste sem Discord de verdade**: `tests/test_comercio.py` (20 casos)
  cobre as funções puras de montagem de select (corte de 25, filtro por
  tipo/vendável, desmanchar ignorando `vendavel`), o `ShimCtx` (response
  na primeira chamada, followup depois), e os fluxos ponta-a-ponta via
  interação fake — mesma estratégia de `tests/test_dialogo.py`: compra e
  venda debitam/creditam moedas de verdade no banco em memória, forjar sem
  ofício recusa sem abrir o select, forjar com ofício+material crafta de
  verdade, melhorar só lista slot equipado, desmanchar reduz a mochila,
  outro jogador é negado, Sair desabilita tudo. `view.is_finished()` não
  dá pra checar fora de uma conexão real (o Future interno de `stop()` só
  é criado quando a View passa pelo dispatch de verdade) — o teste checa
  `disabled=True` nos filhos, que é o efeito que interessa.

## Quantidade no menu de compra do NPC

O select de Comprar (mercador e ferreiro) comprava sempre 1 unidade —
quem queria 5 poções clicava Comprar→escolher 5 vezes, reabrindo o menu a
cada uma. `rpg comprar <item> <qtd>` já resolvia isso; só o menu tinha
perdido a funcionalidade quando `comercio.py` nasceu.

- **Select de quantidade fixa (1/5/10/25), não modal — opção (a) do card.**
  Um segundo `discord.ui.Select` com valores fixos é mais rápido de clicar
  (um toque, sem digitar) e não abre teclado no celular — o público daqui é
  quem já está DESCOBRINDO o item pelo menu (quem sabe o número exato usa
  `rpg comprar <item> <qtd>`, que aceita qualquer valor). Um modal seria
  mais flexível (qualquer quantidade), mas custa mais atrito exatamente pra
  quem o menu deveria servir melhor, e exigiria estender o `ShimCtx` pra
  cobrir o que `discord.ui.Modal.on_submit` precisa — nada que os comandos
  chamados hoje (`comprar`) realmente usam. Ficou fora por não ter ninguém
  que precisasse dele agora: sem modal, sem crescer o shim.
- **A descrição de cada opção de quantidade já mostra o TOTAL, não o preço
  unitário** — "5x" vem com "1.500 🪙 no total" (ou o que for), calculado
  em `_opcoes_quantidade()`. Resolve o "vale mostrar o custo total antes de
  confirmar" do card sem inventar um terceiro passo de confirmação: o
  próprio clique na opção já é a confirmação, porque o número que importa
  já estava visível antes do clique.
- **Fluxo: Comprar → item → quantidade → `comprar` de verdade via
  `ShimCtx`, `argumento=f"{chave} {qtd}"`.** Zero validação nova — `custo`,
  saldo insuficiente e entrega continuam 100% dentro do `comprar` de
  `bot.py`, chamado do mesmo jeito que antes (só a quantidade parou de
  estar hardcoded em `1`). `_pedir_quantidade_e_comprar()` mora em
  `PainelComercioBase` porque mercador e ferreiro compartilham o fluxo
  inteiro — só a lista de itens disponíveis (consumível vs equipamento)
  diferia, e isso já ficava a cargo de cada `comprar_btn`.
- **"Voltar" na tela de quantidade volta pro painel principal, não pro
  select de item.** `MenuSelecaoView`/`BotaoVoltarComercio` já tinham essa
  semântica fixa (sempre volta pro painel) desde o cartão anterior; dar à
  tela de quantidade uma navegação diferente ("voltar um passo" em vez de
  "cancelar tudo") exigiria uma pilha de navegação que nada mais no módulo
  usa. Cancelar no meio da compra custa reescolher o item — troca aceitável
  por não inventar um mecanismo novo pra um caso que devia ser raro.
- **Venda não mudou — só compra.** O card pediu isso explicitamente:
  vender é item-por-item porque a fricção ali é decidir o que sai da
  mochila, não repetir clique pra "mais uma unidade" — problema diferente
  do que motivou este cartão.
- **`ShimCtx` não cresceu.** Continua só `.author`/`.send()` — a opção (a)
  não precisou de `ctx.channel` nem `ctx.message`, então o "cuidado
  conhecido" do card não chegou a se materializar. Fica registrado aqui
  pro próximo cartão que PRECISAR de modal saber que vai ter que estender
  o shim, e com cuidado (ver aviso original em `comercio.ShimCtx`).
- **3 testes novos** (`tests/test_comercio.py`, 22 no total): escolher item
  não debita nada ainda (só abre o select de quantidade, com os 4 valores
  certos e o total calculado); comprar 5 numa sequência de duas interações
  debita `preço × 5` e entrega 5 unidades, com o painel restaurado no
  fim; tentar comprar sem moedas suficientes recusa exatamente como
  `rpg comprar` recusaria (mesma mensagem, via `ShimCtx`), sem debitar nem
  entregar nada.

## Equipamento no rpg status

`rpg status` mostrava Ataque/Defesa como números soltos, sem dizer de onde
vinham — e ninguém que não foi em raide sabia que slot de anel/colar existe.

- **`stats()` passou a expor `s["equipamento"]`** — os quatro slots
  (arma/armadura/anel/colar), cada um `None` (vazio) ou `(chave, dado)` com
  o dict já resolvido (`com_bonus_upgrade` já aplicado em arma/armadura).
  Zero conta nova: é literal o que `ficha()` já usava internamente, só que
  agora sai do escopo da função em vez de morrer ali. `rpg status` só lê.
- **Slot vazio mostra "*vazio*" em vez de sumir da lista** — de propósito,
  é como o jogador descobre que o slot existe.
- **Nível de melhoria (+1/+2) vem de `db.get_upgrade()` à parte**, não do
  bônus em si — ler o nível não é "recalcular", é mostrar um dado que já
  existe (a mesma leitura que `rpg melhorar` faz antes de agir).
- **Teste**: `tests/test_status_equipamento.py` (8 casos) — os 4 slots
  vazios por padrão, peça resolvida com e sem melhoria, texto sem "vazio"
  quando tudo equipado, e a conta final: `at.ataque()`/`at.defesa()`
  aplicados aos bônus mostrados batem exatamente com `s["atk"]`/`s["def"]`
  que o resto do embed já exibia.

## Ações de diálogo de todos os NPCs

Faltava dar às 28 NPCs (menos A Guia, carta própria) as ações que a Lore já
descrevia. Mercador e ferreiro só tinham o botão de comércio; taverneiro e
carroceiro nem tinham entrado no diálogo. Nenhuma sidequest neste corte — o
que a Lore marca como gancho de quest virou resposta de texto normal, e
`opcoes_por_estado` (existe desde 421e4e2) continua sem nenhum NPC usando.

- **`rpg descansar` e `rpg carroca` NÃO viraram redirecionamento — desvio
  deliberado do texto literal do card, confirmado com o Rafael.** O card
  pedia "mesmo padrão do `rpg loja`", mas `rpg descansar` documentava
  explicitamente "sem NPC físico exigido" — funciona em qualquer andar até
  o Selo, não só nos andares 1/10 que têm taverneiro. Gutar o comando
  quebraria descanso pros andares 2-9, uma mudança de REGRA, não só de
  porta de entrada. `rpg carroca` tem o mesmo formato (informativo, útil
  de qualquer andar). A pergunta que resolveu isso: os dois ficam de pé,
  exatamente como `rpg comprar`/`rpg vender` (que também nunca exigiram
  NPC físico por perto, e por isso sobreviveram no cartão do comércio) —
  só `rpg loja` morreu de verdade, porque a lista que ele mostrava foi
  substituída por dois comandos que já existiam. O menu do taverneiro/
  carroceiro é uma PORTA A MAIS, chamando os mesmos comandos via `ShimCtx`
  — não uma regra nova.
- **Fileira de opções + Sair nunca hardcoded — calculada a partir de onde a
  subclasse já parou.** `PainelComercioBase.__init__` roda depois de
  `super().__init__()` (que já populou `self.children` com os botões dos
  decorators da subclasse), pega `max(row) + 1` como a próxima linha livre,
  desenha as perguntas da Lore ali, e Sair uma linha depois (ou na mesma,
  se não teve pergunta nenhuma). Isso deixa Mercador (1 fileira de
  mecânica), Ferreiro (2 fileiras) e Taverneiro/Carroceiro (1 fileira)
  compartilharem a mesma base sem hardcode de número de linha em lugar
  nenhum — um NPC com mais perguntas no futuro não quebra o layout.
- **Sair virou 100% igual entre `DialogoView` (bot.py) e
  `PainelComercioBase` (comercio.py)**: `BotaoOpcaoComercio`/
  `BotaoSairComercio` são a mesma lógica de `BotaoOpcaoDialogo`/
  `BotaoSairDialogo`, só que precisando existir em `comercio.py` (que já
  não importa bot.py, evita circular). Duplicação de UI aceitável — são
  ~15 linhas cada, e as duas Views têm ciclos de vida diferentes (uma só
  conversa, outra abre sub-telas de select) que não compartilham base sem
  forçar acoplamento entre os dois módulos.
- **Bramm não tem `opcoes` — a chave nem existe no dict dele.** A Lore não
  tinha pergunta nenhuma pra ele; `opcoes_do_dialogo` já trata ausência
  igual a lista vazia (`dado.get("opcoes", [])`), então o menu dele só
  mostra Viajar e Sair, sem fileira de pergunta no meio.
- **Selen (andar 9) não precisou de nenhum código novo pra "não vender
  nada".** A Lore avisa que o botão Comprar "não se aplica a ela", mas
  como nenhuma receita de loja tem `andar_min == 9`,
  `equipamentos_do_andar(9)` já vinha vazio — o Comprar dela cai sozinho no
  mesmo fallback ephemeral "Nada à venda aqui agora." que qualquer andar
  sem estoque mostraria. Conferido, não assumido (ver
  `test_selen_comprar_nao_precisa_de_caso_especial`).
- **A rede do Torv (Kesh, Hjalmar, Selen) foi escrita numa passada só**,
  como o card pediu, pra não se contradizer: os três confirmam que ele
  treinou/é conhecido por todo ferreiro da torre, os três já o convidaram
  pra visitar/se mudar, e os três recebem a mesma recusa — ele fica porque
  "tem gente demais contando com isso". Fecha com a fala original dele
  ("Ninguém mais desce pra me render") em vez de contradizer.
- **Respostas escritas por mim de novo, mesmo acordo do cartão do
  diálogo (421e4e2).** A Lore trouxe só o tópico de cada pergunta
  ("perguntar sobre a barraca torta"), não a fala em si — os 5 NPCs de
  conversa que já tinham linha na Lore bateram exatamente com o que eu já
  tinha escrito naquele cartão (nenhuma mudança), e os 18 novos (mercador/
  ferreiro/taverneiro/carroceiro) seguem o mesmo tom.
- **Corrigido:** a fala do Bramm em `npcs.py` dizia "três vezes por dia";
  a Lore já tinha "quatro". Só o código estava desatualizado.
- **`falar()` ficou mais simples, não mais complexo.** Antes tinha um
  branch por mecânica (mercador/ferreiro→comércio, taverneiro→footer
  "rpg descansar", carroceiro→footer "rpg carroca") mais um fallback
  genérico que nunca era alcançado por "conversa"/"guia" (já tratados
  antes). Agora os quatro tipos de mecânica caem numa linha só
  (`comercio.abrir_comercio`), e o fallback — que ficou struturalmente
  inalcançável, já que os 6 tipos de NPC do jogo têm todos um branch
  próprio agora — foi removido.
- **Teste**: 32 casos em `test_comercio.py` (+14) — `_opcoes_destino` com e
  sem carroça ativa, Descansar/Viajar chamando os comandos de verdade via
  `ShimCtx`, o embed do carroceiro mostrando os dois estados (parada agora
  / próximo horário), Bramm só com Viajar+Sair, clicar numa pergunta edita
  a descrição sem desabilitar o painel, `rpg descansar`/`rpg carroca`
  continuam funcionando fora de qualquer NPC, e o caso da Selen. Mais 8
  casos em `test_dialogo.py` (+8) — só a Guia fica sem `dialogo`, nenhuma
  `opcoes` duplica um botão de mecânica (Comprar/Vender/Descansar/Sair/
  Viajar), a rede do Torv menciona ele nas três respostas, `abertura`
  sempre bate com a `fala` de `npcs.py`, Bramm sem `opcoes`, e a fala dele
  corrigida pra "quatro vezes".
- **Notion não atualizado nesta carta — MCP do Notion segue desconectado.**
  Guia da Torre e Lore ficam pendentes de sincronizar manualmente quando a
  conexão voltar (nada que mudasse a lista de comandos do jogo, só o
  conteúdo do diálogo — os comandos digitados continuam os mesmos).

## Instâncias de item — melhoria presa à peça, não mais ao jogador

Pré-requisito do Arcano (encantamento). **Esta carta não implementa
encantamento** — só o modelo de instância e a migração das melhorias
existentes. `upgrades(user_id, item, nivel)` chaveava a melhoria pelo par
(jogador, item): duas cópias do mesmo item eram indistinguíveis, e uma
peça melhorada era bloqueada de troca porque o bônus "pertencia" ao
jogador, não à peça — problema real quando o encantamento (que precisa
viajar com a peça numa troca) fosse entrar em cima disso.

Peça comum continua sendo só quantidade em `inventario`, sem identidade.
Peça ganha identidade — uma linha em `instancias` (id, dono, item,
nivel_melhoria, e `encantamento_atributo`/`encantamento_valor` já
criados agora, sem uso, pra não precisar de segunda migração quando o
Arcano nascer) — **só quando recebe melhoria**. `upgrades` continua no
schema (nunca se dropa tabela com dado real) mas não é mais escrita por
nada; virou histórico morto depois da migração.

### Forma do slot: coluna paralela, não o slot guardando id

`jogadores.arma`/`armadura` continuam guardando a CHAVE do item, sempre —
igual antes, pra peça comum e melhorada. Duas colunas novas,
`arma_instancia_id`/`armadura_instancia_id` (nullable), dizem SE a peça
equipada é uma instância e QUAL linha ela é.

Alternativa descartada: o slot guardar o id da instância em vez da chave
quando a peça é melhorada. Motivo de não fazer isso: `j["arma"]`/
`j["armadura"]` são lidos direto (sem passar por `stats()`) em pelo menos
3 arquivos (`combate.py` — afinidade de skill e bônus de arma nu,
`comercio.py` — listar o que está equipado no menu de Melhorar). Um slot
polimórfico (às vezes chave, às vezes id) obrigaria todo esses call sites
a saber diferenciar os dois formatos — risco real de esquecer um, sem
teste cobrindo 100% deles. Coluna paralela deixa a chave sempre presente
e sempre no mesmo formato; só quem precisa saber SE é instância (bônus de
melhoria/encantamento, trade) consulta a coluna nova.

### Onde mora uma instância desequipada: estado derivado, não coluna

Não existe coluna `local`/`equipado`. Uma instância pertence ao dono
(`instancias.dono`) e está "na mochila" sempre que o id dela **não**
aparece em nenhuma coluna `<slot>_instancia_id` desse mesmo dono
(`database.instancias_na_mochila`). Fonte de verdade única: os ponteiros
de slot em `jogadores` (mesma disciplina que `arma`/`armadura` já exigem
hoje pra peça comum). Alternativa descartada: uma coluna `local` explícita
seria mais fácil de consultar direto, mas cria duas fontes de verdade que
podiam dessincronizar se algum caminho (equipar, trade, desmanchar)
esquecesse de atualizar as duas.

Consequência prática: uma instância só nasce **equipada** — `rpg melhorar`
só opera na peça que já está no slot (regra que já existia), então a
primeira melhoria cria a instância e aponta o slot pra ela no mesmo
UPDATE. Ela só passa a "morar" na mochila depois, quando o jogador equipa
outra coisa no lugar (`rpg equipar` limpa o ponteiro sem mexer em
`inventario` — a instância não decrementa nem soma quantidade em lugar
nenhum, só muda se algum slot aponta pra ela).

### Migração dos 4 `upgrades` reais existentes

Roda dentro de `init_db()`, migração 12, mesmo padrão do projeto —
guardada por `if novas_instancias` (só roda quando as colunas de
instância ainda não existem), então idempotente por construção: rodar
`init_db()` de novo nunca reprocessa `upgrades`. A lógica de migração foi
extraída pra `database._migrar_upgrades_para_instancias(conn)` — testável
isolada (`tests/test_database_migracao.py`) sem precisar fingir schema
antigo.

Três casos, cada um com regra fechada (nenhum tinha exemplo real nos 4
`upgrades` do banco — todos estavam equipados, sem cópia extra, sem
órfã — mas a regra precisa existir pra qualquer estado futuro):

- **Peça equipada e melhorada** → vira instância equipada: cria a linha em
  `instancias` e aponta o `<slot>_instancia_id` do dono pra ela.
- **Peça não equipada, várias cópias comuns no inventário + uma linha de
  upgrade** → UMA cópia vira a instância melhorada (decrementa 1 de
  `inventario`), o resto continua comum. O jogo nunca soube diferenciar
  cópias além dessa única linha salva — não tem como saber qual "era" a
  melhorada além de tirar uma da pilha.
- **Linha de upgrade órfã** (jogador não tem mais o item, nem equipado nem
  na mochila) → descartada, não materializada. Não existe peça física pra
  prender a instância; inventar uma do nada daria item de graça.

Validado contra uma cópia de `aincrad.db` antes de subir: os 4 upgrades
reais (todos peça equipada, todos +1) viraram 4 instâncias corretas,
apontadas pelos slots certos, com `nivel_melhoria` preservado. Rodar a
migração duas vezes na mesma cópia não duplicou nada.

### Preço de venda de peça melhorada

`rpg vender` de uma instância usa a mesma curva de bônus do combate,
**preço × (1 + 0.12 × nível)** — mesmo número de `com_bonus_upgrade`, só
aplicado em moedas em vez de ATK/DEF. Consistente e fácil de justificar
pro jogador: a peça vale o que ela rende em combate.

### `rpg trade` perdeu o bloqueio de peça melhorada — decisão deliberada

Antes, `_checar_item_para_oferta` recusava qualquer item com
`get_upgrade(...) > 0` ("o bônus é preso a você"). Isso saiu: o bônus
agora é preso à PEÇA (instância com dono, id, nível), não ao jogador —
trocar só muda `instancias.dono`, o nível viaja junto. Isso cria mercado
de peças melhoradas entre jogadores, de propósito.

- `_commitar_troca` revalida cada instância ofertada dentro da mesma
  transação: `dono` ainda é quem ofereceu, e a instância não foi equipada
  por ele depois da oferta (senão cancela com motivo, sem mover nada —
  mesmo padrão de revalidação que já existia pra saldo/inventário).
- **Só instância DESEQUIPADA entra na oferta** — `ModalItem` só considera
  `db.instancias_na_mochila(user_id)`. Equipada continua bloqueada de
  trade, mas pelo motivo de sempre (peça equipada nunca pôde ser
  oferecida, `equipados = {...}` já barrava isso antes desta carta).
- **Limitação conhecida, documentada aqui em vez de resolvida**: se um
  jogador tem cópia COMUM e a instância modificada da mesma chave ao
  mesmo tempo, `ModalItem` só oferece a cópia comum (prioridade
  automática, sem seletor). Nenhum dos 4 casos reais tem essa
  duplicidade hoje — não valeu construir uma UI de desambiguação pra um
  cenário que não existe ainda. Se acontecer, o próximo passo é um
  seletor explícito no modal, não mudar a prioridade.
- Mesma prioridade "cópia comum primeiro, instância só se não sobrar
  comum suficiente" em `rpg vender` e `rpg desmanchar` — evita que um
  comando genérico por nome destrua/venda a peça melhorada sem querer
  quando existe cópia comum de sobra pra atender o pedido.
  `rpg equipar` é o oposto (prioriza a instância): equipar a pior cópia de
  propósito não tem uso real, e a instância é sempre igual ou melhor.

### Teste

`tests/test_database_migracao.py` (3 casos da migração + colunas novas),
`tests/test_status_equipamento.py` (bônus de melhoria lido da instância,
não mais de `upgrades`), `tests/test_trocas.py` (peça melhorada troca e o
bônus viaja; instância equipada por fora ou dona trocada por fora cancela
sem exceção). Migração validada contra cópia real de `aincrad.db` (ver
acima). Sem teste automatizado dedicado pra `rpg equipar`/`vender`/
`melhorar`/`desmanchar` como comandos Discord (a suíte não tinha isso
antes desta carta pra essas quatro tampouco, só pros helpers puros de
`profissoes.py`) — validação desses quatro é manual, jogando (ver Antes
de subir / teste no card original).

## Correção — anel e colar também carregam instância, e o gatilho da migração 12 tava presa a errada

Bug real encontrado antes de virar incidente: acrescentar coluna nova a
`COLUNAS_INSTANCIAS` (pra dar a anel/colar onde guardar instância, prérequisito
do Arcano em qualquer peça) reexecutaria `_migrar_upgrades_para_instancias`
inteira. O gatilho era "qualquer coluna do dict que falte" — `novas_instancias
= [c for c in COLUNAS_INSTANCIAS if c not in colunas]` — e a migração de dados
estava pendurada nesse mesmo `if`. Bastava a lista crescer pra condição virar
verdadeira nas colunas antigas mesmo já preenchidas, reprocessando `upgrades`
(que nunca é apagada, ver decisão original) e duplicando as 4 instâncias reais
em produção pra 8.

**Correção estrutural, não patch pontual**: a migração de dados (12) ficou
presa às DUAS colunas originais (`arma_instancia_id`/`armadura_instancia_id`),
marcadas **CONGELADAS** em comentário no próprio dict — nenhuma coluna nova
entra em `COLUNAS_INSTANCIAS` nunca mais. Slot de instância novo ganha dict e
migração PRÓPRIOS, com guarda independente. `anel_instancia_id`/
`colar_instancia_id` entraram assim, em `COLUNAS_INSTANCIA_ACESSORIOS` /
migração 13 — só `ALTER TABLE`, sem chamar `_migrar_upgrades_para_instancias`
(não existe `upgrades` de acessório pra migrar: `rpg melhorar` nunca aceitou
anel/colar, isso não mudou aqui).

Descartei as outras duas formas que o card ofereceu:
- **Flag de versão de schema** (tabela nova só pra marcar "migração X já
  rodou") — funcionaria, mas nenhuma outra migração do projeto usa esse
  padrão; todas se guardam por presença de coluna. Criar uma exceção só
  pra essa migração destoaria mais do que ajudaria.
- **Checar se `instancias` já tem linha** — frágil: um banco legítimo onde
  todo mundo já vendeu/desmanchou a peça melhorada ficaria com `instancias`
  vazia e a migração rodaria nunca deveria de novo, mesmo já tendo rodado.

Migração 13 não muda nada visível — não é possível melhorar anel/colar
(`rpg melhorar` continua recusando qualquer coisa que não seja `arma`/
`armadura`, sem alteração nesta carta) nem encantar (Arcano não existe
ainda), então as duas colunas ficam `NULL` pra todo mundo até o Arcano
nascer. `bot.stats()` ganhou `com_instancia()` — anexa o id da instância ao
dict do item sem aplicar bônus nenhum (diferente de `com_bonus_upgrade`,
que só arma/armadura usam) — só pra o Arcano ter de onde ler depois, sem
precisar reconsultar o banco. `rpg equipar` deixou de checar
`slot in ("arma", "armadura")` em dois pontos: como os quatro slots têm
coluna de instância agora, o código generalizado funciona igual pros
quatro, mesmo só arma/armadura realmente populando `arma_instancia_id`/
`armadura_instancia_id` hoje.

**Teste**: `test_migracao_13_anel_colar_nao_reexecuta_a_migracao_12`
simula exatamente o estado de produção (migração 12 já rodada, colunas de
acessório ainda não existem) via `ALTER TABLE ... DROP COLUMN` num banco
em memória, roda `init_db()` de novo e confere que o total de instâncias
não muda. Validado também contra uma **cópia do `aincrad.db` real**
(que já estava exatamente nesse estado — 4 instâncias, colunas de
arma/armadura presentes, sem as de acessório): depois de rodar a migração
13, continuam **4** instâncias, não 8. `COLUNAS_ESPERADAS` em

## Patch 0.3 — Encantador e Joalheiro

Dois ofícios novos, substituindo o Minerador (cortado do projeto — os
quatro ofícios ficam Forja/Alquimia/Encantador/Joalheiro). Dependia da
carta anterior (instâncias em anel/colar) porque o bônus dos dois ofícios
mora na peça, não no catálogo — a mesma chave (`espada_ferro`, `anel_joia`)
precisa poder valer coisas diferentes em duas cópias.

### Onde o bônus do Joalheiro foi guardado

`instancias` já tinha `encantamento_atributo`/`encantamento_valor`,
reservadas desde a carta de instâncias pro "Arcano" (o card que virou
Encantador). Essas duas colunas viraram a fonte de verdade do
**encantamento** — reuso direto, sem migração nova.

O bônus **base** do Joalheiro (o atributo que ele escolhe ao fabricar
anel/colar) não podia reusar as mesmas colunas: as duas camadas precisam
somar de forma independente ("anel de Joalheiro encantado pelo Encantador"
é o próprio pedido, sem trava). Duas colunas novas, **migração 14**,
`joia_atributo`/`joia_valor` em `instancias` — primeira migração do projeto
que altera uma tabela que não é `jogadores`, então o bloco em `init_db()`
lê `PRAGMA table_info(instancias)` em vez de `table_info(jogadores)` como
todas as anteriores. Fora isso, mesmo padrão de sempre (checa coluna
faltando, só then faz `ALTER TABLE`) — não precisou de dado histórico pra
migrar, porque nenhuma joia de Joalheiro existia antes desta carta.

`bot.com_instancia()` (que já existia, preparada exatamente pra isso desde
a carta de instâncias) ganhou o corpo que faltava: lê a instância uma vez
e aplica as três camadas que podem coexistir na mesma linha —
`nivel_melhoria` (+1/+2 do Forjador, só arma/armadura), `joia_atributo`/
`joia_valor` (vira `"atributo"`/`"bonus"` no dict do item, mesma chave que
acessório de raide e arma elemental já usavam) e `encantamento_atributo`/
`encantamento_valor` (vira `_encantamento_atributo`/`_encantamento_valor`,
com underscore de propósito — não pode colidir com `"atributo"`/`"bonus"`,
senão a soma das duas camadas vira substituição). Isso também **absorveu**
o antigo `com_bonus_upgrade`: eram duas funções fazendo duas leituras de
banco separadas pra arma/armadura (uma pra melhoria, outra pro que virou
encantamento); virou uma função, uma leitura, pras 4 peças. `stats()` passa
a chamar só `com_instancia()` pros 4 slots.

`bonus_atributo_equipamento()` ganhou uma segunda passada: além de somar
`"atributo"`/`"bonus"` (como já fazia), soma `_encantamento_atributo`/
`_valor` de qualquer peça que tiver — por isso agora recebe `armadura`
também (antes só `arma, anel, colar`, porque armadura nunca tinha bônus de
atributo próprio; agora pode ter encantamento). O atributo de joia e o de
encantamento entram só no `atribs` **efetivo** de `stats()`, nunca na
coluna crua do jogador — mesma regra que já valia pra acessório de raide,
então "não conta pra requisito de habilidade" saiu de graça, sem código
novo (`habilidades.conhecida()` já lia a coluna crua, não `s['atribs']`).

### A curva própria (Encantador e Joalheiro não fabricam em série)

`xp_para_subir()` passou a receber a profissão. Forja/Alquimia continuam
com `50 * nível` (comportamento idêntico a antes, só o parâmetro mudou).
Encantador/Joalheiro usam uma tabela fixa (`XP_NIVEL_MAGICO`,
`profissoes.py`) que fecha em exatamente 75 ações de 25 XP fixo do nível 1
ao 9 (não 10 — `NIVEL_MAXIMO_MAGICO = 9`, teto diferente do resto).
`aplicar_xp_profissao()` também passou a receber a profissão, e todo call
site dela (craftar/melhorar/desmanchar da Forja) foi atualizado — mecânico,
sem mudar comportamento nenhum desses três.

O bônus que cada nível entrega (`BONUS_POR_NIVEL_MAGICO`) e o custo em
moedas por bônus (`CUSTO_MOEDAS_POR_BONUS`) são **a mesma tabela pros dois
ofícios** — o pedido já confirmava isso pela conta ("encantar as 4 peças no
teto = 27.200" bate com 6.800×4, e "anel + colar de Joalheiro no teto =
13.600" bate com 6.800×2, o mesmo 6.800 de bônus+7). O material muda: cada
ofício tem sua própria escada de andar (`ANDARES_ENCANTADOR` ímpares,
`ANDARES_JOALHEIRO` pares) e material (`MATERIAL_ENCANTADOR`/
`MATERIAL_JOALHEIRO`), mas o índice que liga bônus a andar
(`INDICE_ANDAR_POR_BONUS`) é compartilhado. `material_magico(bonus,
profissao)` ficou separado de `custo_magico(nivel, profissao)` de propósito
— o mapeamento bônus→material é a invariante real do pedido, nível→bônus é
uma composição por cima; separar os dois deixou o teste
(`test_material_do_encantador_...`) exercitar a tabela certa sem embutir a
composição de nível junto (um teste que testasse só via `custo_magico`
passando "nível" como se fosse "bônus" mentiria — bônus 2 e nível 3 não são
o mesmo número, ver `BONUS_POR_NIVEL_MAGICO[3] == 2`).

O bônus entregue **não é escolha do jogador** — é o que o nível atual dele
rende. Um Encantador nível 3 sempre encanta em bônus 2, nunca escolhe
gastar mais material por um bônus menor ou maior.

### Por que reencantar depois de remover dá XP de novo

É o mecanismo que já existia pro resto do craft (craftar, melhorar,
desmanchar — todos dão XP pela AÇÃO, não pelo resultado final). Encantar
grava `XP_ACAO_MAGICA = 25` sempre que roda com sucesso, remover não some
XP nenhum de volta (não tem como "devolver" nível de ofício). O pedido
descreve isso como intencional e já antecipa o freio: reencantar depois de
remover queima moeda de novo (o custo pelo bônus atual, não tem desconto de
segunda vez) — self-balanceado, sem precisar de trava extra tipo cooldown
ou limite de remoções.

### Encantador (`rpg encantar`/`rpg desencantar`)

- Vale nos 4 slots (arma/armadura/anel/colar) — `_slot_equipamento()` faz o
  mesmo parsing que `melhorar()` já tinha pra arma/armadura, estendido.
- Recusa reencantar peça já com `encantamento_atributo` na instância —
  manda desencantar primeiro. Sem essa checagem, encantar de novo
  sobrescreveria o valor salvo silenciosamente (`db.definir_encantamento`
  não protege sozinha, quem chama tem que checar antes).
- Remover custa **metade do custo de encantar aquele valor**
  (`CUSTO_MOEDAS_POR_BONUS[bonus] // 2`) — só moeda, sem devolver material
  (o pedido não menciona refund de material, só de moeda; diferente de
  `rpg desmanchar`, que devolve material porque desfaz uma fabricação
  inteira — desencantar desfaz só a camada de cima).
- Peça sem instância ainda (arma/armadura/anel/colar comum, nunca
  melhorada) ganha uma na hora de encantar (`db.criar_instancia` +
  `{slot}_instancia_id`) — mesmo caminho que `melhorar()` já usava pra
  criar a primeira instância de uma peça.

### Joalheiro (`rpg lapidar`)

Fabrica direto pra dentro de `instancias` (`db.criar_instancia(...,
joia_atributo=, joia_valor=)`) — nunca passa por `db.add_item` (cópia
comum), porque não existe "cópia comum" de uma peça de Joalheiro: o
bônus varia por fabricação, então toda peça nasce como instância própria,
flutuando na mochila até ser equipada (mesmo estado derivado que peça
melhorada desequipada já usa). Dois itens novos no catálogo, `anel_joia`/
`colar_joia` — **sem** `"atributo"`/`"bonus"` estáticos (ao contrário de
`anel_forca` etc.): esses dois campos só existem depois de `com_instancia`
ler a instância, porque variam por peça.

`rpg receitas`/`rpg craftar` continuam existindo mas não servem pra estes
dois ofícios (o catálogo `RECEITAS` é pra Forja/Alquimia, com nível fixo
por item — Encantador/Joalheiro não têm "item de catálogo", o resultado
depende do nível de quem fabrica). `rpg receitas` com um desses dois
ofícios agora devolve uma mensagem apontando pro comando certo em vez do
embed vazio que apareceria antes.

### A armadilha do `ACESSORIOS_RAIDE` — corrigida antes das peças existirem

`game_data.ACESSORIOS_RAIDE` era `tuple(k for k, v in ITENS.items() if
v.get("tipo") in ("anel", "colar"))` — qualquer anel/colar novo entrava
sozinho na mesa de loot da raide. `anel_joia`/`colar_joia` teriam caído
nessa lista no mesmo commit que os criou, sem ninguém pedir. Trocado por
tupla **explícita** com os 8 originais, comentada como "não muda nesta
carta nem em nenhuma futura sem decisão direta" — mais simples que uma
flag nova no dict do item (`"raide": True`), e os 8 acessórios de raide já
são um conjunto fechado (`decisoes.md` § Pacote 1 já dizia isso).
Testado (`test_acessorios_raide_nao_inclui_itens_do_joalheiro`).

### Dez NPCs novos — falas não são do Rafael

`encantador` (ímpares: Baldo/1, Lira/3, Corin/5, Talla/7, Astrea/9) e
`joalheiro` (pares: Orin/2, Kef/4, Mira/6, Vesna/8, Eco de uma Joalheira/10)
são dois tipos novos em `npcs.py`, com bancada (`bancada_no_andar` já
generalizado — só olha `PROFISSOES[profissao]["npc"]`, funcionou pros dois
sem mudança). `dialogos.py` ganhou as 10 entradas num bloco próprio (mesmo
padrão dos 9 NPCs de tipo `conversa`, que também ficam agrupados por
categoria em vez de por andar). **As falas e as perguntas de diálogo dos
10 são inventadas pra fechar a carta — não são do Rafael.** Mesmo acordo
dos 9 NPCs de conversa anteriores: tom estabelecido, ele revisa/reescreve
quando quiser.

`comercio.py` ganhou `EncantadorView`/`JoalheiroView`, registradas em
`VIEW_POR_TIPO` — mesmo padrão do `FerreiroView` (botão que recusa
ephemeral se o ofício não bate, dois selects em sequência reaproveitando
`abrir_selecao`/`MenuSelecaoView` já existentes, sem UI nova). Testado
ponta-a-ponta com interação fake (mesma estratégia de
`tests/test_comercio.py`): clicar Encantar → escolher peça → escolher
atributo → moedas debitadas e instância com o encantamento certo; clicar
Lapidar → escolher anel/colar → escolher atributo → instância nova na
mochila.

### Teste

`tests/test_encantador_joalheiro.py` (curva de XP, tabela de bônus/custo/
material, `com_instancia` somando joia+encantamento+melhoria na mesma
peça, requisito de skill não conta o bônus, `ACESSORIOS_RAIDE` fechado),
`tests/test_comercio_encantador_joalheiro.py` (fluxo ponta-a-ponta dos dois
botões novos), migração 14 em `tests/test_database_migracao.py` (colunas
criadas, idempotente, não reprocessa `upgrades`).

**Não testado automaticamente**: os 10 diálogos novos (mesma situação dos
9 anteriores — conteúdo, não lógica) e o comando de texto puro
`rpg encantar`/`rpg lapidar` sem passar pelo botão (coberto indiretamente
pelos testes de comércio, que chamam o `.callback()` de verdade via
`ShimCtx`, igual ao resto do craft).

## Despertar (patch 0.3)

`rpg comecar` deixou de ser um embed único e virou sequência por botão:
abertura → classe → ofício → pronome → Elna acorda o jogador com as poções →
diálogo com ela. Módulo novo, `despertar.py`, mesmo padrão de `npcs.py`
(concentra a plumbing sem mexer em `game_data.py`).

- **Abandonar no meio recomeça do zero, de propósito.** Nada é gravado no
  banco até o botão de pronome ser clicado — classe e ofício ficam só como
  atributo da própria `View` (`EscolhaOficioView.classe`, por exemplo),
  repassados adiante a cada `edit_message`. Fechar o Discord no meio, ou só
  deixar o botão expirar (timeout de 300s), não deixa registro parcial: como
  não existe jogador nenhum pra achar, `rpg comecar` de novo é
  indistinguível de começar pela primeira vez. A alternativa (gravar a cada
  passo e ter um "estado de criação" no banco) resolveria o mesmo problema,
  mas com mais uma coluna e mais um jeito de o jogador ficar preso num
  estado esquisito se travar no meio — não gravar nada é mais simples e
  cobre o requisito sozinho.
- **Nomes de classe/ofício com gênero usam o marcador de
  `pronomes.concordar()`, não um par de campos.** `CLASSES[x]["nome"]` e
  `PROFISSOES[x]["nome"/"titulo"]` viraram string com marcador
  (`"Ladin{o|a}"`, `"Forjador{|a}"`) em vez de, por exemplo,
  `{"nome_m": ..., "nome_f": ...}`. Reaproveita a mesma função que já existe
  pra concordância de frase — todo lugar que lia `dados["nome"]` cru passou
  a chamar `pronomes.concordar(dados["nome"], pronome)` (bot.py,
  profissoes.py, comercio.py — a mesma troca se repete). `Alquimista` ficou
  sem marcador — o regex de `concordar()` exige um `|` dentro das chaves,
  então uma string sem marcador nenhum simplesmente volta igual, sem
  precisar de `if` nenhum pra invariável. Efeito colateral que precisou de
  ajuste: `bot.encontrar_classe` comparava `texto normalizado` contra
  `dados["nome"]` cru pra casar `rpg classe guerreiro`; com marcador, isso
  ia comparar contra a string `"Guerreir{o|a}"` literal e nunca casar —
  agora compara contra as duas formas já concordadas (`concordar(nome,
  "ele")` e `concordar(nome, "ela")`), o que também deixou `rpg classe
  guerreira` funcionar como sinônimo de `rpg classe guerreiro`, de graça.
- **`Ferreiro` virou `Forjador`/`Forjadora`** — `PROFISSOES["forja"]["titulo"]`,
  em todo lugar que aparece (não só no despertar): `rpg profissao`, troca de
  ofício, recusa de bancada errada. `FerreiroView` (comercio.py) e o NPC
  `tipo: "ferreiro"`/"o Ferreiro Aposentado" (npcs.py, Torv) são conceito
  diferente — loja/NPC, não o título do jogador — e não mudaram. `APELIDOS`
  ganhou `forjador`/`forjadora` como sinônimo de `forja`; `ferreiro` como
  apelido continua valendo, ninguém que já digitava isso precisa aprender
  de novo.
- **O gate de `rpg comecar` é `classe is None`, não "a linha existe".**
  `database.resetar_temporada()` zera classe/profissão mas **mantém** a
  linha do jogador (título equipado, mortes, `criado_em`) — é assim desde
  antes deste cartão. O reset de temporada do 0.3 bundle exige que os 13
  jogadores atuais passem pela sequência inteira de novo, sem atalho —
  então o gate de `comecar` (bot.py) precisou trocar de "existe jogador?"
  pra "esse jogador já tem classe?": quem foi resetado (linha existe,
  classe `NULL`) cai de novo no despertar e sai do outro lado com título e
  mortes intactos, só classe/ofício/pronome escolhidos de novo. **Este
  cartão só mudou a lógica do gate — `resetar_temporada()` em si não foi
  executado contra o banco de produção; o Rafael decide quando rodar o
  reset de verdade.**
- **Os 8 cards de explicação (um por classe, um por ofício, mostrados antes
  da escolha) são texto PROVISÓRIO, escrito pra fechar o cartão — não são
  do Rafael.** Moram em `despertar.CARDS_CLASSE`/`CARDS_OFICIO`, separados
  de `dialogos.DESPERTAR` de propósito: essa segunda constante é só o texto
  exato do Rafael (abertura, confirmações de classe/ofício, falas da Elna),
  colado sem alterar vírgula. Mesmo acordo já usado nos 10 NPCs de
  Encantador/Joalheiro — ele revisa/reescreve os cards quando quiser.
- **`{classe}`/`{oficio}` são placeholder de `str.format()`, resolvidos
  DEPOIS do marcador `{opcao|opcao}` de `concordar()`, nunca antes.**
  `dialogos.DESPERTAR["confirmacao_classe"]` tem os dois tipos de chave na
  mesma string (`"...era um{|a} {classe}!..."`). Como o regex de
  `concordar()` exige um `|` dentro das chaves, ele ignora `{classe}` (sem
  `|`) e resolve só o marcador de gênero — sobra só o placeholder de nome
  pro `.format()` seguinte. Se a ordem fosse invertida, `.format()` bateria
  primeiro no `{|a}` sobrando e quebraria (campo sem nome com `|` dentro não
  é sintaxe válida de `.format()`).
- **A confirmação de classe/ofício concorda no pronome ANTES de o pronome
  existir.** A pergunta de pronome só vem depois da de ofício — nesse
  meio-tempo, `pronomes.concordar(texto, None)` resolve pra forma ele/elu,
  que é o mesmo fallback que a função já tem documentado pra pronome
  ausente/inválido (mesmo espírito do default `'elu'` da coluna). Não é
  gambiarra nova pro despertar, é o comportamento padrão já existente sendo
  usado no único lugar onde o pronome genuinamente ainda não existe.
- **`obter_ou_criar_canal_privado` (bot.py) é a lógica de `rpg priv`
  extraída pra função**, reaproveitada por `rpg comecar` em vez de duplicar
  categoria/overwrites/`create_text_channel`. `despertar.py` não importa
  `bot.py` (evita import circular, já que `bot.py` importa `despertar.py`) —
  recebe a `DialogoView` real por parâmetro em `iniciar_despertar()`, não por
  import direto.
- **`rpg comecar` aponta pra `rpg ajuda` no fechamento, não pra `rpg
  h`/`rpg adv`** — de propósito, pra empurrar quem acabou de chegar a
  explorar o mundo antes de aprender os atalhos de grind.
- **A sala privada nasce ANTES da sequência, não mais no fim dela —
  inversão deliberada.** Até aqui, `rpg comecar` respondia no canal onde a
  pessoa digitou e só criava/reaproveitava a sala privada
  (`obter_ou_criar_canal_privado`) depois do clique de pronome, junto com a
  gravação no banco — coerente com "nada grava até o pronome" (ver acima).
  Agora `rpg comecar` cria/reaproveita a sala **primeiro**, responde no canal
  de origem só apontando pra ela ("sua sala é #torre-fulano, o despertar te
  espera lá"), e a sequência inteira — abertura, classe, ofício, pronome,
  Elna, fechamento — roda dentro da sala, nunca mais no canal onde o comando
  foi digitado. `iniciar_despertar()` recebe o canal já pronto em vez de uma
  função de criação; cada `View` da sequência carrega esse canal (`.canal`)
  e manda tudo pra lá (`canal.send`), não mais pra `ctx.send`.
  - **Consequência aceita**: quem digita `rpg classe` errado e desiste na
    primeira tela deixa uma sala criada sem personagem nenhum (nada grava
    até o pronome, isso não mudou). Não é vazamento — a segunda tentativa de
    `rpg comecar` acha a sala pelo nome (`obter_ou_criar_canal_privado` já
    fazia isso pra `rpg priv`) e reaproveita a mesma, sem duplicar. Vale a
    troca: a cena inteira (a abertura falada pela Elna, os cards de
    classe/ofício) acontece num canal só do jogador desde o primeiro
    segundo, em vez de vazar pro canal público até o pronome.
  - Se a criação da sala falhar (sem permissão de Gerenciar Canais, limite
    de canais do Discord), `obter_ou_criar_canal_privado` já manda o aviso
    e devolve `None` — `rpg comecar` simplesmente não chama
    `iniciar_despertar()` nesse caso, então não existe despertar pela
    metade.
  - Quem já tem classe continua caindo no gate de sempre ("O gate de
    `rpg comecar` é `classe is None`", acima) sem tocar em canal nenhum — a
    criação de sala só acontece depois de passar por esse gate.
- **`rpg classe` e `rpg profissao` pararam de escolher — a escolha só existe
  dentro do despertar agora.** Antes deste cartão, os dois comandos ainda
  ofereciam escolher classe/ofício pela primeira vez (redundante com o
  despertar, que já faz isso no clique do pronome) — dois caminhos pra
  mesma coisa. `rpg classe` virou puramente informativo: sem argumento
  mostra a classe do próprio jogador (habilidades base + os ramos de
  ascensão que ela abre, sem número de nível — `game_data.ASCENSOES` não
  carrega nenhum campo de nível, e a ascensão em si ainda não é jogável, só
  mapa); com argumento mostra a classe pedida, por curiosidade, sem travar
  nada. `rpg profissao` idem para o ofício, mas a **troca**
  (`rpg profissao trocar <novo>`) continua morando ali — é onde ela morava
  antes deste cartão também, decisão de cartão anterior, não mexida agora.
  Quem está sem classe/ofício (pós-`resetar_temporada`, antes de rodar
  `rpg comecar` de novo) recebe um aviso apontando pro despertar em vez do
  menu de escolha que existia antes.
  - Todo texto vem de `game_data.CLASSES`/`HABILIDADES`/`ASCENSOES` e
    `profissoes.PROFISSOES`/`RECEITAS` — nada digitado solto no comando,
    pra não desatualizar sozinho na próxima mudança de balanceamento.

### Teste

`tests/test_despertar.py`: sequência não grava nada até o pronome, grava
classe/ofício/pronome/3 poções juntos no clique do pronome, concordância nas
confirmações e na fala da Elna (pronome ainda não escolhido cai em ele/elu,
depois do escolhido usa o de verdade), segunda sequência não sobrescreve
quem já terminou a primeira, autor errado recebe recusa sem mudar o painel,
o gate de `rpg comecar` (recusa quem já tem classe, libera quem foi
resetado mesmo com título/mortes, libera jogador novo), `rpg pronome`
sumiu. Cobre também a inversão da sala: `rpg comecar` cria a sala **antes**
de chamar `iniciar_despertar()` (ordem verificada, não só presença de
chamada), passa o mesmo canal duas vezes seguidas quando
`obter_ou_criar_canal_privado` devolve reaproveitado (abandonar e tentar de
novo não duplica), não chama o despertar quando a sala falha, e quem já tem
classe nem toca em `obter_ou_criar_canal_privado`. As mensagens de fim de
sequência (Elna, fechamento) são verificadas indo pro `canal` fake, não pro
`ctx` do canal de origem. Segue a mesma estratégia de
`tests/test_comercio.py` — interação fake, sem discord.py conectado de
verdade; a `DialogoView` da Elna em si não é recoberta aqui de novo, já é
indiretamente testada via `bot.py`.

`tests/test_classe_profissao_wiki.py`: `rpg classe`/`rpg profissao` sem
argumento não alteram o banco (snapshot antes/depois igual), apontam pro
despertar quando o jogador está sem classe/ofício (pós-reset de temporada)
em vez de oferecer um menu de escolha, `rpg classe <outra>` só mostra a
wiki da classe pedida sem travar nada, a wiki reflete `game_data.HABILIDADES`
mutado em tempo de teste (texto/custo não são hardcoded no comando), e a
troca de ofício (`rpg profissao trocar <novo>`) continua funcionando.

**Não testado automaticamente**: os 8 cards (conteúdo, não lógica, mesma
situação dos diálogos de NPC) e a sequência de verdade jogando no Discord —
criação do canal privado, abandonar de fato fechando o cliente, timeout de
300s expirando.

## Padrão — mapa de domínio nunca é subscript direto

Terceira vez que o mesmo formato de bug derruba um comando: um dict literal
indexado direto por uma chave que vem de dado (`ANDAR_MATERIAL[andar_min]`
pras armas elementais, o dict de material de upgrade duplicado entre
`custo_melhorar`/`refund_desmanche`, e agora `bot.py:849` — o papel de cada
NPC em `rpg npcs` montado com `{"mercador": ..., ...}[n["tipo"]]`, sem chave
pra `encantador`/`joalheiro`, que derrubava o comando inteiro em qualquer
andar com um dos dois ofícios mágicos).

Nas três vezes o mapa cobria os tipos que existiam quando foi escrito e ficou
pra trás quando um tipo novo (andar, item, ofício, NPC) foi semeado no banco
sem ninguém lembrar de voltar no dict.

**Padrão do projeto a partir daqui**: todo mapa de domínio (tipo de NPC, tipo
de item, andar → algo) é uma **constante nomeada no topo do módulo**, nunca
um dict literal dentro da função que usa, e o acesso é sempre **com padrão**
(`.get(chave, default_seguro)`), nunca subscript direto (`dict[chave]`) — a
não ser que a chave já tenha sido validada antes (ex.: contra
`ITENS`/`CLASSES` no momento da criação). Um tipo sem entrada vira
comportamento degradado (linha sem descrição, custo zero, o que fizer sentido
no contexto), nunca `KeyError` derrubando o comando pro jogador.

- **`bot.py` — `PAPEL_NPC`**: extraído do literal dentro de `listar_npcs`
  pra constante ao lado de `ICONES_NPC` (que já usava `.get()` corretamente
  desde antes — só o dict de papel tinha regredido pro subscript direto).
  Ganhou as entradas de `encantador`/`joalheiro` que faltavam.
- **Teste-contrato, não teste-de-lista-fixa**: `tests/test_npcs_listagem.py`
  varre os tipos que EXISTEM em `npcs.NPCS` (todos os andares) e afirma que
  cada um tem entrada em `PAPEL_NPC` — não fixa "mercador, ferreiro, ..." a
  mão, senão o teste passaria mudo no próximo tipo esquecido, do mesmo jeito
  que o bug passou mudo três vezes. Cobre também que montar a listagem pra
  todo andar semeado não levanta exceção nenhuma.

## Correção — Instâncias de item: três lacunas na mesma tabela

Revisão pós-Patch 0.3, sem sintoma reportado em jogo ainda — achadas lendo o
código de Encantador/Joalheiro contra o que este arquivo já dizia. As três
moram em `instancias` (melhoria do Forjador, joia do Joalheiro, encantamento
do Encantador). Nenhuma tinha teste antes desta correção.

### `rpg desencantar` reembolsava — a decisão já registrada acima dizia o
### contrário

A seção "Encantador (`rpg encantar`/`rpg desencantar`)" já dizia **"Remover
custa metade do custo de encantar aquele valor"** — mas o código fazia
`moedas = moedas + reembolso`, devolvendo em vez de cobrar. O código
divergiu da decisão já registrada, provavelmente na hora de implementar.
Corrigido pra cobrar (`profissoes.desencantar`): recusa com a mensagem
dizendo quanto falta quando o jogador não tem o valor, mensagem de sucesso
passou de "X de volta" pra "custou X". Valores batem com
`CUSTO_MOEDAS_POR_BONUS[bonus] // 2`, mesma tabela de sempre: +1=200,
+2=450, +3=800, +4=1.300, +5=1.900, +6=2.600, +7=3.400. Sem essa cobrança
nas duas pontas, o refarm de XP (encantar → remover → encantar) parava de
queimar dinheiro na remoção — era justamente esse custo duplo que
justificava não travar o refarm com cooldown nenhum.

**Guia da Torre**: a seção do Encantador ainda diz "devolve metade" — precisa
virar "custa metade" quando isso subir pra produção.

### `rpg vender` — cada camada de bônus soma o próprio valor de revenda

Antes, o preço de uma instância só escalava por `nivel_melhoria` (+12%/nível,
Forjador). Duas consequências: uma joia do Joalheiro nunca tem
`nivel_melhoria`, então um Anel Lapidado +1 e um +7 vendiam pelo mesmo preço
fixo (metade do `"preco"` de catálogo, 3.800); e uma peça encantada pelo
Encantador tinha o valor do encantamento **sumindo** na venda, camada nenhuma
lia `encantamento_valor`.

`bot.preco_venda_instancia(dado, instancia)`: joia usa como base
`CUSTO_MOEDAS_POR_BONUS[joia_valor] // 2` (ancorado no que a peça custou pra
fabricar, mesma regra de "equipamento revende por metade" — não o `"preco"`
de catálogo, que é só um placeholder pra peça comum); melhoria continua a
conta antiga quando não é joia (as duas são mutuamente exclusivas na
prática — joia nunca passa por `rpg melhorar`). Encantamento soma
`CUSTO_MOEDAS_POR_BONUS[encantamento_valor] // 2` por cima de qualquer uma
das duas bases, porque é camada independente que pode conviver com as
outras (mesmo espírito de `bonus_atributo_equipamento`).

### Duplicata da mesma chave: ordinal em vez de id de banco

`equipar`/`vender` indexavam a mochila com `{i["item"]: i for i in
instancias_na_mochila(...)}` — um dict comprehension colapsa pra UMA
instância por chave (a última iterada). Com dois anéis do Joalheiro
desequipados ao mesmo tempo, só um ficava alcançável; o outro não dava pra
equipar nem vender, apesar de continuar dono do jogador — peça paga
inacessível, o mais grave dos três.

- **`db.instancias_por_chave(user_id)`**: agrupa `instancias_na_mochila` (que
  ganhou `ORDER BY id`, ordem de criação estável) numa lista por chave, em
  vez de colapsar num dict de valor único. A ordem é a mesma em toda
  listagem/escolha — instância mais antiga é sempre #1.
- **O número que já existia** (`separar_quantidade`, mesmo mecanismo de
  `rpg vender poção 3`) virou o seletor: com cópia comum cobrindo o pedido,
  continua significando quantidade (comportamento antigo, sem mudança);
  sem cópia comum e mais de uma instância da mesma chave, passa a escolher
  QUAL — `rpg equipar anel lapidado 2`, `rpg vender anel lapidado 2`. Sem
  número, cai na #1 (mesmo comportamento de antes quando só existia uma).
  `equipar` ganhou esse parsing (antes não tinha nenhum, não precisava).
  Índice fora do intervalo recusa com contagem, não silencia nem escolhe
  sozinho.
- **`rpg inventario` mostra o bônus da instância** (`bot.rotulo_instancia`,
  reaproveitado nas mensagens de sucesso de `equipar`/`vender`) — sigla e
  valor da joia, "encantado SIGLA +N" quando tem encantamento, "+N" de
  melhoria quando tem — e o `(#N)` só aparece quando há mais de uma
  instância da mesma chave (mostrar sempre seria ruído pro caso comum de
  uma só). Sem isso, "escolher a #2" não tinha como funcionar: o jogador não
  tinha nenhuma pista de qual era qual.

### Teste

`tests/test_instancias_item.py`: desencantar cobra o valor exato por bônus
(1 a 7) e recusa sem saldo sem tocar na instância; preço de venda da joia
sobe com o bônus (+1 vende por 200, +7 por 3.400) e o encantamento soma por
cima do preço em vez de sumir; duas instâncias da mesma chave são as duas
alcançáveis por `equipar` e por `vender` (inclusive a mais antiga, que era a
presa); índice além da quantidade disponível recusa com mensagem clara;
`rpg inventario` mostra atributo+valor da joia e numera (#1/#2) só quando há
duplicata, sem número nenhum sobrando pro caso de uma instância só.

## Avatar do jogador — `rpg avatar`

Cosmético puro: o jogador escolhe uma imagem (anexo ou link) que aparece
como `set_thumbnail` no `rpg perfil`. `avatar.py`, módulo próprio no padrão
simples `instalar(bot)` de `admin.py`/`agenda.py` — não toca em stats nem
combate, só em `jogadores.avatar_msg_id`/`avatar_url` e no canal de arquivo.

**A fonte da verdade é o ID DA MENSAGEM repostada, não a URL do anexo.** A
URL de anexo do Discord vem assinada e com prazo — os parâmetros `ex`, `is`
e `hm` no fim do link (`ex` é o timestamp de expiração, em hex, unix
seconds). O que expira é a ASSINATURA, não o arquivo: enquanto a mensagem
existir, o anexo continua lá, e pedir a mensagem de novo
(`canal.fetch_message`) devolve uma URL nova e válida pro mesmo arquivo. É o
tipo de coisa que alguém "simplifica" depois (guardando só a URL, ou trocando
por link cru do jogador) sem entender por que existe — documentando aqui
pra isso não acontecer.

- **Nunca guarda a imagem em BLOB nem em pasta local, nunca guarda o link
  externo cru como fonte.** Link externo passa pelo mesmo caminho que
  anexo: baixa (`avatar._baixar_link`, `aiohttp`) e reposta em
  `CANAL_ARQUIVO_ID` (`.env`, canal dedicado, mesmo padrão de leitura que
  `CANAL_TORRE_ID`) — assim o avatar não depende do imgur/Picrew do
  jogador continuar no ar.
- **`avatar.obter_avatar_atualizado(bot, jogador)` é o único ponto que lê
  avatar pra exibir** — usado tanto por `rpg perfil` (`bot.py`, `perfil()`)
  quanto por `rpg avatar` sem argumento. Se a URL em cache
  (`jogador["avatar_url"]`) ainda não venceu (checado com
  `MARGEM_EXPIRACAO_SEG = 300` de folga, pra nunca mandar pro Discord uma
  URL que vence nos próximos minutos), usa direto — **zero chamada de
  API**. Só refaz o `fetch_message` quando venceu (ou a URL é ilegível/sem
  `ex`), e atualiza o cache no banco depois.
- **`fetch_message` falhando (mensagem apagada, canal sumiu, `HTTPException`
  em geral) nunca quebra `rpg perfil`** — trata como avatar ausente
  (`None`, sem thumbnail), igual a nunca ter definido. Imagem é cosmético;
  não pode ser motivo de um comando central do jogo quebrar.
- **Validação com mensagem clara, nunca "erro ao processar"**: só png/jpg/
  webp (`TIPOS_ACEITOS`, comparado contra o `content_type` normalizado —
  corta o `; charset=...` que às vezes vem junto), até 8MB
  (`TAMANHO_MAXIMO_BYTES`). Pra link, `_baixar_link` lê no máximo
  `TAMANHO_MAXIMO_BYTES + 1` bytes mesmo que o `Content-Length` minta ou
  falte — nunca lê um corpo arbitrariamente grande pra memória só pra
  descobrir depois que passou do limite.
- **`rpg avatar` sem argumento é lista, não frase com link costurado no
  meio** (`_embed_avatar`): mostra o avatar atual (ou diz que não tem),
  como trocar, e "onde fazer a arte" com o Picrew como primeiro item —
  formato pensado pra crescer sem reescrever a mensagem quando um segundo
  caminho (agente de IA, ainda não existe) for adicionado.
- **`rpg removeravatar @jogador`, restrito ao dono (`admin.py`), sem
  `ConfirmarAcao`** — diferente de `resetartemporada`/`resetarjogador`
  (que usam a view de confirmação porque perdem progresso de jogo de
  verdade), tirar avatar é reversível na hora e o Rafael só roda o comando
  depois de já ter visto a imagem problemática — não precisa de "tem
  certeza?" pra uma decisão que ele já tomou olhando.
- **Colunas `avatar_msg_id`/`avatar_url` em `jogadores`, migração 15,
  ambas `NULL` por padrão** (`COLUNAS_AVATAR`, `database.py`) — cosmético
  igual `titulo`: **não entram em `resetar_temporada()`**, sobrevivem ao
  reset de temporada como título e `criado_em`.

### Teste

`tests/test_avatar.py`: definir por anexo salva `avatar_msg_id`/`avatar_url`;
definir por link baixa (`_baixar_link` isolado, com sessão HTTP fake) e
reposta; tipo fora da lista e tamanho acima do limite recusam com a
mensagem certa, tanto por anexo quanto por link; **URL ainda válida não
chama `fetch_message` nenhuma vez, URL vencida chama exatamente uma e
atualiza o cache** (`test_url_valida_nao_dispara_fetch_message` /
`test_url_vencida_dispara_refetch_e_atualiza_cache` — o teste que prova o
desenho inteiro, sem ele o caminho de refresh podia nunca ter sido
exercitado até os links vencerem em massa de verdade); `fetch_message`
levantando `NotFound` não derruba `rpg perfil` (embed sai sem thumbnail);
avatar sobrevive a `resetar_temporada()`; `rpg removeravatar` remove o
avatar de um jogador que não é quem chamou o comando.
`test_database_migracao.py` ganhou as duas colunas novas.

### Bug: "canal de arquivo indisponível" nos dois servidores — `CANAL_ARQUIVO_ID` lido antes do `load_dotenv()`

Sintoma reportado: `rpg avatar` com anexo recusava com "canal de arquivo
indisponível" nos dois servidores (jogo e o privado onde o canal mora),
mesmo com o ID certo e o bot presente no canal. Causa: `bot.py` importa
`avatar` na linha 14, mas só chama `load_dotenv()` na linha 33 — a primeira
versão de `avatar.py` lia `CANAL_ARQUIVO_ID = os.getenv(...)` pra uma
constante de módulo, na hora do `import`, ANTES da env var existir em
`os.environ`. `None` congelado pra sempre, em qualquer servidor, porque o
bug era de código, não de configuração — nenhum teste pegou porque a suíte
inteira roda sem nunca chamar `load_dotenv()` de verdade.

- **Correção adotada: ler a env var a cada chamada, não uma vez na
  importação** (`avatar._canal_arquivo_id()`, chamado de dentro de
  `_resolver_canal`/`diagnosticar_canal`) — opção deliberadamente mais
  robusta que só corrigir a ordem dos imports em `bot.py`: não importa a
  ordem de import mudar de novo no futuro, o valor nunca fica congelado
  errado. `import avatar` continua no topo de `bot.py` (precisa estar lá
  pra `perfil()` e `on_ready()` chamarem `avatar.obter_avatar_atualizado`/
  `avatar.diagnosticar_canal`), mas isso deixou de importar.
- **`get_channel` → `fetch_channel` como fallback** (`_resolver_canal`):
  canal recém-criado pode não estar no cache de guild do bot ainda —
  `get_channel` devolve `None` nesse caso, que não é o mesmo problema que
  "canal não existe" ou "sem permissão". Resultado cacheado em
  `_canal_cache` (estado de módulo) depois da primeira resolução — não
  bate na API de novo em toda mensagem.
- **Três mensagens de erro em vez de uma genérica** (`MENSAGENS_CANAL`,
  chaveado por `"sem_id"`/`"nao_encontrado"`/`"sem_permissao"`):
  `CANAL_ARQUIVO_ID` ausente, canal que não resolve nem por
  `fetch_channel` (ID errado ou bot fora do servidor), e
  `discord.Forbidden` na hora do `canal.send()` (bot no servidor e vendo o
  canal, mas sem permissão de Anexar Arquivos — só aparece nesse ponto, não
  antes). As três viravam a mesma frase antes; cada uma agora aponta pra
  uma correção diferente.
- **Diagnóstico no `on_ready`** (`avatar.diagnosticar_canal`, chamado em
  `bot.py` logo depois de `agenda.iniciar()`): loga o valor lido de
  `CANAL_ARQUIVO_ID` (ou "não configurado"), se resolveu do cache ou via
  `fetch_channel`, e a exceção específica quando nem isso resolve —
  responde "qual das causas é" só olhando o log depois de um restart, sem
  precisar reproduzir o erro em servidor de verdade pra descobrir.

Teste: `test_env_var_ausente_e_canal_nao_resolvido_geram_mensagens_diferentes`
confirma que as duas causas mais fáceis de confundir batem em mensagens
distintas; `test_bot_sem_permissao_de_anexar_gera_mensagem_propria` cobre a
terceira; `test_repostar_cai_pra_fetch_channel_quando_cache_esta_frio` prova
o fallback; três testes de `diagnosticar_canal` conferem o log de cada
ramo; `test_caminho_de_sucesso_continua_funcionando_com_o_resolver_novo`
é a regressão — confirma que nada quebrou no caminho feliz com o resolver
novo no lugar do `if CANAL_ARQUIVO_ID` antigo.

## Bug: HP final é congelado ao sair da luta, não CONGELADO por cima da cura

Aconteceu em produção: jogador entrou machucado num chefe, fugiu, tomou
poção **fora** da luta, e voltou a ficar com o HP baixo sozinho — a cura
parecia não ter acontecido.

Causa, em `turno_do_chefe()` (`combate.py`, fim de rodada):

```python
for c in self.participantes:
    c.defendendo = False
    c.acao = None
    c.salvar_estado()
```

O laço percorre `Luta.participantes` (a lista inteira, criada uma vez em
`Luta.__init__` e nunca encolhida), não `Luta.ativos`. Quem fugiu, saiu por
timeout ou caiu continua nessa lista pro resto da luta, com `Combatente.hp`
CONGELADO em memória no valor exato do momento da saída — nada mais muda
esse atributo depois disso. Toda vez que a luta segue rodando (porque ainda
sobra gente lutando) esse mesmo laço roda de novo e grava esse valor velho
por cima do que estiver no banco, desfazendo qualquer cura que tenha
acontecido fora da luta nesse meio-tempo. `on_timeout()` (quem some sem
clicar) tem o mesmo padrão, com o mesmo bug.

- **Correção: `Combatente.salvar_estado()` ganhou uma guarda própria**
  (`self._estado_final_salvo`, setado em `__init__`) em vez de trocar
  `participantes` por `ativos` só no laço de `turno_do_chefe()`. Motivo de
  não fazer a troca simples: existem outros pontos que chamam
  `salvar_estado()` — fuga (`fugir` callback), timeout (`on_timeout`), o
  golpe de iniciativa (`iniciar_luta`/`iniciar_raide`) — e cura por
  habilidade (Palavra de Alento) só persiste através desse mesmo laço de
  fim de rodada. Um `ativos` local ali resolvia só aquele um caminho; o
  próximo laço escrito em qualquer um desses outros pontos reintroduziria o
  mesmo bug. A guarda dentro do método garante a regra pra sempre, não
  importa de onde `salvar_estado()` é chamado.
- **A regra é: o estado de quem SAIU da luta é final — grava uma vez, no
  momento exato da saída, e nunca mais.** Enquanto `Combatente.ativo` for
  `True`, `salvar_estado()` continua gravando toda vez (comportamento de
  sempre, sem mudança pra quem segue lutando). No instante em que `ativo`
  vira `False` (fugiu/saiu/caiu), a PRÓXIMA chamada a `salvar_estado()`
  ainda escreve — é essa que captura o HP final de verdade (0 pra quem
  caiu, o HP com que fugiu ou sumiu) — e toda chamada depois dessa vira
  no-op.
- **`raide.py` não precisou de nenhuma mudança** — reusa `Combatente`/`Luta`
  de `combate.py` direto, então ganhou a correção de graça.

Teste (`tests/test_combate.py`): fuga com cura externa entre a fuga e a
rodada seguinte confirma que o valor de fora sobrevive; mesmo caso pra
timeout; quem caiu grava 0 uma vez e uma segunda chamada forçada não
regrava; quem continua lutando ainda tem HP/mana salvos toda rodada (não
regride). Validado revertendo a guarda de propósito antes de fechar o
cartão — os quatro testes relacionados quebram sem ela, confirmando que não
são falsos positivos.

## HP de chefe fixo acima do Selo (andar 11+)

`Luta.__init__` multiplicava `chefe["hp"]` pelo número de donos em QUALQUER
andar — decisão original, pensada pra chefe do 1 ao 10 (a torre principal,
onde puxar mais gente não pode ser estratégia de graça). Decisão explícita
do Rafael: **do andar 11 pra cima o HP do chefe passa a ser fixo, igual ao
solo, não importa quantos donos entraram.** Ele sabe que isso deixa a party
bem mais forte lá em cima e é exatamente o que quer — 11 a 15 é conteúdo de
grupo, roguelike, pensado pra ser enfrentado acompanhado.

- **O limiar reusa `ANDAR_ACIMA_DO_SELO` (10, `andares_altos.py`)** — já é a
  constante nomeada pra essa fronteira exata em todo o resto do arquivo
  (`recompensar()` já compara `luta.andar_num > ANDAR_ACIMA_DO_SELO` pra
  decidir a chance de material). Não criei uma constante nova tipo
  `LIMIAR_HP_FIXO = 11` — teria duplicado o mesmo número com um nome
  diferente, e as duas podiam divergir se o Selo um dia mudar de andar.
- **`SalaDeEspera.embed()` mentia pros andares altos** — anunciava
  "**{hp} HP por dono do andar**" pra qualquer andar, incluindo os que
  agora têm HP fixo. Virou `combate.texto_regra_hp_chefe(andar_num, chefe)`,
  função à parte (não só um `if` inline no embed) pra dar pra testar a
  frase sem montar `SalaDeEspera` inteira.
- **`raide.py` não muda.** Ele passa por esse mesmo `Luta.__init__`, mas com
  `andar_num=ANDAR_REFERENCIA_RAIDE` (7, `game_data.py` — só pra fórmulas de
  penetração/destreza, não desbloqueia nada) e `donos_ids=None` (todo mundo
  é dono, sempre). 7 nunca passa do limiar de 10, então a raide continua
  escalando por participante como sempre escalou — conferido com teste
  próprio, não só por leitura de código.
- **Recompensa e "dono do andar" não mudaram** — só a conta de HP. Drop,
  XP/moedas reduzidos pra ajuda, e a regra de quem é "dono" pra progressão
  continuam exatamente como estavam (pedido explícito do Rafael pra não
  mexer nisso).

Teste (`tests/test_combate.py`): andar 10 com 2 donos dobra o HP; andar 11
com 2 donos fica igual ao solo; o texto da sala de party muda de "por dono"
pra "fixo" cruzando o limiar; a raide (`ANDAR_REFERENCIA_RAIDE`) continua
escalando por participante. Validado revertendo a mudança de propósito
antes de fechar o cartão — o teste do andar 11 quebra sem ela.

## Salão da Guilda — tesouros de chefe e progressão de guilda

Duas metades de um pedido só: 10 tesouros novos (segundo drop, 100%, nos
chefes 1-10, ao lado do `fragmento_selo`) e o Salão, o eixo de progressão que
a guilda não tinha — hoje ela é idêntica no dia 1 e no mês 3.

- **Tier é contado por quantidade TOTAL de tesouros depositados, não
  distintos.** É a decisão que sustenta o desenho inteiro, travada em
  `tests/test_salao_guilda.py::test_tier_conta_total_nao_distintos`: 3 cópias
  do mesmo tesouro (3 membros que passaram do mesmo andar) valem o mesmo tier
  que 3 tesouros diferentes. Por distintos, um único jogador que chega ao
  andar 10 destrava tudo sozinho e a guilda vira carona de um carry; por
  total, largura de gente que avançou pesa mais que profundidade de herói
  solo — o oposto do que o ranking individual já premia. `COUNT(*)` em
  `guilda_salao` — uma LINHA por tesouro depositado, não um contador — dá o
  tier de graça e cada linha já carrega o crédito (`user_id`) sem precisar de
  duas fontes de verdade.
- **`vendavel: False` + `loja: False` nos 10 tesouros**, mesmo precedente do
  `fragmento_selo`. `tipo: "tesouro"` (tipo novo) já os exclui de
  equipar/craft/receita — nenhuma função por tipo (`equipar`, `RECEITAS`,
  `itens_da_loja`) precisou de exceção nova, só não incluir "tesouro" nas
  listas de tipos aceitos que já existiam.
- **Piso de 3+ membros gate o BENEFÍCIO, não o depósito.** Depositar sempre
  funciona (uma guilda de 2 pessoas ainda constrói crédito histórico); o que
  `salao.tier_efetivo()` faz é forçar tier 0 pra home/cooldown de raide
  quando `membros < MEMBROS_PARA_VALER`, mesmo com tesouro de sobra — mesmo
  raciocínio que já valia pra viagem grátis (`guildas.MEMBROS_PARA_VALER`).
  Sem isso o ótimo seria fundar guilda solo por 5.000 e ser o próprio Salão.
- **Migração sem retroagir (grandfather).** Guildas existentes têm home
  livre de 1 a 10 e tier 0 — aplicar o gate novo retroativamente rebaixaria
  quem já está lá, sem aviso. Nenhum código toca `andar_home` na subida do
  bot; o gate (`salao.tier_efetivo` dentro de `guildas.acao_home`) só entra
  na hora de TROCAR, que já é ato voluntário com cooldown de 3h. Existe
  precedente contrário no arquivo (migração 10, que puxou home acima do Selo
  de volta pro andar 1) mas aquilo corrigia estado JÁ inválido; aqui o estado
  é válido, só ganhou critério novo — não é o mesmo caso.
- **Contador de temporada novo: `estado_temporada` (linha única, `numero`).**
  Não existia nenhum jeito de saber "que temporada é essa" no banco antes
  desta carta — precisei criar um pra a coluna `temporada` de `guilda_salao`
  fazer sentido. `resetar_temporada()` só incrementa esse número (não apaga
  `guilda_salao`): toda leitura de tier filtra por
  `temporada = temporada_atual()`, então a contagem ativa volta a 0 sozinha
  assim que o número muda, e as linhas antigas ficam de pé pra
  `rpg guilda salao historico <n>`. "A mecânica reseta, a memória não."
- **Por que `resetar_temporada()` não precisa esvaziar `guilda_salao` na
  mão pra fechar o exploit de "guardar tesouro antes do reset e depositar
  depois":** `DELETE FROM inventario` já roda incondicionalmente dentro do
  mesmo reset (linha de sempre, não é coisa desta carta) — qualquer tesouro
  ainda não depositado na hora do reset é apagado junto com o resto da
  mochila. Não tem como um tesouro da temporada anterior sobreviver pra
  inflar o tier da temporada nova; o único jeito de um tesouro entrar em
  `guilda_salao` é `rpg guilda depositar` ANTES do reset (aí já é histórico
  da temporada velha) ou vencer o chefe DEPOIS do reset (temporada nova,
  legítimo). Verificado lendo `resetar_temporada()` antes de escrever
  qualquer coisa pra esta carta — não precisou de tratamento especial pro
  tipo `tesouro` dentro do `DELETE FROM inventario` porque ele já é
  incondicional (todo item, não só uns tipos).
- **`rpg guilda depositar` é reusado, não duplicado.** O mesmo comando que já
  deposita item no baú agora também recebe tesouro — `salao.extrair_tesouro()`
  casa o nome/chave do tesouro contra o INÍCIO do argumento (palavra por
  palavra, não por índice de string — nome acentuado muda de tamanho ao
  normalizar) e, se bater, desvia pro fluxo do Salão ANTES do parsing de
  quantidade do fluxo antigo. O resto do texto vira a assinatura opcional —
  não existe modal nem passo extra: a assinatura já entra junto do comando
  que abre a confirmação obrigatória (irreversível), e aparece na própria
  embed de confirmação pra revisão antes de clicar.
- **Confirmação por dependency injection.** `salao.depositar()` recebe a
  classe de confirmação (`admin.ConfirmarAcao`) por parâmetro em vez de
  importá-la no topo do módulo — evita prender `salao.py` a `admin.py` e,
  de brinde, deixa os testes passarem uma view fake sem precisar simular
  interaction/botão de Discord de verdade.
- **Sanitização em duas camadas.** Entrada: `@everyone`/`@here` (regex,
  case-insensitive) recusam o depósito com mensagem explicando o motivo —
  bloquear a inserção, não confiar só em não pingar depois. Saída: toda
  embed do Salão (confirmação e vitrine paginada) sai com
  `AllowedMentions.none()` — cinto e suspensório, porque o depósito não pode
  ser desfeito se algo escapar. `paginacao.enviar_paginado`/`PaginacaoView`
  ganharam um parâmetro `allowed_mentions` pra isso (default `None`, não
  muda nenhum call site existente).
- **Assinatura tem limite de 140 chars e é RECUSADA acima disso, nunca
  truncada em silêncio** — o jogador reformula, o Salão nunca mostra uma
  frase cortada no meio sem avisar.
- **Editar/apagar assinatura nunca muda `COUNT(*)`** — é update de uma coluna
  só (`mensagem`), sem tocar a linha em si. Autor edita a própria; líder só
  LIMPA a de qualquer membro (não pode escrever uma nova em nome de outro).
- **Cooldown de raide passou a ser lido do tier na hora de disparar** (
  `raide.iniciar_raide`, via `salao.tier_efetivo`) em vez do
  `COOLDOWN_RAIDE_SEGUNDOS` fixo de sempre — 2h nos tiers 0-1, 1h30 no 2, 1h
  no 3 (nunca menos, `game_data.SALAO_TIERS`). Calibrado pra não destravar
  a torneira de acessório da raide (800 moedas + 2 acessórios) rápido demais
  — ver o teto de 1h no cartão original, não apertar sem dado de uma
  temporada rodada.
- Testado em `tests/test_salao_guilda.py`: os 10 andares batendo 1:1 com o
  catálogo (sem lista escrita à mão — deriva de `ANDARES`), tesouro recusado
  em venda/equipar/receita, tier por total vs. distinto, piso de membros,
  depósito confirmado/cancelado/sem item, `@everyone`/`@here` recusados,
  assinatura longa recusada, editar/limpar sem mudar contagem, grandfather da
  home, home liberando por tier, cooldown de raide por tier, reset zerando
  ativo e preservando histórico com assinatura, vitrine com 36 tesouros
  assinados no limite não estourando embed.

### Bug — embed de vitória não anunciava o tesouro (nem qualquer drop novo)

Os tesouros entraram certo no inventário (`recompensar()` já rolava
`chefe["drops"]` inteiro, sem lacuna) mas o embed de "Recompensas" que o
jogador lê na hora tinha `🔷 Fragmento` **fixo, escrito na string**
(`combate.py:finalizar_vitoria`) — sobrou de quando `fragmento_selo` era o
único drop de chefe que existia. Mesmo formato do § Padrão — mapa de domínio
nunca é subscript direto, mais acima: código que cobria o que existia quando
foi escrito e ficou pra trás quando um drop novo (tesouro) foi semeado sem
ninguém voltar aqui. Achado testando `rpg boss` no andar 1 depois do Pacote
do Salão: a Coroa Velha chegou na mochila, a mensagem só falou em Fragmento.

- **Correção**: `recompensar()` agora devolve também `itens_dropados` (o que
  realmente foi sorteado/gravado pra aquele combatente, não o que *poderia*
  cair) — 5-tupla em vez de 4, único call site (`finalizar_vitoria`)
  atualizado junto. `finalizar_vitoria` monta a linha do dono a partir dessa
  lista, via `_texto_item_dropado()` (nome+emoji de `ITENS`, com `.get()` e
  fallback pra chave crua — chave já validada na autoria de
  `game_data.ANDARES`, mas um typo num drop novo agora vira texto degradado
  em vez de `KeyError` derrubando o embed de vitória inteiro). Item nenhum
  dropado (chance de repetição falhou, andar 11+) não escreve nada — a linha
  fica só com XP/moedas, sem sobrar texto de item nenhum.
- **Os dois mecanismos de drop de chefe são DIFERENTES de propósito, não bug
  duplicado**: andares 1-10 usam `H["rolar_drops"]` (cada entrada de
  `chefe["drops"]` rola a própria chance independente — `fragmento_selo` e o
  tesouro, os dois 100%) porque `andar == andar_max` nunca deixa refazer
  aquele chefe na mesma temporada (destranca o próximo andar pra sempre).
  Andares 11-15 usam o caminho de `chefes_derrotados` (100% na primeira
  vitória da conta, 15% nas repetições) porque ali É roguelike de propósito
  — dá pra refazer o mesmo chefe de novo (ver § Roguelike acima do Selo). Os
  10 tesouros **não** ganham a regra de 15%: eles não precisam, o gate de
  `andar_max` já os torna "uma vez só" sem precisar de desconto nenhum.
- **Nenhum outro lugar tinha a mesma lacuna.** `finalizar_vitoria` é chamado
  de um só ponto de produção (`combate.py`, fim de rodada) e serve solo E
  party ao mesmo tempo (mesmo motor `Luta`/`PainelLuta`) — não existe resumo
  separado, DM ou post de canal de guilda pra vitória de chefe. A única outra
  tela que anuncia drop de chefe é `raide.finalizar_vitoria_raide`, mas essa
  já monta o texto a partir do `random.sample()` de verdade (nunca teve texto
  fixo) — conferido, não precisou de correção.
- Testado em `tests/test_combate.py`: andar 1 e andar 10 (dois pontos
  diferentes da lista de `ANDARES`, não só o primeiro) mostrando os dois
  itens certos; andar 11 primeira vez mostrando o material; andar 11
  repetição COM sorte mencionando o item. Os 4 quebram revertendo só
  `combate.py` — confirmado antes de fechar o cartão.
- **Dois testes saíram depois, por não validarem nada**: um checava "andar 11
  repetição SEM sorte não menciona o item" e outro checava "ajudante nunca
  lista item" — os dois passavam mesmo com `combate.py` revertido pro bug,
  porque o texto antigo (`🔷 Fragmento` fixo) nunca citava "Sopro Contido" nem
  aparecia na linha do ajudante por acaso. Teste que passa igual com o bug
  presente não prova que a correção funciona — removidos a pedido do Rafael
  na revisão seguinte, não é esquecimento.

## Salão da Guilda — home reset (reversão da decisão anterior)

Pedido direto do Rafael (19/08/2026), sem diagnóstico prévio dele — fecha o
pacote do Salão. `resetar_temporada()` passa a devolver `andar_home` pro
andar 1 pra toda guilda, revertendo "Baú da guilda zera, a guilda sobrevive"
(mais acima neste arquivo), que dizia explicitamente que a home sobrevivia
intacta.

- **Por que reverter**: aquela decisão foi tomada antes do Salão existir. Com
  o Salão, manter a home intacta no reset cria exatamente a inconsistência
  que o "número a vigiar" do cartão original do Salão apontava — uma guilda
  entraria na temporada nova com home no andar 10 (o tier 3 da temporada
  ANTERIOR) sem ter nenhum tesouro depositado na temporada nova que
  justifique aquele tier. O Salão já zera (`estado_temporada.numero` avança);
  deixar a home destravada por cima do zero é a mesma armadilha, só que sem
  gate nenhum barrando.
- **O grandfather de `guildas.acao_home` não muda e não é o mesmo caso.** Ele
  cobre só a migração ÚNICA que introduziu o gate de tier pra guildas que já
  existiam antes do Salão — não é uma isenção que deveria se repetir a cada
  reset de temporada daqui pra frente. Depois deste cartão, toda guilda
  começa oficialmente a temporada em tier 0/home 1, e só sobe conforme
  deposita tesouro de novo — igual quem nunca teve Salão nenhum.
- **`guilda_home_cooldown` não é tocado no reset, de propósito.** Se uma
  guilda trocou de home pouco antes do reset e ainda tem cooldown de 3h
  rodando, o líder só espera vencer normal — não é um caso especial que
  precise de tratamento, e zerar o cooldown junto seria escopo que ninguém
  pediu.
- **`UPDATE guildas SET moedas = 0, andar_home = 1`** — uma linha só,
  acrescentada ao `UPDATE` que já existia pro caixa (não precisou de
  `UPDATE` separado nem de coluna nova).
- Testado em `tests/test_guilda_reset.py`: guilda com home 3 volta pro 1
  (mantendo membros e cargo intactos) e guilda com home 10 (caso mais
  realista de produção — tier alto conquistado antes do reset) também volta
  pro 1. Confirmado que os dois quebram revertendo só a cláusula
  `andar_home = 1` do `UPDATE` (sem mexer no resto do reset) — o resto da
  suíte (Salão, baú, membros) não se abala.
- **`admin.py`**: `PRESERVADO` perdeu a menção à home ("guilda em si...
  continua de pé" já não inclui mais home) e `GUILDA_RESET` ganhou linha
  própria explicando o motivo, separada da linha do Salão — são dois campos
  diferentes zerando pela mesma razão, não vale esconder um dentro do outro.

## Comunicação do Salão e dos tesouros — polimento, sem mudar mecânica

Salão e os 10 tesouros já estavam em produção (subiram 20/08); tier, cálculo
e taxa de drop continuam intactos. O pedido era só texto: `rpg guilda salao`
não explicava o que era a coisa pra quem via zerado, e o embed de vitória
anunciava o tesouro sem contexto nenhum de guilda.

### `rpg guilda salao` — três estados, não um texto fixo (`salao.py`)

- **Zero tesouros depositados**: `_texto_salao_vazio()` — bloco explicativo
  completo: o que é o tesouro (drop garantido do chefe 1-10, não vendável,
  não serve pra nada além do Salão), que o total é da guilda inteira, que o
  progresso é por temporada e zera no reset (mas o histórico sobrevive em
  `rpg guilda salao historico`), e que o Salão **não dá bônus de combate** —
  só home mais alta e cooldown de raide menor. Enviado como texto puro (via
  `mensagem_vazia` de `paginacao.enviar_paginado`, que já manda por
  `ctx.send` simples quando a lista de entradas está vazia — não precisou de
  embed novo).
- **1+ tesouros**: `_LINHA_CURTA` (uma linha, sem repetir o bloco todo) +
  `_descricao_progresso()` — tier atual, total, quanto falta pro próximo
  tier **e o que esse tier destrava de verdade** (andar máximo de home +
  cooldown de raide), lido direto de `SALAO_TIERS` em vez de só citar o
  nome do tier. `_fmt_cooldown()` novo (`salao.py`) formata segundos como
  "2h"/"1h30"/"1h" — sem depender de `H["fmt_tempo"]` (`bot.py`), porque
  `salao.py` não tem `H` (é módulo "sem instalar()", ver arquitetura.md).
- **Tier máximo**: `proximo_tier()` já devolve `None` nesse caso — `" Tier
  máximo — nada mais pra destravar aqui."` substitui o "Faltam X" em vez de
  concatenar em cima. Não precisou de ramo novo, só do `else` que já existia
  em `_descricao_progresso()`.
- Testado em `tests/test_salao_guilda.py`: os três estados (vazio explica,
  1+ mostra tier/total/faltam/o-que-destrava, máximo não mostra "Faltam") —
  asserções positivas sobre o texto, não só "não quebra" (os dois testes de
  vitrine que já existiam continuam, só ganharam vizinhos).

### Embed de vitória do chefe — contexto do tesouro (`combate.py`)

`finalizar_vitoria` já listava o nome do item dropado (bug antigo corrigido
antes, ver seção acima); faltava dizer o que fazer com ele quando é tesouro.

- **Com guilda**: `_texto_contexto_tesouro()` mostra uma PROJEÇÃO — "se você
  depositar isso, a guilda fica em X/Y pro tier N" — sem depositar nada de
  verdade (isso continua sendo `rpg guilda depositar`, ato manual). Lê
  `db.guilda_do_membro`/`db.contar_tesouros_salao` direto (funções que
  `combate.py` já tinha disponíveis via `db`, sem import novo) e computa o
  tier alvo com `_progresso_salao_previsto()`, uma cópia pequena e local da
  lógica de `salao.tier_por_total`/`proximo_tier` sobre `SALAO_TIERS` (dado
  puro de `game_data.py`, já importado). **Não chama `salao.py`** — ver nota
  de arquitetura abaixo. **Não menciona irreversibilidade** — esse aviso já
  existe em `salao.depositar()`, na hora do depósito de verdade; repetir
  aqui seria alarme falso pra um item que ainda nem saiu da mochila.
- **Sem guilda**: versão convite — que é tesouro de guilda, que vale
  guardar, como fundar (`rpg guilda criar`) ou entrar numa que já convidou
  (`rpg guilda convites` / `rpg guilda aceitar`). Sem número de progresso —
  não tem guilda pra progredir.
- **Nota de arquitetura**: `combate.py` lê guilda/Salão via `database.py`
  (que já importa) e via `SALAO_TIERS` de `game_data.py` (dado puro) — não
  importa `guildas.py` nem `salao.py`. Mesma regra que já vale pra
  `guildas.py` não depender de `bot.py`: combate/habilidades/profissões não
  dependem de módulo de feature. Custo: `_progresso_salao_previsto()`
  duplica ~5 linhas de `salao.tier_por_total`/`proximo_tier` — aceito de
  propósito, é mais barato que acoplar o motor de combate a um módulo de
  guilda pra uma projeção de 2 linhas.
- Testado em `tests/test_combate.py`: com guilda mostra "N/M" e tier certo
  e NÃO menciona "não pode ser desfeito"; sem guilda mostra convite
  (`rpg guilda criar`) e não mostra fração nenhuma (`/6` ausente).

## Status do item na compra (`comercio.py`)

Antes disso o jogador comprava às cegas: `_opcoes_compra` só mostrava nome e
preço, sem stat nenhum. Agora a `description` do `SelectOption` (linha única,
teto de 100 chars do Discord) mostra preço + stat + delta contra o que já
está equipado, por tipo de item — mesmo helper (`_texto_stat_e_delta`)
reaproveitado em `_opcoes_venda` (2.3 do pedido original: "mesmo buraco no
sentido inverso"), sem custar refatoração nenhuma.

- **Delta lê `H["stats"](j)["equipamento"]`, não `ITENS[j["arma"]]` cru** —
  esse dict já resolve o bônus da instância (melhoria +1/+2, joia do
  Joalheiro, encantamento do Encantador — ver decisoes.md § Instâncias de
  item), então o delta mostrado é contra o que a peça equipada RENDE de
  verdade, não contra o item base do catálogo.
- **Slot vazio → stat absoluto, nunca "+24 vs nada"**: `_par_equipado()`
  devolve `None` quando `s["equipamento"][tipo]` é `None`, e
  `_texto_stat_e_delta` trata "sem par" e "par sem delta comparável" (ver
  próximo item) do mesmo jeito — só o valor absoluto.
- **Acessório sem o mesmo atributo não gera delta**: comparar um anel de
  +4 FOR com um de +2 INT não informa nada, então `_delta_comparavel`
  devolve `None` nesse caso e cai no mesmo ramo do slot vazio (absoluto
  só). Delta de acessório só existe quando o item novo e o equipado têm o
  mesmo `atributo`.
- **Estouro de 100 chars trunca o NOME da peça equipada, nunca o preço, o
  stat ou o número do delta** — `_texto_stat_e_delta` calcula o espaço
  sobrando pro nome DEPOIS de reservar os números inteiros, e só corta ali
  (com `…`). Preço e stat nunca encolhem.
- **🔒 (requisito não cumprido) existe na formatação mas não dispara na
  prática hoje** — decisão consciente, perguntada direto ao Rafael: os dois
  call sites de `_opcoes_compra` (mercador, ferreiro) já filtram
  `disponiveis` por requisito ANTES de chegar na função (mercador por
  `andar_max`, ferreiro só vende do próprio andar — item ali sempre tem
  `andar_min == andar atual`, nunca trancado). Mudar esse pré-filtro pra
  mostrar prévia de tier futuro foi cogitado e recusado — Rafael escolheu
  manter o filtro como está e só deixar `_marca_indisponivel` correta pra
  quando/se isso mudar. `💸` (sem moeda) já dispara normalmente hoje, porque
  preço nunca foi filtrado.
- **Marca clicável, recusa de verdade no comando de texto por trás**: nem
  `💸` nem `🔒` bloqueiam o clique — quem clica cai no fluxo de sempre
  (`_pedir_quantidade_e_comprar` → `comprar()` de `bot.py` via `ShimCtx`),
  e a recusa de lá já ensinava a regra antes desse cartão (quanto falta de
  moeda, ou "só é forjado no andar N, manda `rpg viajar N`" pra equipamento
  fora de alcance) — não precisou de texto novo ali, só da marca visual no
  select.
- **`_opcoes_venda` ganhou o mesmo stat/delta**: vender uma peça mostra o
  que ela vale e quanto ela perde pro que já está equipado (delta negativo
  quando a peça na mochila é pior que a equipada) — mesma função,
  `unitario` (0.5× preço, ou preço cheio pra material) no lugar do preço de
  compra.
- Testado em `tests/test_comercio.py`: description por tipo (arma, armadura,
  poção, material, acessório com/sem mesmo atributo) com asserção positiva
  na string; slot vazio sem "vs"; sem moeda mostra `💸` E a recusa real
  ensina quanto falta; `🔒` disparando corretamente quando testado direto
  (fora do fluxo pré-filtrado); teto de 100 chars com o item de nome mais
  longo do catálogo, inclusive no pior caso (nome longo comparado contra
  peça equipada de nome longo); `_opcoes_venda` com o mesmo delta.

## A Guia vira menu + a corrente de pedidos do manto (andares 11-15)

Card do Notion "A Guia — diálogo, teleporte e sidequest da flor" fechou em
25/08 o texto das 8 falas (5 "O que me espera" + 3 "Sobre você") e a tabela
de pedidos/entregas por andar. Esta carta implementa isso — ela deixa de
teleportar sozinha ao abrir e vira um menu de 4 opções fixas (**Pedir para
voltar · O que me espera · Sobre você · Sair**), com um 5º botão condicional
quando há material suficiente pra entregar.

- **A Guia continua carta própria, fora de `dialogos.DIALOGOS`.** Ela nunca
  ganhou o campo `dialogo` (`npcs.py`) nem passou a usar
  `opcoes_do_dialogo`/`opcoes_por_estado` — o menu dela é uma
  `GuiaDialogoView` própria em `bot.py`, porque a lógica de pedido/entrega
  não cabe no contrato genérico de "opções soltas + estado antes/durante/
  depois" sem forçar os outros 27 NPCs a aprender sobre uma corrente de 4
  estágios que só ela tem. `test_so_guia_fica_de_fora_do_campo_dialogo`
  continua de pé sem mudança.
- **Quest_id por andar (`guia_flor`/`guia_farpas`/`guia_estilhacos`/
  `guia_cinzas`), não uma quest única com estado de etapa.** O card pedia
  pra avaliar isso: a tabela `sidequests(user_id, quest_id, estado)` já
  traduz `'ativa'/'concluida'` pra `'durante'/'depois'`
  (`db.estado_sidequest`) com um dicionário fixo de 2 chaves — inventar um
  terceiro vocabulário pra "qual estágio da corrente" quebraria esse
  tradutor ou exigiria estendê-lo pra todo NPC que o usa. Uma linha por
  andar deixa cada estágio caber exatamente no antes/ativa/concluída que já
  existe, e zero mudança em `database.estado_sidequest`.
- **"Ela cobra a anterior" = a corrente sempre processa o pedido mais
  antigo ainda aberto, não o do andar onde o jogador está fisicamente.**
  `andares_altos.pedido_pendente(user_id)` percorre `PEDIDOS` (11→12→13→14)
  e devolve o primeiro que não está `'depois'`. Um jogador pode subir de
  chefe em chefe sem nunca falar com ela num andar intermediário — ao
  encontrá-la em qualquer andar 11-15, o pedido em jogo continua sendo o
  mais antigo pendente, nunca o do andar atual. É isso que faz "chegar no
  13 sem ter passado pelo 12 não pula etapa" funcionar sem checagem
  especial nenhuma — é a mesma função pra todo andar.
- **`andares_altos.entregar_pedido(user_id)` nunca recebe qual pedido
  entregar por fora — ele recalcula a frente da fila sozinho.** Isso é o
  que torna impossível entregar fora de ordem mesmo com o material errado
  na mochila: `BotaoEntregarGuia` só chama a função com o `user_id`, ela
  decide. `db.remove_item` já garante que nada é consumido se a
  quantidade não bate, então "entregar sem ter o suficiente" não precisou
  de checagem redundante em `entregar_pedido`.
- **Entrega é um 5º botão condicional, não uma das 4 opções fixas.**
  Perguntei ao Rafael como a entrega deveria disparar já que o menu
  aprovado não tem opção "Entregar" — a resposta foi um botão extra que só
  aparece quando o jogador já carrega a quantidade pedida (`bot.py`,
  `GuiaDialogoView`/`BotaoEntregarGuia`). Os 4 fixos nunca mudam de
  quantidade nem de posição.
- **Conceder o pedido (`'antes' -> 'ativa'`) acontece sozinho, ao abrir
  `rpg falar guia`, não atrás de outro clique.** Mesmo raciocínio: não há
  botão "pedir" no menu aprovado, então o momento natural é a própria
  abertura da conversa — `andares_altos.conceder_pedido_pendente` roda
  antes de montar o embed, idempotente (só concede uma vez; visitas
  seguintes com o pedido já `'ativa'` não fazem nada de novo).
- **Texto de "novo pedido"/"entrega" é campo de embed (recibo), não fala
  dela.** Só os 8 textos aprovados (`FALA_O_QUE_ESPERA`, `FALA_SOBRE_VOCE`
  em `andares_altos.py`) são dela, palavra por palavra. O que acontece
  mecanicamente (o que ela pediu, o que foi trocado) aparece como campo
  factual do embed ("📜 Novo pedido"/"✅ Entregue"), no mesmo espírito de
  outros recibos do jogo (loot, custo de melhoria) — evita inventar falas
  novas pra ela fora do que foi aprovado.
- **A abertura da conversa reaproveita `n["fala"]` de `npcs.py` sem
  mudança** — são as 5 falas antigas (uma por andar), que já existiam como
  o "Escutar" tier-0 da versão anterior do design. Não inventei abertura
  nova: como o card só aprovou os 5+3 textos das respostas, e não um texto
  de saudação, reaproveitar o que já estava lá evita escrever conteúdo dela
  sem aprovação.
- **`FALA_O_QUE_ESPERA`/`FALA_SOBRE_VOCE` substituem `FALAS_GUIA` por
  inteiro** (a função antiga, `fala_da_guia(andar, mortes)`, misturava as
  duas coisas — cada andar variava por mortes, que era o design anterior).
  A fala periódica acima do Selo (`bot.py:falar_guia_acima_do_selo`, a cada
  `GUIA_A_CADA_ACOES` comandos) passou a chamar `o_que_espera(andar)` no
  lugar — mesmo papel de antes (comentário ambiente, não interativo), só
  que com o texto novo, fixo por andar.

### A flor do andar 1 — `rpg colher` + aviso na chegada

Perguntei ao Rafael como o jogador "encontra" a flor, já que o card só
falava em gatilho de horário sem especificar a interação. Resposta: um
comando dedicado (`rpg colher`) e um aviso quando o jogador entra no andar
1 durante a janela.

- **`npcs.flor_ativa()` é só um `carroca_ativa()` reaproveitado** — mesmos
  horários, mesma janela de 30 min, sem duplicar a lógica de agenda. Não
  há aviso no #torre (`agenda.py` nunca é tocado por isso) — só quem roda
  algum comando enquanto está no andar 1 na janela certa sabe.
- **`rpg colher` funciona em qualquer momento dentro da janela**, contanto
  que `andares_altos.pode_colher_flor(user_id)` seja verdade (pedido do
  andar 11 já concedido, ainda não entregue) e o jogador ainda não tenha a
  flor na mochila. Fora da janela, fora do andar 1, sem o pedido concedido,
  ou já com a flor em mãos: recusa sem efeito colateral.
- **`rpg viajar` pro andar 1 mostra um aviso** ("🌸 Na grama") quando chega
  durante a janela e a flor está disponível pra colher — descoberto ao
  entrar, não avisado de fora (mesmo espírito de "sem aviso no #torre": só
  quem está ali sabe). É só conveniência — `rpg colher` funciona igual sem
  o aviso ter aparecido, pra quem já estava parado no andar 1 quando a
  janela abriu sozinha.
- **A quest não é repetível**: `pode_colher_flor` fica falso pra sempre
  depois que a quest do andar 11 é concluída (`estado_sidequest` vira
  `'depois'`) — a flor nunca mais nasce pra aquele jogador, mesmo dentro de
  uma janela futura.

### Itens novos (`game_data.ITENS`)

`flor_do_andar_1` (pedido do andar 11) + `molde_do_manto`/`fio_do_manto`/
`forro_do_manto`/`fecho_do_manto` (entregues em 11/12/13/14). Todos
`tipo: "material"`, `vendavel: False`, `loja: False` — mesmo precedente do
`fragmento_selo`/tesouros de chefe: nada aqui vira moeda, craft ou loja.
As peças do manto não têm `def`/`atk`/bônus nenhum ainda — só ficam na
mochila até o cartão do manto em si (Manto de Luz/Sombra) dar uso a elas.
Os materiais dos andares 12-14 (`farpa_eletrica`/`estilhaco_gelido`/
`cinza_quente`) já existiam desde o Pacote 2 (drop comum de monstro) —
reaproveitados como pedido, sem criar item novo pra isso.

### Import circular evitado — `andares_altos.py` não importa `database` no topo

`database.py` já importa `ANDAR_ACIMA_DO_SELO` de `andares_altos.py`
(`from andares_altos import ANDAR_ACIMA_DO_SELO`, existia desde o Pacote 2).
Como `bot.py` importa `andares_altos` antes de `database`, um
`import database as db` no topo de `andares_altos.py` criaria um ciclo real
— `database.py` ficaria pausado dentro do próprio import, tentando ler
`ANDAR_ACIMA_DO_SELO` de um `andares_altos` que ainda não tinha executado
até aquela linha. Corrigido com `import database as db` **dentro** de cada
função de `andares_altos.py` que precisa dele (`pedido_pendente`,
`conceder_pedido_pendente`, `entregar_pedido`) — import lazy, resolve sem
reordenar nada em `bot.py` nem duplicar a constante. Confirmado com
`python -c "import bot"` limpo antes de escrever qualquer teste.

Testado em `tests/test_guia_manto.py`: as 5 falas fixas de "O que me
espera" e a escala de "Sobre você" nas 3 faixas (revelação só em 7+); a
corrente concede na ordem certa e nunca pula etapa (material do andar 13 na
mochila não adianta nada se o pedido pendente ainda é o do 11); entrega sem
quantidade completa não consome nada; entrega concede exatamente 1 peça e
consome exatamente a quantidade pedida; a corrente completa (11→14) entrega
as 4 peças na ordem; quest concluída nunca mais libera a flor; morte acima
do Selo reseta andar/andar_max sem apagar peça nem progresso de quest; o
menu de `rpg falar guia` mostra os 4 botões fixos e só ganha o 5º quando há
material suficiente; `rpg colher` respeita janela/andar/elegibilidade.
Validado revertendo a mudança (`git stash`) e confirmando que só os 21
testes novos quebram, nada mais na suíte (311 → 332 depois).

### Aviso da flor também em `rpg cacar`/`rpg explorar` + botão "Sobre o pedido"

Carta pequena em cima da anterior: o aviso da flor só saía na chegada do
`rpg viajar 1` — quem já estava parado no andar 1 farmando quando a janela
abria não via nada. E o menu não tinha como reler o pedido em aberto.

- **`aviso_flor_do_andar_1(user_id, andar_atual)` (`bot.py`) é a mesma
  checagem extraída da chegada de `rpg viajar`**, agora chamada nos três
  lugares onde o jogador pode estar parado no andar 1 quando a janela abre:
  `rpg viajar` (chegada), `rpg cacar` e `rpg explorar` (ação parada ali).
  Um helper só, não a mesma condição copiada três vezes — os três chamam
  logo antes do `ctx.send(embed=e)` final, dentro do `if`/`else` de vitória/
  derrota (o aviso não depende de ganhar ou perder a caçada).
- **Continua sem gatilho por entrada de andar via `after_invoke`** — cada
  comando checa sozinho no momento em que já ia mandar a mensagem, mesmo
  padrão de antes. Quem não estiver no andar 1 na janela continua perdendo,
  de propósito (igual já valia pra `rpg viajar`).
- **"Sobre o pedido" é um botão condicional a mais no menu da Guia**
  (`BotaoSobreOPedidoGuia`, `bot.py`) — aparece quando
  `andares_altos.pedido_pendente()` devolve algum pedido (independente de
  já dar pra entregar ou não) e some sozinho quando a corrente termina.
  Mostra a fala aprovada do pedido (`andares_altos.FALA_PEDIDO`/
  `fala_do_pedido`, um texto por `quest_id`, separado de
  `FALA_O_QUE_ESPERA`/`FALA_SOBRE_VOCE` porque varia por PEDIDO, não por
  andar nem por mortes) e o progresso `tem/precisa` no rodapé do embed.
- **O progresso é lido no clique, não guardado no momento em que o menu foi
  montado.** `db.qtd_item(user_id, item)` (nova, ao lado de `tem_item` —
  esta devolve o número exato, não só o booleano de "tem o bastante")
  é chamada dentro do `callback` do botão, então farmar mais material
  enquanto a conversa está aberta na tela já reflete no clique seguinte.
- Testado em `tests/test_guia_manto.py`: `rpg cacar`/`rpg explorar` avisam
  no andar 1 com janela aberta e pedido da flor em aberto, e não avisam sem
  janela, sem pedido, ou fora do andar 1; as 4 falas de pedido batem com o
  texto aprovado; "Sobre o pedido" ausente sem pedido em aberto e depois da
  corrente completa; o botão mostra fala + progresso certo, e o progresso
  reflete item adicionado à mochila DEPOIS do menu já montado (prova que lê
  na hora do clique, não no momento em que a view foi criada). Validado
  revertendo só os arquivos de implementação (`andares_altos.py`, `bot.py`,
  `database.py`) via `git stash` e mantendo os testes no lugar: 8 dos 30
  testes do arquivo quebram (os que afirmam o comportamento novo — os
  outros 22 continuam passando porque também seriam verdade sem a
  mudança, ex. "não avisa sem a janela aberta").