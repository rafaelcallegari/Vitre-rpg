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
     `registrar_acao` → `fim_da_luta` → `encerrar`), incluindo o caso de
     `encerrar_sem_donos` (raide/party sem quem convocou).
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
 seguia: estado de guilda não é zerado no reset de temporada de jogador,
 só progresso individual (inventário, cooldown pessoal, upgrades, chefes
 derrotados).
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
- **Achado no caminho, não mexido**: `bot.py` ainda tem um `@bot.command(name="boss", ...)`
 inteiro (resolução instantânea, motor de `simular_combate`, o mesmo de
 `cacar`/`explorar`) que faz sua própria conta de `novo_andar`/XP/drop e
 também cita "Décimo Selo". É código morto — `combate.instalar()` chama
 `bot.remove_command("boss")` antes de registrar o `boss` de verdade (por
 turnos), então esse daqui nunca roda. Não tem risco funcional (nunca é
 chamado, não precisou de reset roguelike nele), mas é lixo que vale uma
 limpeza separada — não mexi de novo porque não foi pedido e não faz
 diferença nenhuma rodando.

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