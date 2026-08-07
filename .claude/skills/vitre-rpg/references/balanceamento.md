# Balanceamento — Vitre RPG

Fórmulas e curvas tiradas direto de `atributos.py`, `combate.py` e `bot.py`.
Se este arquivo discordar do código, o código venceu — corrija aqui.

## Progressão de nível

- XP para sair do nível N: `xp_necessario(N) = int(40 * N**1.5)` (`game_data.py`).
- Cada nível dá `PONTOS_POR_NIVEL = 3` pontos livres de atributo.
- Todo personagem começa com `BASE = 5` em cada um dos quatro atributos.
- Respec (`rpg respec`) custa `50 * nível` moedas (`custo_respec`), exceto se
 a coluna `respec_gratis` do jogador estiver ligada — nesse caso é de graça e
 a flag desliga sozinha depois de usada. A migração do rebalanceamento de
 defesa ligou a flag pra todo mundo que já jogava, porque tirar CON da
 defesa muda o que vale a pena distribuir.
- Subir de nível cura `CURA_LEVEL_UP = 50%` do HP máximo **novo**, somado ao
 crescimento de HP do(s) nível(is) ganho(s) (`hp_depois_do_nivel` em `bot.py`).

## HP e mana

- `hp_maximo(nível, CON) = 60 + 10*CON + 10*(nível-1)`
 (`HP_BASE=60`, `HP_POR_CON=10`, `HP_POR_NIVEL=10`).
- `mana_maxima(nível, INT) = 20 + 5*INT` (`MANA_BASE=20`, `MANA_POR_INT=5`).
 Confirma o valor citado em `decisoes.md` (INT 6 → 50 de mana).
- Mana não tem consumidor ainda — habilidades não existem no código.

## Ataque, defesa e crítico

- `ataque(atributo_da_arma, bônus_arma) = 5 + 2*atributo + bônus_arma`.
 O atributo usado depende da arma: `atributo_da_arma()` olha o campo
 `"atributo"` do item, e cai para **força** com mãos vazias ou arma sem o
 campo (`ATRIBUTO_PADRAO_ARMA`).
- `defesa(bônus_armadura) = 2 + bônus_armadura`. **CON não entra mais na
 conta** — defesa vem só de equipamento, CON só dá HP (ver
 `decisoes.md` § Rebalanceamento da defesa). Antes da migração de respec
 grátis, essa fórmula tinha `+ CON`.
- Crítico: `CRITICO_BASE = 10%` para armas de força (ou mãos vazias). Armas de
 destreza declaram `"critico": 0.18` no item — **18%**, fixo, não escala com
 atributo. Multiplicador de crítico: `MULTIPLICADOR_CRITICO = 1.8x`.
- Isso é a assimetria de arma: força bate mais forte com metade do crítico;
 destreza crita quase o dobro das vezes. Nenhuma arma de destreza tem
 `"critico"` diferente de 0.18 — é constante de classe de arma, não por item.

## Redução de dano por defesa

Curva com teto — a defesa nunca zera o dano:

```
reducao_dano(DEF) = min(0.60, DEF / (DEF + 50))   # DEF <= 0 → 0
dano_final = max(1, int(dano_bruto * (1 - reducao_dano(DEF))))
```

`K_DEFESA = 50`, `TETO_REDUCAO = 60%`. Alguns pontos da curva:

| DEF | Redução |
|---|---|
| 10 | 16.7% |
| 20 | 28.6% |
| 30 | 37.5% |
| 50 | 50.0% |
| 75 | 60.0% (já no teto) |
| 120 | 60.0% (teto, DEF acima disso não faz nada) |

Uma vez que a party passa de ~75 de DEF efetiva contra um alvo, gastar mais
em defesa pura não compra mais redução — só o HP por trás dela ainda ajuda.

## Destreza implícita do monstro

Monstros e chefes não têm campo de destreza em `game_data.py`. Ela é
calculada na hora: `destreza_monstro(andar) = 4 + 2*(andar-1)`. Sobe 2 por
andar, então iniciativa, esquiva e fuga do jogador degradam sozinhas conforme
a torre avança, mesmo com DES parada.

## Iniciativa, esquiva e fuga

Todas com teto e piso (`_limitar`):

- **Iniciativa** (quem abre o combate):
 `0.50 + 0.02*(DES_jogador - DES_monstro)`, entre 20% e 90%.
- **Esquiva**: `0.02 + 0.01*(DES_jogador - DES_atacante)`, entre 0% e
 `TETO_ESQUIVA = 25%`. Sobe metade do ritmo da iniciativa.
- **Fuga** (só existe na luta de chefe): `0.45 + 0.02*(DES - DES_chefe)`,
 entre 10% e 85% — e **-15 pontos percentuais fixos** por ser chefe
 (`eh_chefe=True`). Em party, cada companheiro que já caiu soma
 `+15%` de novo (`FUGA_POR_DESFALQUE`), até o teto de 90% do próprio
 `Luta.chance_de_fuga`.

