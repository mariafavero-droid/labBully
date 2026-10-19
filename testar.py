"""Testes de integração com cinco subprocessos reais e sockets TCP locais."""
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def executar(automatico=False):
    processos, arquivos = {}, []
    sufixo = "automatico" if automatico else "manual"

    def iniciar(pid):
        arquivo = (RAIZ / "evidencias" / f"{sufixo}-P{pid}.log").open("a")
        arquivos.append(arquivo)
        processos[pid] = subprocess.Popen(
            [sys.executable, "-u", str(RAIZ / "processo.py"), str(pid)]
            + (["--automatico"] if automatico else []),
            stdin=subprocess.PIPE, stdout=arquivo, stderr=subprocess.STDOUT, text=True)

    def comando(pid, texto):
        processos[pid].stdin.write(texto + "\n")
        processos[pid].stdin.flush()

    def parar(pid, abrupto=False):
        processo = processos.pop(pid)
        if abrupto:
            processo.kill()
        else:
            processo.stdin.write("sair\n")
            processo.stdin.flush()
        processo.wait(timeout=10)
        try:
            processo.stdin.close()
        except BrokenPipeError:
            pass

    def aguardar(vencedor):
        limite = time.monotonic() + 15
        while time.monotonic() < limite:
            offsets = {pid: (RAIZ / "evidencias" / f"{sufixo}-P{pid}.log").stat().st_size for pid in processos}
            for pid in processos:
                assert processos[pid].poll() is None, f"P{pid} encerrou inesperadamente"
                comando(pid, "status")
            time.sleep(0.25)
            if all(f"Coordenador: P{vencedor} | Eleição: False" in
                   (RAIZ / "evidencias" / f"{sufixo}-P{pid}.log").read_bytes()[offsets[pid]:].decode()
                   for pid in processos):
                return
        raise AssertionError(f"Não houve convergência para P{vencedor}")

    try:
        for pid in range(1, 6):
            iniciar(pid)
        time.sleep(0.5)
        if automatico:
            aguardar(5)
            parar(5, abrupto=True)
            aguardar(4)
            iniciar(5)
            aguardar(5)
            print("PASSOU: inicialização, falha abrupta e recuperação automáticas")
        else:
            comando(5, "eleicao")
            aguardar(5)
            print("PASSOU: experimento 1, eleição inicial -> P5")
            parar(5)
            comando(2, "eleicao")
            aguardar(4)
            print("PASSOU: experimento 2, falha de P5 -> P4")
            iniciar(5)
            time.sleep(0.3)
            comando(5, "eleicao")
            aguardar(5)
            print("PASSOU: experimento 3, recuperação de P5 -> P5")
            parar(5)
            comando(4, "eleicao")
            aguardar(4)
            parar(2)
            iniciar(2)
            time.sleep(0.3)
            comando(2, "eleicao")
            aguardar(4)
            print("PASSOU: experimento 4, recuperação de P2 mantém P4")
            parar(4)
            comando(1, "eleicao")
            aguardar(3)
            print("PASSOU: experimento 5, apenas P1/P2/P3 -> P3")
            for pid in processos:
                comando(pid, "eleicao")
            aguardar(3)
            print("PASSOU: eleições simultâneas convergem para P3")
    finally:
        for pid in list(processos):
            parar(pid, abrupto=True)
        for arquivo in arquivos:
            arquivo.close()


if __name__ == "__main__":
    (RAIZ / "evidencias").mkdir(exist_ok=True)
    for caminho in (RAIZ / "evidencias").glob("*.log"):
        caminho.unlink()
    executar()
    executar(automatico=True)
