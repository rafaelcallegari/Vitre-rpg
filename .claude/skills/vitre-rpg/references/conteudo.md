# Conteúdo — Vitre RPG

Andares, itens, NPCs e receitas tirados direto de `game_data.py`, `npcs.py` e
`profissoes.py`. Conteúdo original — a torre é inspirada em SAO, mas nenhum
nome de monstro, chefe ou NPC vem do anime.

## A torre — 10 andares

Equipamento só é vendido nos andares **ímpares** (1, 3, 5, 7, 9), pelo
ferreiro daquele andar. Poção é vendida em qualquer andar já destrancado.

| # | Nome | Descrição |
|---|---|---|
| 1 | Planície dos Iniciantes | Grama alta até o joelho e o céu de pedra do andar de cima. Todo mundo começa aqui. |
| 2 | Bosque Sussurrante | As árvores repetem, com meio segundo de atraso, tudo o que você fala. |
| 3 | Ruínas Afundadas | Uma cidade inteira submersa até a metade. Alguma coisa ainda anda lá embaixo. |
| 4 | Deserto de Sal | Branco até onde a vista alcança. O chão range quando você pisa. |
| 5 | Lago Congelado | O gelo é grosso o bastante pra andar e fino o bastante pra ouvir. |
| 6 | Mina Abandonada | As lamparinas ainda estão acesas. Ninguém apagou porque ninguém saiu. |
| 7 | Campos de Cinzas | Não chove aqui. Cai cinza, e ela é quente. |
| 8 | Catedral Quebrada | O teto sumiu, os bancos continuam ocupados. |
| 9 | Céu Partido | O andar acabou e vira ponte. Não olhe pra baixo — não tem baixo. |
| 10 | Salão do Selo | Dez portas atrás de você. Uma na frente. Nenhuma janela. |

### Monstros de caçada/exploração (3 por andar, sorteio uniforme)

| Andar | Monstro | HP | ATK | DEF | XP | 🪙 | Drop (chance) |
|---|---|---|---|---|---|---|---|
| 1 | Javali das Planícies | 42 | 8 | 1 | 18 | 26 | Presa de Javali 55% |
| 1 | Lobo da Névoa | 38 | 9 | 1 | 19 | 24 | Presa de Javali 45% |
| 1 | Slime Azulado | 52 | 6 | 2 | 17 | 28 | Presa de Javali 60% |
| 2 | Aranha Tecelã | 72 | 13 | 3 | 32 | 45 | Seda Sussurrante 55% |
| 2 | Cogumelo Andante | 82 | 11 | 4 | 30 | 48 | Seda Sussurrante 50% |
| 2 | Corvo de Ferro | 62 | 15 | 2 | 34 | 42 | Seda Sussurrante 45% |
| 3 | Esqueleto Enferrujado | 102 | 18 | 5 | 46 | 65 | Osso Enferrujado 55% |
| 3 | Rato Colossal | 92 | 20 | 4 | 48 | 62 | Osso Enferrujado 50% |
| 3 | Lodo Ácido | 115 | 16 | 6 | 44 | 68 | Osso Enferrujado 45% |
| 4 | Escorpião de Cristal | 132 | 23 | 7 | 60 | 85 | Cristal de Sal 55% |
| 4 | Bandido Errante | 122 | 26 | 6 | 62 | 90 | Cristal de Sal 45% |
| 4 | Verme das Dunas | 145 | 21 | 8 | 58 | 82 | Cristal de Sal 50% |
| 5 | Lobo de Gelo | 162 | 28 | 9 | 74 | 105 | Núcleo Gelado 55% |
| 5 | Espírito da Neblina | 148 | 32 | 7 | 78 | 100 | Núcleo Gelado 45% |
| 5 | Urso Corrompido | 180 | 26 | 11 | 72 | 110 | Núcleo Gelado 50% |
| 6 | Golem de Minério | 205 | 31 | 13 | 88 | 125 | Minério Negro 55% |
| 6 | Morcego Sanguinário | 175 | 36 | 9 | 92 | 120 | Minério Negro 45% |
| 6 | Mineiro Enlouquecido | 190 | 34 | 11 | 90 | 130 | Minério Negro 50% |
| 7 | Cavaleiro Queimado | 232 | 38 | 14 | 102 | 145 | Brasa Eterna 55% |
| 7 | Elemental de Brasa | 210 | 43 | 11 | 106 | 140 | Brasa Eterna 45% |
| 7 | Abutre de Ferro | 220 | 40 | 13 | 104 | 150 | Brasa Eterna 50% |
| 8 | Estátua Animada | 265 | 42 | 17 | 116 | 165 | Fragmento de Sino 55% |
| 8 | Monge Silente | 240 | 47 | 14 | 120 | 160 | Fragmento de Sino 45% |
| 8 | Sino Amaldiçoado | 280 | 40 | 18 | 114 | 172 | Fragmento de Sino 50% |
| 9 | Harpia Tempestade | 292 | 48 | 18 | 130 | 185 | Pena do Trovão 55% |
| 9 | Dragão Jovem | 320 | 45 | 21 | 128 | 195 | Pena do Trovão 45% |
| 9 | Sentinela Alada | 275 | 52 | 16 | 134 | 180 | Pena do Trovão 50% |
| 10 | Cavaleiro Espelhado | 325 | 53 | 20 | 144 | 205 | Eco Cristalizado 55% |
| 10 | Eco do Jogador | 300 | 58 | 18 | 148 | 200 | Eco Cristalizado 45% |
| 10 | Guardião do Selo | 350 | 50 | 23 | 142 | 215 | Eco Cristalizado 50% |