## Regeneração fora de combate

- `REGEN_POR_MINUTO = 5%` do HP máximo por minuto parado.
- Teto de `REGEN_TETO = 70%` — regeneração nunca substitui poção pro resto.
- Só começa `REGEN_PAUSA_SEG = 180s` (3 min) depois do último combate.

## Caçada e exploração (`bot.py`)

- `calcular_dano(atk, def, crítico) = aplicar_defesa(atk * U(0.85, 1.15) * (1.8 se crítico), def)`.
 Mesma fórmula pro jogador e pro monstro.
- `simular_combate` roda até 60 rodadas (proteção contra loop infinito, nunca
 deveria bater nisso na prática) e resolve instantâneo — sem botão, sem
 escolha do jogador durante a luta.
- Quem tem iniciativa perdida (`chance_iniciativa` falhou) leva o primeiro
 golpe do monstro antes de atacar.
- **Caçada**: 1 monstro, cooldown `COOLDOWN_CACAR = 60s`.
- **Exploração**: 3 monstros em sequência com o HP acumulando entre eles,
 cooldown `COOLDOWN_EXPLORAR = 180s` (3 min). Recompensa recebe
 **+50% de bônus de moedas** (`total_moedas * 0.5`) sobre a soma dos 3
 monstros — o preço de arriscar perder tudo se cair no 2º ou 3º.
- **Morte** (caçada, exploração ou chefe): `processar_morte` tira **20%** das
 moedas atuais e devolve o jogador com **30%** do HP máximo. Na exploração,
 cair no meio também derruba todo o XP/moedas/drop já acumulado na corrida —
 tudo ou nada.

## Chefe (`combate.py`) — combate por turnos com botão

- **ATK do chefe**: `13 + 13*(andar-1)` (`game_data.py`, valor fixo por
 andar, não é uma função — atualizar à mão se o andar mudar). Andar 1 fica
 em 13, andar 10 em 130. Antes do rebalanceamento de defesa era
 `13 + 8*(andar-1)` (andar 10 = 85); subiu porque CON parou de dar defesa e
 o chefe precisava continuar ameaçador.
- **HP do chefe escala com o tamanho da party**: `hp_chefe = chefe["hp"] *
 nº de participantes`. Cada jogador recebe a recompensa **inteira** ao
 vencer (não dividida), então subir de tamanho de party não dilui — só
 exige mais dano total pra compensar o HP extra.
- **Penetração de armadura do chefe**, cresce com o andar:
 `penetracao(andar) = min(0.85, 0.30 + 0.015*(andar-1))`.

 | Andar | Penetração normal | + golpe carregado |
 |---|---|---|
 | 1 | 30.0% | 55.0% |
 | 5 | 36.0% | 61.0% |
 | 10 | 43.5% | 68.5% |

 A penetração reduz a defesa efetiva do alvo (`def * (1 - penetração)`)
 antes de aplicar `reducao_dano`. Armadura vale cada vez menos contra chefe
 quanto mais alto o andar — empurra pra HP e cura, não só pra DEF.
- **Golpe carregado**: `CHANCE_CARREGAR = 30%` por rodada de o chefe recuar e
 avisar. Na rodada seguinte acerta **todo mundo** com `MULTIPLICADOR_CARREGADO
 = 3x` de dano e `+25 pontos percentuais` de penetração extra
 (`PENETRACAO_CARREGADO`).
- **Defender** (`REDUCAO_DEFENDENDO = 50%`): zera a penetração do golpe
 recebido **e** ainda corta o dano resultante pela metade. É a resposta
 correta ao golpe carregado — só avisa, então dá pra reagir.
- Crítico do chefe usa as mesmas constantes do jogador: `CRITICO_BASE = 10%`,
 `x1.8`.
- Até `MAX_POCOES = 3` **poções** por pessoa por luta, e à parte,
 `MAX_ELIXIRES = 1` **elixir de Alquimia** por pessoa por luta — contadores
 independentes (dá pra usar os dois no mesmo combate). A diferença é o campo
 do item: cura fixa (`"cura"`) conta como poção, cura por porcentagem
 (`"cura_pct"`) conta como elixir. Sala de espera de party
 fecha em `TIMEOUT_SALA = 90s`; cada rodada dá `TIMEOUT_RODADA = 60s` pra
 agir, senão o jogador sai sozinho da luta (sem contar como fuga).
- Cooldown de chefe: `COOLDOWN_BOSS = 900s` (15 min), gasto ao **entrar** na
 luta — vale pra vitória, derrota e sumiço por timeout. Só quem **foge**
 pelo botão não paga o cooldown de novo (o `SalaDeEspera`/`iniciar_luta` já
 cobrou na entrada; a fuga bem-sucedida zera de volta).
