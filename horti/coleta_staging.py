"""Coleta desligada. O índice de ano e mês fica em horti/indice e não baixa nada."""
ATIVO = False


def executar(*_args, **_kwargs):
    raise SystemExit("coleta desligada")
