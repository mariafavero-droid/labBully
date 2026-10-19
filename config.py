"""Endereços TCP e tempos (em segundos) do laboratório."""
PROCESSOS = {pid: ("127.0.0.1", 5000 + pid) for pid in range(1, 6)}
TIMEOUT = 0.5
INTERVALO_PING = 1.0
ESPERA_COORDENADOR = 4.0
