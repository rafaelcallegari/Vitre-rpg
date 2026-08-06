# Decisões de design — Vitre RPG

Registro do que já foi decidido, com o motivo. O que está em **pendente** foi
decidido mas ainda não existe no código.

## Rebalanceamento da defesa — feito

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
 com dar função real à DES. Ver "Verificar antes de implementar" abaixo,
 que segue valendo pro próximo passo.

Ainda em aberto pro próximo passo: **o level up ainda cura 100%?** (Não —
cura 50% do HP máximo novo, `CURA_LEVEL_UP` em `atributos.py`. Já era assim
antes deste commit.) Falta calibrar HP-por-CON e esquiva de DES junto com as
classes, como já estava planejado.

## Consumíveis na luta de chefe — feito

O limite de 3 poções por luta (`MAX_POCOES`) passou a valer só pra poção
comum (`pocao_p/m/g`, cura fixa). Elixir de Alquimia (`elixir_ervas`,
`elixir_vermelho`, `nectar_torre` — cura por porcentagem) ganhou contador
próprio, `MAX_ELIXIRES = 1`, em `combate.py`. Os dois contadores são
independentes: dá pra usar 3 poções **e** 1 elixir na mesma luta. Distinção é
por `"cura_pct" in ITENS[chave]` (`eh_elixir`), não por lista de nomes —
qualquer receita de Alquimia futura já cai automaticamente no contador de
elixir.

## Sistema de títulos — feito

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

## Classes e habilidades — infraestrutura feita, catálogo pendente

Este commit deixou tudo pronto pra receber skills, mas **nenhuma skill existe
ainda** — `game_data.HABILIDADES = {}`. É de propósito: calibrar dano, mana e
duração de condição sem ter uma skill de verdade pra testar é achismo. O
próximo passo é lançar a primeira e ajustar o motor em cima dela, não inventar
os 12 números de uma vez.

O que já está no ar:
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

Em aberto pra quando a primeira leva de skills entrar:
- O Ar não tem classe dona (decisão antiga, ver ideia original abaixo).
 Guerreiro não tem elemento — vira a classe de efeito físico puro
 (sangramento, quebra de armadura, o próprio Provocar).
- O Batedor de Carteira (ramo do Ladino) rouba de quem? Roubo entre
 jogadores em servidor de amigos é risco social, não só de balanceamento.
- Custo de mana por skill (referência antiga: 12 a 18, ~3 usos por luta de
 ~15 rodadas) e o que cada uma faz além de dano — segue valendo, não foi
 decidido ainda porque nenhuma skill existe pra testar contra os chefes de
 verdade.
- Tag elemental nos 10 chefes — só vale a pena cadastrar quando souber quais
 elementos as primeiras skills realmente usam.

## Profissões e craft — em andamento, bloqueado

- **Cada jogador escolhe uma única profissão** entre Minerador, Forjador,
 Alquimista, Joalheiro e Arcanista.
- Isso torna o craft **dependente de trade entre jogadores**, que está em Baixa
 no Kanban e não existe. Sem trade, Minerador acumula material que não usa e
 Forjador fica sem insumo. **Trade sobe para Alta quando o craft voltar.**
- Arcanista fica com encantamento (melhora equipamento pronto). Junto com o
 Joalheiro, vira a camada final de progressão defensiva — o que faz sentido
 agora que defesa só vem de equipamento.
- Em aberto: Minerador precisa de um loop próprio (`rpg minerar` com cooldown,
 competindo com caçar e explorar) ou só melhora drop de material no combate que
 já existe? A segunda é bem mais barata.

## Taverna — pendente, cuidado

Está em Alta no Kanban, mas mistura três escopos: cura, party/guild, e base da
guild com viagem grátis. Party já existe.

A **cura da taverna seria a quarta rede de segurança** (junto com cura no level
up, regeneração por tempo e 3 poções por luta) e a mais forte, porque é sob
demanda. Se entrar grátis, desfaz o rebalanceamento inteiro. Entra cobrando
moeda e funcionando só no andar onde a taverna está.

## Ordem de trabalho acordada

1. Skills/classes/mana (dá função ao INT e conteúdo aos veteranos) — a
   infraestrutura já está no ar; falta a primeira leva de skills de verdade
2. Slots de anel e colar (o Joalheiro precisa fabricar alguma coisa)
3. Terminar craft + trade
4. Taverna, quebrada em cartões separados

O rebalanceamento da defesa é mudança de fórmula e anda em paralelo — não
bloqueia nenhum desses.