### Chefes (luta por turnos, `rpg boss` ou `rpg party`)

Todo chefe dropa `Fragmento do Selo` com 100% de chance — é o material das
receitas de nível 9 (armas e manto de selo).

| Andar | Chefe | HP (por jogador) | ATK | DEF | XP | 🪙 |
|---|---|---|---|---|---|---|
| 1 | «Vargash, o Kobold Coroado» | 165 | 13 | 2 | 150 | 260 |
| 2 | «Aracnia, a Rainha dos Fios» | 285 | 21 | 5 | 260 | 450 |
| 3 | «Guardião de Pedra Rachada» | 410 | 29 | 8 | 380 | 650 |
| 4 | «Zarhak, o Verme Ancião» | 530 | 37 | 11 | 500 | 850 |
| 5 | «Nivalgar, o Uivo Branco» | 650 | 45 | 14 | 620 | 1050 |
| 6 | «Núcleo Vivo da Mina» | 770 | 53 | 17 | 740 | 1250 |
| 7 | «Ignar, o Cavaleiro de Brasas» | 890 | 61 | 20 | 860 | 1450 |
| 8 | «Coro dos Sem Rosto» | 1010 | 69 | 23 | 980 | 1650 |
| 9 | «Vyrra, a Serpente do Trovão» | 1130 | 77 | 26 | 1100 | 1850 |
| 10 | «O Arquiteto do Décimo Selo» | 1260 | 85 | 29 | 1220 | 2050 |

### Tesouros de chefe (andares 1-10) e o Salão da Guilda

Cada chefe 1-10 solta um tesouro (100%, `tipo: "tesouro"`, não vendável, não
craftável, não equipável), ao lado do `fragmento_selo`, um por andar. Não é
farmável — `rpg boss` só vale em `andar == andar_max`, então cada jogador
enfrenta cada chefe uma vez só (por temporada).

| Andar | Chefe | Tesouro |
|---|---|---|
| 1 | «Vargash, o Kobold Coroado» | 👑 Coroa Velha |
| 2 | «Aracnia, a Rainha dos Fios» | 🧶 Novelo da Rainha |
| 3 | «Guardião de Pedra Rachada» | 🪨 Lasca do Guardião |
| 4 | «Zarhak, o Verme Ancião» | 🦷 Presa de Zarhak |
| 5 | «Nivalgar, o Uivo Branco» | ❄️ Uivo Congelado |
| 6 | «Núcleo Vivo da Mina» | 🫀 Batida do Núcleo |
| 7 | «Ignar, o Cavaleiro de Brasas» | ⛑️ Elmo de Ignar |
| 8 | «Coro dos Sem Rosto» | 🔕 Sino Sem Badalo |
| 9 | «Vyrra, a Serpente do Trovão» | 🐍 Escama de Vyrra |
| 10 | «O Arquiteto do Décimo Selo» | 🔨 Martelo do Arquiteto |

