"""Algoritmo Bully com processos independentes e mensagens TCP delimitadas por newline."""
import argparse
import json
import socket
import threading
import time
from datetime import datetime

from config import PROCESSOS, TIMEOUT, INTERVALO_PING, ESPERA_COORDENADOR


def ler_mensagem(conexao):
    dados = bytearray()
    while len(dados) < 4096:
        parte = conexao.recv(1)
        if not parte:
            raise ValueError("Conexão encerrada antes do fim da mensagem")
        if parte == b"\n":
            mensagem = json.loads(dados)
            if not isinstance(mensagem, dict):
                raise ValueError("Mensagem deve ser um objeto")
            return mensagem
        dados.extend(parte)
    raise ValueError("Mensagem excede 4096 bytes")


def escrever(conexao, mensagem):
    conexao.sendall((json.dumps(mensagem) + "\n").encode())


class Processo:
    def __init__(self, id_processo, automatico=False, enderecos=None):
        self.processos = enderecos if enderecos is not None else PROCESSOS
        if id_processo not in self.processos:
            raise ValueError("ID não configurado")
        self.id = id_processo
        self.coordenador = None
        self.automatico = automatico
        self.eleicao_em_andamento = False
        self.lock = threading.RLock()
        self.parado = threading.Event()
        self.anuncio = threading.Event()
        self.geracao = 0
        self.servidor = None
        self.threads = []

    def log(self, texto):
        print(f"[{datetime.now():%H:%M:%S.%f}] P{self.id} | {texto}", flush=True)

    def iniciar(self):
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            servidor.bind(self.processos[self.id])
            servidor.listen()
            servidor.settimeout(0.2)
        except OSError:
            servidor.close()
            raise
        self.servidor = servidor
        self._thread(self.iniciar_servidor)
        if self.automatico:
            self._thread(self.monitorar)
        self.log(f"aguardando conexões na porta {self.processos[self.id][1]}")

    def _thread(self, alvo, *args):
        thread = threading.Thread(target=alvo, args=args, daemon=True)
        self.threads.append(thread)
        thread.start()

    def iniciar_servidor(self):
        while not self.parado.is_set():
            try:
                conexao, _ = self.servidor.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._thread(self.atender, conexao)

    def atender(self, conexao):
        with conexao:
            conexao.settimeout(TIMEOUT)
            try:
                msg = ler_mensagem(conexao)
                origem, tipo = msg.get("origem"), msg.get("tipo")
                if type(origem) is not int or origem not in self.processos:
                    raise ValueError("Origem inválida")
                if tipo == "ELECTION" and origem < self.id:
                    self.log(f"P{origem} --> P{self.id} : ELECTION")
                    escrever(conexao, {"tipo": "OK", "origem": self.id})
                    self.log(f"P{self.id} --> P{origem} : OK")
                    self.solicitar_eleicao()
                elif tipo == "COORDINATOR":
                    if origem < self.id:
                        self.log(f"Anúncio de P{origem} inferior; iniciando eleição")
                        self.solicitar_eleicao()
                    else:
                        with self.lock:
                            self.coordenador = origem
                            self.geracao += 1
                            self.anuncio.set()
                        self.log(f"P{origem} --> P{self.id} : COORDINATOR (novo coordenador: P{origem})")
                    escrever(conexao, {"tipo": "ACK", "origem": self.id})
                elif tipo == "PING":
                    self.log(f"P{origem} --> P{self.id} : PING; P{self.id} --> P{origem} : PONG")
                    escrever(conexao, {"tipo": "PONG", "origem": self.id})
                else:
                    raise ValueError("Tipo ou direção inválida")
            except (OSError, ValueError, TypeError) as erro:
                self.log(f"Conexão ignorada: {erro}")

    def enviar(self, destino, tipo):
        try:
            with socket.create_connection(self.processos[destino], TIMEOUT) as cliente:
                cliente.settimeout(TIMEOUT)
                escrever(cliente, {"tipo": tipo, "origem": self.id})
                resposta = ler_mensagem(cliente)
                if resposta.get("origem") == destino:
                    return resposta.get("tipo")
        except (OSError, ValueError, TypeError):
            return None
        return None

    def solicitar_eleicao(self):
        with self.lock:
            if self.eleicao_em_andamento or self.parado.is_set():
                return
            self.eleicao_em_andamento = True
        self._thread(self.iniciar_eleicao)

    def iniciar_eleicao(self):
        try:
            while not self.parado.is_set():
                with self.lock:
                    geracao = self.geracao
                    self.anuncio.clear()
                self.log(f"INICIANDO ELEIÇÃO (iniciador local: P{self.id})")
                respondeu = False
                for pid in sorted(self.processos):
                    if pid > self.id:
                        self.log(f"P{self.id} --> P{pid} : ELECTION")
                        if self.enviar(pid, "ELECTION") == "OK":
                            respondeu = True
                            self.log(f"P{pid} --> P{self.id} : OK; P{self.id} desiste em favor de ID maior")
                        else:
                            self.log(f"P{pid} indisponível / sem OK")
                if self.parado.is_set():
                    return
                with self.lock:
                    if self.geracao != geracao:
                        return
                    if not respondeu:
                        self.coordenador = self.id
                        self.geracao += 1
                        self.log(f"VENCEDOR: P{self.id} É O NOVO COORDENADOR")
                if not respondeu:
                    for pid in sorted(self.processos):
                        if pid != self.id:
                            self.log(f"P{self.id} --> P{pid} : COORDINATOR:{self.id}")
                            self.enviar(pid, "COORDINATOR")
                    return
                # Se o processo maior morrer após OK, não esperamos indefinidamente.
                if self.anuncio.wait(ESPERA_COORDENADOR):
                    return
                self.log("Prazo para COORDINATOR expirou; repetindo eleição")
        finally:
            with self.lock:
                self.eleicao_em_andamento = False

    def monitorar(self):
        while not self.parado.wait(INTERVALO_PING):
            with self.lock:
                coordenador = self.coordenador
                ocupado = self.eleicao_em_andamento
            if ocupado or coordenador == self.id:
                continue
            if coordenador is None or self.enviar(coordenador, "PING") != "PONG":
                self.log(f"Coordenador {coordenador} indisponível; eleição automática")
                self.solicitar_eleicao()

    def encerrar(self):
        self.parado.set()
        self.anuncio.set()
        if self.servidor:
            self.servidor.close()
        for thread in list(self.threads):
            if thread is not threading.current_thread():
                thread.join(timeout=TIMEOUT + 0.3)


def main():
    parser = argparse.ArgumentParser(description="Laboratório do algoritmo Bully")
    parser.add_argument("id", type=int, choices=sorted(PROCESSOS))
    parser.add_argument("--automatico", action="store_true", help="ativa PING/PONG e eleição ao iniciar")
    args = parser.parse_args()
    processo = Processo(args.id, args.automatico)
    try:
        processo.iniciar()
        print("Comandos: eleicao | status | sair", flush=True)
        while True:
            comando = input(f"[P{args.id}] comando> ").strip().lower()
            if comando == "eleicao":
                processo.solicitar_eleicao()
            elif comando == "status":
                with processo.lock:
                    coord = f"P{processo.coordenador}" if processo.coordenador else "indefinido"
                    print(f"ID: P{processo.id} | Coordenador: {coord} | Eleição: {processo.eleicao_em_andamento}", flush=True)
            elif comando == "sair":
                break
            else:
                print("Comandos: eleicao | status | sair", flush=True)
    except (EOFError, KeyboardInterrupt):
        pass
    except OSError as erro:
        parser.exit(1, f"Não foi possível iniciar P{args.id}: {erro}\n")
    finally:
        processo.encerrar()


if __name__ == "__main__":
    main()
