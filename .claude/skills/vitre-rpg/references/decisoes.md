# Decisões de design — Vitre RPG

Registro do que já foi decidido, com o motivo. O que está em **pendente** foi
decidido mas ainda não existe no código.

## Rebalanceamento da defesa — pendente

Contexto: dois jogadores terminaram o andar 10 sem usar as armas de selo e sem
correr risco de morrer. O objetivo é a torre inteira ficar mais dura, do andar 1
em diante. A penalidade de morte atual está boa — morrer deve **acontecer** mais,
não **doer** mais.

Diagnóstico: CON dava HP e aparagem ao mesmo tempo, e a aparagem é multiplicativa
e sem teto. Uma build de 29 CON tinha 540 de HP e 57% aparado — ~1.256 de HP
efetivo. Subir o ataque dos monstros só tornaria CON mais obrigatório.

Decisões:
- **CON dá só HP.** Defesa passa a vir exclusivamente de equipamento.
- **Aparagem relativa ao andar**, para armadura antiga envelhecer sozinha:
 `aparagem = def / (def + 50 + 15 * andar)`.
- **Migração obrigatória**: devolver os pontos de atributo ou dar um respec
 grátis, senão o nerf é retroativo e silencioso.
- Compensar CON com mais HP por ponto, e dar função real à DES (esquiva de
 verdade, com teto). Calibrar isso **junto com as classes**, não antes.

Verificar antes de implementar: **o level up ainda cura 100%?** Se sim, ele é a
causa provável de ninguém morrer, mais que a defesa.

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