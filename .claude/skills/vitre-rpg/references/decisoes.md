# Decisões de design — Vitre RPG

Registro do que já foi decidido, com o motivo — o porquê por trás de cada
escolha, não o status de implementação. Progresso, prioridade e o que ainda
está em aberto vivem no Kanban Vitre, no Notion.

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
 inflar o chefe, é ajuda pura. Recompensa do veterano (XP e moedas, não
 HP) cai com `fator_recompensa_ajuda`: `1.0` se `andar_max - andar_chefe
 <= 0`, senão `max(0.10, 1 - 0.25*diff)` — nunca some de vez, só fica
 pouco atrativo repetir muitas vezes num andar muito abaixo do próprio.
 Drop de item do chefe e progressão de `andar`/`andar_max` são só pra
 dono; pra quem ajudou, `recompensar()` grava de volta os mesmos valores
 que a pessoa já tinha — ela não se move na torre por ter ajudado.
- **Se todos os donos caírem ou saírem e sobrar só ajuda, a luta encerra
 sem vitória** (`Luta.donos_ativos`, checado em `PainelLuta.fim_da_luta`
 *antes* de checar `hp_chefe <= 0` ou `not luta.ativos` — assim um
 veterano não pode fechar o chefe sozinho depois que o dono cai, mesmo que
 o hit que zera o HP seja dele). `encerrar_sem_donos()` ainda cobra a
 penalidade normal de morte de qualquer dono que tenha caído antes disso.
 Não precisou mexer em `raide.py`: lá `donos_ativos == ativos` sempre (todo
 mundo é dono por padrão), então essa checagem nunca dispara nela.
- **Cooldown de chefe (15 min) já era consumido por todo `combatente` em
 `iniciar_luta`, sem distinção** — não precisou de mudança nenhuma pra
 valer também pra quem entra só de ajuda. Fugir continua sem queimar
 (`encerrar_por_abandono` só reseta cooldown de quem `fugiu`); sumir por
 timeout continua queimando — nenhum dos dois foi tocado.

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