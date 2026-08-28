---
version: 1
status: generated
generated_at: "2026-08-26"
source_of_truth: github
---

# Ferramentas que podem ajudar nesta trilha

Este plano mostra somente ferramentas com utilidade concreta para o curso de Estoicismo e para a rotina escolhida. Tudo continua funcionando com os materiais do GitHub quando uma ferramenta opcional não é conectada.

## Visão rápida

| Para quê | Ferramenta | Por que pode ajudar | É necessária? | Alternativa |
| --- | --- | --- | --- | --- |
| Acompanhar as etapas | GitHub Issues | Você já escolheu o GitHub Issues como ferramenta de tarefas no formulário inicial; cada aula vira uma issue com o estado atual visível pelos labels. | sim | Roadmap no repositório (`study/roadmap.md`) |
| Reservar horários fixos | nenhuma | Você optou por decidir isso depois (`decide_later`); nenhum calendário foi ativado. | não | Avançar no seu próprio ritmo, sem agenda fixa |
| Receber lembretes flexíveis | nenhuma | Mesma decisão adiada (`decide_later`); nenhum lembrete foi ativado. | não | Acompanhar o progresso pelas issues |

## Preferência de conexão

Você indicou `account_connections: ask_per_provider` no formulário inicial: está aberto a conectar uma ferramenta quando ela tiver valor claro para a etapa atual, mas nada é conectado sem uma ação explícita sua. Nesta trilha, isso significa: o GitHub (já em uso) é a ferramenta principal, e nenhuma outra conta será sugerida até que faça sentido para uma aula específica.

## Rotina de estudo

Sua preferência de rotina está registrada como `decide_later`: nem um calendário fixo nem lembretes flexíveis foram ativados agora. Você avança pelo seu próprio ritmo, na ordem dos pré-requisitos de cada aula. Se depois você quiser um lembrete recorrente (Todoist) ou blocos fixos de estudo (Google Calendar ou Outlook Calendar), basta pedir e cuidamos dos detalhes que faltarem (dias, horário, duração, fuso).

## Como cada ferramenta será usada

### GitHub Issues — acompanhamento das aulas

- **Por que faz sentido para você:** foi a opção que você escolheu no formulário inicial, e a trilha tem um número de aulas (8) confortável para issues bem organizadas por labels.
- **Como será usada:** cada aula do roadmap vira uma issue única, com labels indicando o estado (`study:planned`, `study:ready`, `study:in-progress` etc.) e links para a aula, a prática (quando houver uma separada) e a avaliação.
- **Quando entra em cena:** na próxima etapa da trilha, quando você pedir para organizar a trilha nas ferramentas escolhidas.
- **O que será compartilhado:** apenas título da aula, descrição de estudo, links para os materiais e labels de estado — nenhum dado pessoal além do necessário para navegação.
- **Sem esta ferramenta:** o roadmap em `study/roadmap.md` e os arquivos em `study/topics/` continuam descrevendo completamente a trilha e a ordem das aulas.
- **Acesso:** usa o mesmo repositório GitHub que você já está usando; não exige conta adicional.

### Pesquisa e fontes primárias

Para um curso de filosofia como este, a base de evidência são as próprias fontes primárias (Sêneca, Epicteto, Marco Aurélio) e referências acadêmicas estáveis (Stanford Encyclopedia of Philosophy, Internet Encyclopedia of Philosophy), já citadas diretamente em cada aula. Uma ferramenta de pesquisa como o Consensus é mais útil para afirmações empíricas de ciências; não foi ativada para esta trilha porque as fontes textuais diretas já cobrem a necessidade.

## E-mail sob demanda

Gmail e Outlook não foram configurados durante a criação desta trilha. Se, em algum momento, você quiser um resumo por e-mail do seu progresso, basta pedir explicitamente — até lá, o chat e o GitHub continuam sendo os canais principais.

## Detalhes operacionais

<details>
<summary>Ver contrato técnico de integrações</summary>

- account_connections: ask_per_provider
- routine mode: decide_later (sem detalhes de horário coletados; nenhuma ativação de calendário ou lembretes)
- task fallback order: github_issues (selecionado explicitamente no intake), com markdown do repositório como alternativa interna final
- integration constraints preservadas do intake: `integrations.task_manager: github_issues`

Capacidades ativadas nesta etapa de geração: nenhuma escrita externa foi realizada. A publicação de tarefas no GitHub Issues (criação das issues por aula) acontece na próxima etapa da trilha (`Organize minha trilha nas ferramentas que escolhemos.`), seguindo `instructions/42-integration-preflight.md` e `instructions/31-topic-first-safe-publication.md`.

GitHub permanece responsável por currículo, conteúdo, avaliação e progresso verificado. Apenas o GitHub Issues mantém o estado de execução das aulas. Mermaid permanece a representação visual versionada do roadmap. Nenhuma projeção Airtable foi solicitada ou ativada.

</details>