`rpg guilda depositar <tesouro> [assinatura]` crava o tesouro no Salão —
irreversível, com confirmação. O tier da guilda é a quantidade TOTAL de
tesouros depositados na temporada ativa (não distintos — ver decisoes.md §
Salão da Guilda), com piso de `MEMBROS_PARA_VALER` (3) membros pro benefício
valer:

| Tier | Tesouros | Home liberada | Cooldown da raide |
|---|---|---|---|
| 0 — Salão Vazio | 0 | andares 1-3 | 2h |
| 1 — Salão Erguido | 6 | andares 1-5 | 2h |
| 2 — Salão Guarnecido | 18 | andares 1-8 | 1h30 |
| 3 — Salão Coroado | 36 | andares 1-10 | 1h |

`rpg guilda salao` mostra tier/progresso/quem entregou cada um (paginado);
`rpg guilda salao historico [temporada]` arquiva temporadas passadas —
`resetar_temporada` zera o tier ativo (avança o contador de temporada) mas
nunca apaga as linhas antigas.

## Itens

### Consumíveis (loja, todo andar já destrancado)

| Item | Preço 🪙 | Cura | Andar mín. |
|---|---|---|---|
| 🧪 Poção Pequena | 60 | 60 fixo | 1 |
| ⚗️ Poção Média | 220 | 200 fixo | 3 |
| 🍶 Poção Grande | 700 | 600 fixo | 6 |

### Armas de Força (dano alto, crítico 10%)

| Item | Preço 🪙 | ATK | Andar mín. | Loja? |
|---|---|---|---|---|
| 🗡️ Espada de Ferro | 280 | 8 | 1 | sim |
| ⚔️ Espada de Aço | 1100 | 20 | 3 | sim |
| ❄️ «Lâmina de Gelo» | 3200 | 36 | 5 | sim |
| 🔥 «Espada de Brasas» | 7500 | 55 | 7 | sim |
| 🌑 «Lâmina do Selo» | 16000 | 82 | 9 | **não — só craft** |

### Armas de Destreza (75% do dano equivalente, crítico 18%)

| Item | Preço 🪙 | ATK | Andar mín. | Loja? |
|---|---|---|---|---|
| 🔪 Adaga | 260 | 6 | 1 | sim |
| 🏹 Arco Curto | 1000 | 15 | 3 | sim |
| 🌫️ «Foice de Bruma» | 2900 | 27 | 5 | sim |
| 🎯 «Arco de Cinzas» | 6800 | 41 | 7 | sim |
| 🌒 «Adaga do Selo» | 14500 | 61 | 9 | **não — só craft** |

### Armaduras (loja, um ferreiro por andar ímpar)

| Item | Preço 🪙 | DEF | Andar mín. |
|---|---|---|---|
| 🥋 Armadura de Couro | 220 | 5 | 1 |
| 🛡️ Cota de Malha | 900 | 12 | 3 |
| 🪖 Armadura de Placas | 2800 | 22 | 5 |
| 🌋 «Placa de Obsidiana» | 6800 | 36 | 7 |
| 🧿 «Manto do Selo» | 15000 | 54 | 9 (só craft) |

### Armaduras forjadas (só craft — Forja)

| Item | Preço-base 🪙 | DEF | Andar mín. |
|---|---|---|---|
| 🥾 «Couro Batido» | 700 | 8 | 1 |
| ⛓️ «Malha Reforçada» | 2400 | 17 | 3 |
| 🔩 «Placas Polidas» | 5200 | 29 | 5 |
| 🜃 «Couraça de Cinzas» | 11000 | 45 | 7 |

### Alquimia (só craft — cura por porcentagem do HP máximo)

| Item | Preço-base 🪙 | Cura | Andar mín. |
|---|---|---|---|
| 🌿 «Elixir de Ervas» | 200 | 25% | 1 |
| 🍷 «Elixir Vermelho» | 900 | 50% | 4 |
| 🍯 «Néctar da Torre» | 2600 | 100% | 7 |

