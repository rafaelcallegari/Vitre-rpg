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

## Classes e habilidades — pendente, prioridade atual

- **Habilidade só na luta de chefe.** Caçada continua instantânea. Consequência
 aceita: o chefe é o gate de progressão, então INT vira o atributo de avançar e
 FOR/CON os de farmar.
- **INT dá mana para todo mundo**; o dano da habilidade escala com o atributo da
 classe (Guerreiro FOR, Ladino DES, Mago e Orador INT). Assim nenhuma build
 pode zerar INT.
- **Classe é escolha travada**, igual à profissão.
- **Lançar as 4 bases; os 3 ramos de cada uma são os ascendentes**, liberados por
 nível. 12 habilidades no lançamento em vez de 36.

| Base | Ramos (ascendentes) |
|---|---|
| Mago | Mago de Gelo, Mago de Fogo, Mago de Raio |
| Guerreiro | Soldado, Mercenário, Espadachim |
| Ladino | Assassino, Batedor de Carteira, Arqueiro |
| Orador | Monge, Clérigo, Paladino |

Elementos: fogo, gelo, ar, raio, divino, sombrio.
- Elemento é **efeito de status**, não tabela de resistência: fogo queima, gelo
 tira turno, raio atordoa, sombrio drena, divino cura/blinda, ar dá iniciativa.
- Como habilidade só existe contra chefe, **só os 10 chefes** precisam de tag
 elemental.
- Em aberto: o Ar não tem classe dona. Guerreiro não tem elemento — a ideia é ele
 ser a classe de efeito físico puro (sangramento, quebra de armadura, provocar).
- Em aberto: o Batedor de Carteira rouba de quem? Roubo entre jogadores em
 servidor de amigos é risco social, não só de balanceamento.

Mana:
- Volta por **tempo e por poção**.
- A regeneração precisa ser **mais lenta que o cooldown de 15 min do chefe**
 (referência: 1 de mana por minuto). Se encher mais rápido, a poção de mana
 nasce morta — e ela é o produto do Alquimista.
- Mana máxima parece ser `20 + 5 * INT` (perfil com INT 6 mostrava 50). Confirmar
 no código.
- Custo de 12 a 18 por habilidade dá ~3 usos por luta. Com luta de ~15 rodadas,
 a habilidade precisa valer ~3 ataques normais para INT competir com FOR — e
 por isso não pode ser só dano: tem que fazer o que FOR não faz (anular
 penetração de armadura por um turno, curar sem gastar poção, dobrar o crítico
 da rodada seguinte).

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

1. Skills/classes/mana (dá função ao INT e conteúdo aos veteranos)
2. Slots de anel e colar (o Joalheiro precisa fabricar alguma coisa)
3. Terminar craft + trade
4. Taverna, quebrada em cartões separados

O rebalanceamento da defesa é mudança de fórmula e anda em paralelo — não
bloqueia nenhum desses.