- Só entra na sala de chefe quem está com pelo menos `HP_MINIMO_PARA_ENTRAR =
 40%` do HP máximo, e só quem já destrancou aquele andar (`andar == andar_max`
 do próprio; em party, todos precisam ter o mesmo `andar_max` do anfitrião).
- Vencer restaura o HP a 100% de quem sobreviveu, além de XP, moedas cheias
 do chefe e drop garantido de `fragmento_selo` (100% de chance).

## Redes de segurança já existentes

Qualquer aperto no combate (subir dano de monstro, endurecer defesa) precisa
ser calibrado considerando que estas quatro já existem e amortecem risco:

1. **Cura no level up** — 50% do HP máximo novo, de graça.
2. **Regeneração por tempo** — 5%/min fora de combate, até 70% do HP máximo.
3. **3 poções por luta de chefe** — grátis em termos de regra, custa só o
 preço do item.
4. **Morte é barata** — 20% das moedas e volta com 30% de HP; não existe
 perda de item, nível ou XP em nenhuma derrota.

Ver `decisoes.md` para o diagnóstico específico do porquê ninguém estava
morrendo (CON dando HP e defesa juntos, sem teto na aparagem antiga) e o
rebalanceamento pendente.

## Efeitos temporários (`efeitos.py`)

- Contados em **combates**, não em tempo — cada caçada, exploração ou chefe
 consome 1 do contador de todo efeito ativo (`consumir`), sobreviva ou não à
 luta.
- Até `MAX_ATIVOS = 2` efeitos simultâneos.
- Três efeitos no catálogo hoje: **Fúria** (`atk`), **Sorte** (`drop`),
 **Guarda** (`def`) — todos multiplicativos: `fator = 1 + valor`, empilhando
 se por algum motivo dois efeitos aplicassem no mesmo alvo (não acontece
 hoje, cada chave do catálogo aplica em um alvo diferente).
- Nenhuma receita de Alquimia em `profissoes.py` produz um item que concede
 efeito — o sistema existe em código mas ainda não tem produtor.

## Profissões e craft (`profissoes.py`)

- XP de ofício: `xp_para_subir(nível) = 50 * nível`, nível máximo `10`.
 Trocada de `int(50 * nível**1.4)` — mais rápida em todo tier, e mais ainda
 nos altos porque a curva antiga era superlinear.
- Trocar de profissão custa `CUSTO_TROCA = 1000` moedas e **zera o nível**
 de ofício — escolha é praticamente travada na prática.
- Craft exige estar no andar certo (bancada do NPC do ofício) — não dá pra
 fabricar longe do ferreiro/mercador daquele tipo.
- Preço em moedas + material por receita cresce junto com o tier do
 equipamento que ela produz (ver tabela em `conteudo.md`).
- **Gates de nível caíram** (Placas Polidas 5→3, Couraça 7→5, armas do
 Selo 9→7, Manto do Selo 9→8) e **material de andar caiu de x5 pra x3**
 por craft — o ofício estava mais lento que a torre em si.

### Melhoria (`rpg melhorar`) e desmanche (`rpg desmanchar`)

- Nível de melhoria (+1 teto +2) fica na tabela `upgrades(user_id, item,
 nivel)` — chaveado por (jogador, item), não pelo slot equipado. Sobrevive
 a desequipar/reequipar; duas cópias do mesmo item compartilham o nível.
- `+1`: material do andar x2 + 40% do preço, sucesso garantido. `+2`:
 material x3 + 100% do preço, 70% de chance (85% Forjador). Falha consome
 recurso mas nunca quebra/rebaixa a peça.
- Forjador paga 25% a menos (material e moeda) nas duas tentativas.
- Ganho: `+12%` do `atk`/`def` **base do item** por nível — aplicado em
 `bot.py:stats()` antes de montar a ficha de combate, não no dano final.
- XP de ofício do upgrade (25 no +1, 50 no +2) e do desmanche (40% do XP
 de craft da peça) só é concedido a quem `profissao == "forja"` — pagar
 pelo comando não exige ser Forjador, ganhar XP de Forja exige.
- Desmanche devolve 50% do material da receita (mínimo 1) + 1 por nível de
 melhoria que a peça tinha, e zera esse nível. Peça sem receita (comprada
 em loja) usa o material do andar dela com base sintética de 3 unidades.

## Economia de viagem (`npcs.py`)

- `custo_viagem(origem, destino) = |destino-origem| * (80 + 40 * max(origem, destino))`.
 Viajar pro andar mais alto já visitado é sempre mais caro por degrau do que
 descer, porque o custo por distância usa o **maior** dos dois andares.
- A carroça do Bramm (andar 3+) é **grátis**, mas só roda 4 vezes por dia
 (9h, 12h40, 15h, 21h, horário de Brasília) e fica parada só 30 min por
 horário — é a alternativa à viagem paga, não a substitui. `agenda.py`
 avisa automaticamente no canal configurado quando cada janela abre.