### Materiais (drop de monstro, só pra vender ou craftar)

| Item | Preço 🪙 | Andar de origem |
|---|---|---|
| 🦷 Presa de Javali | 12 | 1 |
| 🕸️ Seda Sussurrante | 30 | 2 |
| 🦴 Osso Enferrujado | 55 | 3 |
| 🧂 Cristal de Sal | 85 | 4 |
| 🧊 Núcleo Gelado | 120 | 5 |
| 🪨 Minério Negro | 160 | 6 |
| 🔥 Brasa Eterna | 210 | 7 |
| 🔔 Fragmento de Sino | 265 | 8 |
| ⚡ Pena do Trovão | 330 | 9 |
| 💠 Eco Cristalizado | 400 | 10 |
| 🔷 Fragmento do Selo | 500 | drop de qualquer chefe, **não vendável** |

### Materiais de Encantador (ímpares) e Joalheiro (pares)

Mesma escada de preço dos materiais de chão acima — dropam junto deles em
`rpg cacar`/`rpg explorar` (mesmo monstro, mesma chance, segunda entrada em
`drops`). Ver `balanceamento.md` pra quanto de cada um uma ação de
Encantador/Joalheiro consome.

| Item | Preço 🪙 | Andar | Ofício |
|---|---|---|---|
| 🍃 Essência do Vento | 12 | 1 | Encantador |
| 🟠 Âmbar de Seiva | 30 | 2 | Joalheiro |
| 💧 Essência da Água | 55 | 3 | Encantador |
| 🤍 Lágrima de Sal | 85 | 4 | Joalheiro |
| 🧊 Essência do Gelo | 120 | 5 | Encantador |
| 🔴 Rubi Fosco | 160 | 6 | Joalheiro |
| 🔥 Essência de Fogo | 210 | 7 | Encantador |
| 🟣 Vitral Partido | 265 | 8 | Joalheiro |
| 🌟 Essência Estelar | 330 | 9 | Encantador |
| ⚪ Pérola do Eco | 400 | 10 | Joalheiro |

## NPCs por andar

Tipos: `mercador` (vende poção + é a bancada de Alquimia), `ferreiro` (vende
arma/armadura do andar + é a bancada de Forja), `carroceiro` (viagem grátis,
só a partir do andar 3), `encantador` (bancada de Encantador, ímpares),
`joalheiro` (bancada de Joalheiro, pares), `conversa` (sem função de jogo,
só ambientação).

| Andar | Mercador | Ferreiro | Mágico | Outro |
|---|---|---|---|---|
| 1 | Elna, da Barraca Torta | Torv, o Ferreiro Aposentado | Baldo, do Cata-Vento *(encantador)* | Pip, o Menino que Conta *(conversa)* |
| 2 | Irmã Vell, da Tenda de Musgo | — | Orin, da Árvore Torta *(joalheiro)* | O Lenhador, que não corta *(conversa)* |
| 3 | Doran, do Bote Furado | Kesh, da Forja Submersa | Lira, a Que Escuta a Maré *(encantador)* | Bramm, o Carroceiro *(carroceiro — desbloqueia aqui)* |
| 4 | Ysra, da Caravana | — | Kef, do Poço Seco *(joalheiro)* | O Homem de Sal *(conversa)* |
| 5 | Tikk, do Trenó | Hjalmar, o Sopro Frio | Corin, do Casaco Longo *(encantador)* | A Pescadora, silenciosa *(conversa)* |
| 6 | Bico, do Vagão 7 | — | Mira, do Trilho Morto *(joalheiro)* | Recado do Capataz *(conversa)* |
| 7 | Vane, da Tenda de Cinza | Ignatia, a Bigorna Viva | Talla, da Última Brasa *(encantador)* | O Cavaleiro, que espera *(conversa)* |
| 8 | Irmão Cael | — | Vesna, do Altar Lateral *(joalheiro)* | A Corista, sem voz *(conversa)* |
| 9 | Ori, do Balão | Selen, a Última Forja | Astrea, Contadora de Estrelas *(encantador)* | O Cartógrafo, do Vazio *(conversa)* |
| 10 | Eco de um Mercador | — | Eco de uma Joalheira *(joalheiro)* | A Porta *(conversa)* |

