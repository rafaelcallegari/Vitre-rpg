---
name: vitre-rpg
description: Contexto e ciclo de trabalho do "Vitre bot" — RPG de grind por chat no Discord (Python/discord.py, prefixo `rpg`), com torre de 10 andares, atributos, classes, NPCs, economia e crafting. Use SEMPRE que o pedido tocar no bot, na torre, nos andares, chefes, NPCs, balanceamento, ou em qualquer arquivo do projeto (bot.py, game_data.py, npcs.py, database.py, aincrad.db) — mesmo que pareça pequeno, tipo "adiciona um item" ou "muda o cooldown". Também use para EPIC RPG, mecânica de grind por chat, ou a documentação do jogo no Notion.
---

# Vitre RPG — bot de RPG do Discord

Projeto pessoal do Rafael: um RPG de economia jogado por chat no Discord, no
espírito do EPIC RPG, com progressão em torre inspirada em Sword Art Online.
Roda no PC dele, para um servidor de 5 a 10 amigos que já estão jogando.

**Leia o código antes de perguntar.** O repositório é a verdade. Os references
são resumo e envelhecem; quando um reference discordar do código, o código
vence e o reference deve ser corrigido no mesmo trabalho.

- `references/decisoes.md` — decisões de design já fechadas e as ainda não
 implementadas. Leia sempre.
- `references/arquitetura.md` — onde as coisas moram e o padrão de migração.
- `references/conteudo.md` — andares, itens, NPCs, monstros.
- `references/balanceamento.md` — fórmulas, curvas e armadilhas conhecidas.

## O ciclo

Todo pedido passa pelas mesmas cinco fases. Identifique em qual o pedido está e
conduza dali. Não é obrigatório percorrer as cinco, mas é obrigatório não pular
para "criação" sem ter passado por "brainstorm".

### 1. Brainstorm — questionar antes de construir

Rafael pediu explicitamente para ser questionado bastante antes de qualquer
implementação. Não é formalidade: as perguntas já mudaram o projeto inteiro mais
de uma vez. O pedido inicial parecia ser um assistente de mesa e era um jogo de
grind; "loja por andar" virou sistema de viagem com NPC carroceiro; "subir o
dano dos monstros" virou tirar a defesa do CON.

Faça perguntas que mudem o código, não perguntas de cortesia:
- **Motivação real** — resolver uma dor, praticar, ou zoeira com os amigos?
- **Escopo mínimo** — que fatia já é divertida sozinha?
- **Forks de design** que geram arquiteturas diferentes.
- **Consequências que ele ainda não viu** — exploits de economia, o que acontece
 com 8 pessoas ao mesmo tempo, qual sistema novo desfaz um ajuste antigo.

Desafie o pedido quando fizer sentido. Mas uma vez que ele responde, aceite e
siga — ele já mostrou impaciência com insistência desnecessária.

### 2. Criação — módulo novo, não arquivo gigante reescrito

Quando a mudança atinge um arquivo grande, prefira **criar um módulo novo** a
reescrever o arquivo inteiro. Foi assim que `npcs.py` nasceu: o sistema de NPCs
e viagem entrou sem tocar em uma linha de `game_data.py`.

Sempre que mexer no schema, inclua a migração dentro de `init_db()` — há
progresso real de jogadores no `aincrad.db` e perder isso seria péssimo. Veja o
padrão em `references/arquitetura.md`.

Mudança que enfraquece build já existente (nerf de atributo, troca de fórmula)
entra junto com **devolução de pontos ou respec grátis** na mesma migração.

Depois do código, explique **as duas ou três decisões que mais mudam a sensação
do jogo** e por quê. Não liste tudo que foi feito; ele lê o código.

### 3. Teste — ele roda o bot, você prepara o terreno

O bot precisa do Discord para rodar de verdade, então o teste final é sempre com
ele. O que dá para fazer antes de entregar: checar sintaxe, rodar as funções
puras de combate e economia em isolamento, e simular numericamente o combate
antes de afirmar que um número está bom.

Termine entregas com uma sequência de teste concreta, em ordem, com o motivo da
ordem: comandos que não tocam no banco primeiro (`rpg ajuda`), depois os que
escrevem (`rpg comecar`), depois o loop completo.

Antecipe os erros prováveis pelo **sintoma que ele vai ver**, não pelo nome
técnico. Ele é iniciante em bot de Discord e deploy Python; o que trava são
detalhes de ambiente (venv, `.env` salvo como `.env.txt`, intents no portal).

Diga também o que observar jogando — combates até subir de nível, se poção
pareceu necessária, quantas mortes. Esses dados alimentam a fase seguinte.

### 4. Balanceamento — números vêm dos testes, não do achismo

Faça a conta antes de opinar, com os stats reais que ele descreveu, e mostre o
resultado. Se a fórmula no reference não bater com o código, use o código.

Seja honesto quando o resultado for ruim mesmo que ele esteja empolgado.
"Ninguém morreu" é sinal de problema, não de sucesso.

Antes de propor um ajuste, verifique se ele não é anulado por uma das redes de
segurança que já existem: cura no level up, regeneração por tempo, 3 poções por
luta, e a taverna quando ela entrar. Apertar o combate com todas no lugar
resolve pela metade.

### 5. Documentação — guia e Kanban no Notion

Duas páginas no Notion, mantidas pelo MCP:
- **"Guia da Torre — Bot de RPG"** — comandos, andares, NPCs, itens, curva de XP.
- **"Kanban Vitre"** — backlog com Status e Prioridade.

Sempre que uma mudança alterar algo que está no Guia, ofereça atualizar no mesmo
turno. Um guia que mente é pior que nenhum guia. Ao escrever, mantenha o tom do
jogo: descrições de andar em itálico, nomes de habilidade e itens raros entre
`«»`, tabelas para dados consultáveis.

Decisão de design fechada na conversa entra em `references/decisoes.md` no mesmo
commit da mudança.

## Invariantes de design

Já foram tomadas e discutidas. Não reverta sem perguntar — mas avise se um
pedido novo entrar em conflito com alguma.

- **Chefe só pode ser enfrentado no andar mais alto destrancado.** Sem isso, dá
 para farmar chefe fácil sem risco.
- **Equipamento só existe nos andares ímpares (1, 3, 5, 7, 9)**, com o ferreiro
 daquele andar. Poção é vendida em todo andar. Isso dá função à viagem.
- **`andar` e `andar_max` são coisas diferentes** — localização atual e
 progresso. Muita lógica depende dessa separação.
- **Regeneração de HP existe, mas só fora de jogo**: 5% do máximo por minuto,
 teto em 70%. Ela não pode substituir poção.
- **Combate por turnos com botões é só do chefe.** Caçada é instantânea.
- **Conteúdo é original.** A torre é inspirada em SAO, mas nomes de monstro,
 chefe e NPC são inventados — nada de personagem ou chefe do anime.
- **Prefixo `rpg`, não slash commands.** Exige Message Content Intent ligado.

## Como falar com ele

Português. Direto, sem bajulação. Ele responde bem a análise técnica com a conta
na mesa e a discordância explicada.

Quando usa gíria ("projetinho resenha", "deixar mais roubadinho"), é jeito de
falar — confirme o sentido antes de codar em cima.

Ele está aprendendo bot de Discord e Python de servidor pela primeira vez, então
explique o *porquê* junto com o passo, especialmente em ambiente. Mas não
explique programação básica — ele é estagiário de IA e faz pós em ML.
