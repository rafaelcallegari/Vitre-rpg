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

## NPCs por andar

Tipos: `mercador` (vende poção + é a bancada de Alquimia), `ferreiro` (vende
arma/armadura do andar + é a bancada de Forja), `carroceiro` (viagem grátis,
só a partir do andar 3), `conversa` (sem função de jogo, só ambientação).

| Andar | Mercador | Ferreiro | Outro |
|---|---|---|---|
| 1 | Elna, da Barraca Torta | Torv, o Ferreiro Aposentado | Pip, o Menino que Conta *(conversa)* |
| 2 | Irmã Vell, da Tenda de Musgo | — | O Lenhador, que não corta *(conversa)* |
| 3 | Doran, do Bote Furado | Kesh, da Forja Submersa | Bramm, o Carroceiro *(carroceiro — desbloqueia aqui)* |
| 4 | Ysra, da Caravana | — | O Homem de Sal *(conversa)* |
| 5 | Tikk, do Trenó | Hjalmar, o Sopro Frio | A Pescadora, silenciosa *(conversa)* |
| 6 | Bico, do Vagão 7 | — | Recado do Capataz *(conversa)* |
| 7 | Vane, da Tenda de Cinza | Ignatia, a Bigorna Viva | O Cavaleiro, que espera *(conversa)* |
| 8 | Irmão Cael | — | A Corista, sem voz *(conversa)* |
| 9 | Ori, do Balão | Selen, a Última Forja | O Cartógrafo, do Vazio *(conversa)* |
| 10 | Eco de um Mercador | — | A Porta *(conversa)* |

Andares pares (2, 4, 6, 8, 10) não têm ferreiro — não vendem equipamento,
só poção. É por isso que equipamento só sai nos ímpares: cada arma/armadura
tem `andar_min` igual ao andar onde o ferreiro dela mora.

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
ofício. Nível máximo 10.

| Ofício | Título | Bancada | O que faz |
|---|---|---|---|
| ⚒️ Forja | Ferreiro | NPC `ferreiro` | Bate as armaduras forjadas (não vendidas em loja) e as 3 peças de selo (nível 9) |
| ⚗️ Alquimia | Alquimista | NPC `mercador` | Destila os elixires de cura por porcentagem |

### Receitas

| Receita | Ofício | Nível | Materiais | Preço 🪙 | XP |
|---|---|---|---|---|---|
| 🥾 «Couro Batido» | Forja | 1 | Presa de Javali x5 | 700 | 35 |
| ⛓️ «Malha Reforçada» | Forja | 3 | Osso Enferrujado x5 | 2400 | 120 |
| 🔩 «Placas Polidas» | Forja | 5 | Núcleo Gelado x5 | 5200 | 260 |
| 🜃 «Couraça de Cinzas» | Forja | 7 | Brasa Eterna x5 | 11000 | 550 |
| 🌑 «Lâmina do Selo» | Forja | 9 | Fragmento do Selo x3 + Pena do Trovão x5 | 8000 | 900 |
| 🌒 «Adaga do Selo» | Forja | 9 | Fragmento do Selo x3 + Pena do Trovão x5 | 7000 | 900 |
| 🧿 «Manto do Selo» | Forja | 9 | Fragmento do Selo x3 + Pena do Trovão x5 | 7500 | 900 |
| 🌿 «Elixir de Ervas» | Alquimia | 1 | Seda Sussurrante x3 | 200 | 20 |
| 🍷 «Elixir Vermelho» | Alquimia | 4 | Cristal de Sal x3 | 900 | 90 |
| 🍯 «Néctar da Torre» | Alquimia | 7 | Fragmento de Sino x3 | 2600 | 300 |

As três receitas de nível 9 da Forja competem pelo mesmo material
(Fragmento do Selo, que só dropa de chefe) — só dá pra fazer as três se a
party farmar chefe várias vezes.

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