Andares pares (2, 4, 6, 8, 10) não têm ferreiro — não vendem equipamento,
só poção. É por isso que equipamento só sai nos ímpares: cada arma/armadura
tem `andar_min` igual ao andar onde o ferreiro dela mora. Encantador e
Joalheiro seguem a régua inversa entre si (Encantador só nos ímpares,
Joalheiro só nos pares) — as falas dos 10 NPCs mágicos são inventadas pra
fechar a carta, não são do Rafael (ver `decisoes.md`).

### Carroça do Bramm (viagem grátis)

Passa 4x por dia, horário de Brasília: **9h, 12h40, 15h, 21h**, fica parada
**30 minutos** em cada horário. Só existe a partir de quem já destrancou o
andar 3. Fora da janela da carroça, viajar custa moedas (ver `custo_viagem`
em `balanceamento.md`).

`agenda.py` avisa sozinho no canal configurado (`CANAL_TORRE_ID` no `.env`)
assim que cada janela abre, marcando `@everyone` — precisa da permissão
**Mencionar @everyone** liberada pro bot naquele canal, senão o aviso falha
silenciosamente (só loga no console, não derruba o resto do bot).

## Profissões (`rpg profissao`)

Cada jogador escolhe **uma só**. Trocar custa 1000 🪙 e zera o nível de
ofício. Nível máximo 10 pra Forja/Alquimia, **9** pra Encantador/Joalheiro
(curva própria, ver `balanceamento.md`).

| Ofício | Título | Bancada | O que faz |
|---|---|---|---|
| ⚒️ Forja | Ferreiro | NPC `ferreiro` | Bate as armaduras forjadas (não vendidas em loja) e as 3 peças de selo (nível 9) |
| ⚗️ Alquimia | Alquimista | NPC `mercador` | Destila os elixires de cura por porcentagem |
| 🔯 Encantador | Encantador | NPC `encantador` (ímpares) | `rpg encantar <arma\|armadura\|anel\|colar> <atributo>` — soma um atributo numa peça já existente. `rpg desencantar <peça>` remove por metade do custo |
| 💎 Joalheiro | Joalheiro | NPC `joalheiro` (pares) | `rpg lapidar <anel\|colar> <atributo>` — fabrica anel/colar do zero, escolhendo o atributo. O bônus escala com o nível do Joalheiro |

### Receitas

Curva de XP de ofício: `50 * nível` para subir de N pra N+1 (era `50 *
nível^1.4`, trocada pra ficar mais rápida — vale pra Forja e Alquimia, as
duas usam a mesma `xp_para_subir`).

| Receita | Ofício | Nível | Materiais | Preço 🪙 | XP |
|---|---|---|---|---|---|
| 🥾 «Couro Batido» | Forja | 1 | Presa de Javali x3 | 400 | 22 |
| ⛓️ «Malha Reforçada» | Forja | 3 | Osso Enferrujado x3 | 1400 | 75 |
| 🔩 «Placas Polidas» | Forja | 3 | Núcleo Gelado x3 | 3000 | 165 |
| 🜃 «Couraça de Cinzas» | Forja | 5 | Brasa Eterna x3 | 6200 | 340 |
| 🌑 «Lâmina do Selo» | Forja | 7 | Fragmento do Selo x2 + Pena do Trovão x3 | 8000 | 180 |
| 🌒 «Adaga do Selo» | Forja | 7 | Fragmento do Selo x2 + Pena do Trovão x3 | 7000 | 180 |
| 🌑 «Cajado do Selo» | Forja | 7 | Fragmento do Selo x2 + Pena do Trovão x3 | 8000 | 180 |
| 🌒 «Manoplas do Selo» | Forja | 7 | Fragmento do Selo x2 + Pena do Trovão x3 | 7000 | 180 |
| 🧿 «Manto do Selo» | Forja | 8 | Fragmento do Selo x2 + Pena do Trovão x3 | 7500 | 180 |
| 🌿 «Elixir de Ervas» | Alquimia | 1 | Seda Sussurrante x3 | 200 | 20 |
| 🍷 «Elixir Vermelho» | Alquimia | 4 | Cristal de Sal x3 | 900 | 90 |
| 🟣 «Elixir de Mana» | Alquimia | 4 | Cristal de Sal x3 | 900 | 90 |
| 🍯 «Néctar da Torre» | Alquimia | 7 | Fragmento de Sino x3 | 2600 | 300 |

