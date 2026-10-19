# Laboratório — Algoritmo Bully

Implementação em Python 3, somente com biblioteca padrão. Cada processo é um programa independente que atua como servidor e cliente TCP em `127.0.0.1:5001` a `5005`.

## Execução manual

Abra cinco terminais nesta pasta e execute um comando em cada um:

```sh
python3 processo.py 1
python3 processo.py 2
python3 processo.py 3
python3 processo.py 4
python3 processo.py 5
```

Comandos: `eleicao` inicia uma eleição; `status` mostra o coordenador local e se há eleição; `sair` encerra o processo. `Ctrl+C` também encerra. IDs fora de 1 a 5 e portas ocupadas produzem erro explicativo.

## Experimentos do enunciado

1. Com os cinco processos ativos, digite `eleicao` em P5. Todos devem indicar P5 no `status`.
2. Encerre P5 e digite `eleicao` em P2. P3/P4 respondem OK; P4 vence.
3. Reinicie P5 e digite `eleicao` nele. P5 recupera a coordenação.
4. Encerre P5 e eleja P4; encerre e reinicie P2, iniciando uma eleição em P2. P4 permanece coordenador.
5. Encerre P4/P5, mantendo P1/P2/P3; inicie eleição em P1. P3 vence.

Espere a conclusão dos anúncios antes de consultar o estado final. No modo manual, reiniciar um processo não inicia uma eleição por si só.

## Detecção automática e diagrama

Acrescente `--automatico` a cada comando para ativar PING/PONG e eleição na inicialização. O monitor consulta o coordenador a cada segundo; falha ou ausência de coordenador dispara eleição. Reiniciar P5 nesse modo faz com que ele assuma automaticamente.

Os logs mostram horário, emissor, receptor e mensagens como `P2 --> P4 : ELECTION`, `P4 --> P2 : OK`, desistências, vencedor e `COORDINATOR`. O diagrama é um fluxo textual local em cada terminal; logs de processos diferentes podem ser intercalados no tempo. Cada nova rodada registra seu iniciador local.

## Protocolo e implementação

Mensagens JSON terminadas por newline transportam `tipo` e `origem`. Os tipos do Bully são ELECTION, OK e COORDINATOR. PING/PONG verificam disponibilidade; ACK confirma o recebimento de anúncios. OK é respondido na mesma conexão ELECTION. Cada conexão transmite uma requisição e uma resposta, com limite de 4096 bytes e timeout.

Um lock protege o estado da eleição. O processo consulta apenas IDs superiores, aguarda COORDINATOR depois de receber OK e repete se o anúncio não chegar em quatro segundos. Uma geração local impede uma rodada antiga de sobrescrever um anúncio recebido enquanto consultava os pares. Um anúncio inferior ao ID local provoca nova eleição.

## Testes e entrega

```sh
python3 testar.py
```

Execute com as portas 5001–5005 livres. O teste inicia subprocessos reais, confere convergência de todos os sobreviventes e encerra os subprocessos ao terminar. Reproduz os cinco experimentos, eleições simultâneas, falha abrupta e recuperação automática. Os arquivos em `evidencias/` são regenerados a cada execução; `resultados.txt` contém o resultado da execução entregue.

- `config.py`: participantes e tempos.
- `processo.py`: implementação e interface de terminal.
- `testar.py`: testes de integração.
- `relatorio.pdf`: relatório, evidências, análise e respostas.
- `relatorio.html`: fonte editável do relatório.

## Limitações

A lista de participantes é fixa. Timeouts podem confundir lentidão com falha; partições de rede podem produzir vários coordenadores. Não há consenso por quórum, autenticação, persistência nem garantia de exclusão mútua global. O custo de eleição pode chegar a O(n²) mensagens. Os tempos escolhidos são adequados ao laboratório local, e não constituem garantia de desempenho em rede real.