As cinco receitas de nível 7/8 da Forja competem pelo mesmo material
(Fragmento do Selo, que só dropa de chefe) — só dá pra fazer todas se a
party farmar chefe várias vezes.

### Melhoria e desmanche (`rpg melhorar`, `rpg desmanchar`)

Qualquer jogador pode tentar melhorar a arma ou armadura que tem equipada,
no ferreiro de qualquer andar (`rpg melhorar arma` / `rpg melhorar
armadura`) — Forjador paga 25% a menos de material e moeda. O nível de
melhoria fica preso ao par (jogador, item), não ao slot — sobrevive a
desequipar e reequipar, mas some se a peça for desmanchada. Se o jogador
tiver duas cópias do mesmo item, as duas "compartilham" o nível salvo (não
há distinção por cópia individual).

| Tentativa | Custo | Sucesso | Ganho |
|---|---|---|---|
| +1 | material do andar x2 + 40% do preço da peça | garantido | +12% do stat base (atk/def) |
| +2 | material do andar x3 + 100% do preço da peça | 70% (85% Forjador) | +12% adicional — teto em +2 |

Falha no +2 consome material e moeda mas nunca quebra nem rebaixa a peça.
XP de ofício do upgrade (+1 = 25, +2 = 50) só é concedido a quem **é**
Forjador — qualquer jogador pode pagar pra melhorar, mas só sobe nível de
Forja quem exerce o ofício.

`rpg desmanchar <item>` funde equipamento não-equipado de volta em
material: devolve 50% do material da receita (arredondado pra baixo,
mínimo 1) + 1 por nível de melhoria que a peça tinha, e zera esse nível.
Dá 40% do XP de craft daquela peça — de novo, só se o jogador for Forjador.
Peça comprada em loja (sem receita própria, ex. Espada de Ferro) desmancha
pelo material do andar dela, com a mesma conta de 50%.

### Encantador e Joalheiro

Não fabricam em série como Forja/Alquimia — o bônus entregue é o que o
**nível atual** do ofício rende, não escolha do jogador. Mesma tabela pros
dois:

| Nível do ofício | Bônus | Custo 🪙 |
|---|---|---|
| 1-2 | +1 | 400 |
| 3 | +2 | 900 |
| 4 | +3 | 1.600 |
| 5 | +4 | 2.600 |
| 6-7 | +5 | 3.800 |
| 8 | +6 | 5.200 |
| 9 | +7 | 6.800 |

Material: 3x do material do ofício no "andar do bônus" (bônus 1/2 → andar
mais baixo da escada, ..., bônus 7 → andar mais alto + 1x 💠 Eco
Cristalizado). Ver `balanceamento.md` pra tabela completa de bônus→andar.

- **Encantador**: soma o atributo escolhido (FOR/DES/CON/INT) numa peça já
  existente (arma, armadura, anel ou colar). Não conta pra requisito de
  skill. Peça já encantada recusa reencantar — `rpg desencantar` remove por
  metade do custo de encantar aquele valor, e dá pra encantar de novo
  depois (ganha XP outra vez).
- **Joalheiro**: fabrica anel/colar do zero (`anel_joia`/`colar_joia`),
  jogador escolhe o atributo na hora. Soma com um encantamento por cima
  sem trava nenhuma.

## Efeitos temporários (`rpg efeitos`)

Contados em combates (caçada, exploração ou chefe — qualquer um consome 1),
não em tempo. Até 2 ativos ao mesmo tempo hoje. Nenhuma receita de craft
produz o item que concede efeito ainda — o sistema existe, mas está sem
fonte in-game.

| Efeito | Aplica em | Efeito |
|---|---|---|
| ⚔️ Fúria | `atk` | aumenta o dano dos golpes |
| 🍀 Sorte | `drop` | aumenta a chance de drop dos monstros |
| 🛡️ Guarda | `def` | aumenta a defesa |
