"""Libera mesas após testes, encerrando os atendimentos e QR codes de teste."""

from datetime import datetime, timezone

from app import app
from models import AtendimentoMesa, Conta, Mesa, Pedido, db


def liberar_mesas_de_teste():
    """Marca como encerrados os fluxos de mesa abertos e libera todas as mesas."""
    agora = datetime.now(timezone.utc)

    atendimentos = AtendimentoMesa.query.filter(
        AtendimentoMesa.status != "saida registrada"
    ).all()
    for atendimento in atendimentos:
        atendimento.status = "saida registrada"
        atendimento.saiu_em = agora

    contas = (
        Conta.query.join(Pedido, Conta.pedido_id == Pedido.id)
        .filter(Pedido.mesa_id.isnot(None), Conta.saiu_em.is_(None))
        .all()
    )
    for conta in contas:
        conta.saiu_em = agora

    mesas = Mesa.query.filter_by(ocupada=True).all()
    for mesa in mesas:
        mesa.ocupada = False

    db.session.commit()
    return len(mesas), len(atendimentos), len(contas)


if __name__ == "__main__":
    confirmacao = input(
        "Use somente após confirmar que estes dados são de teste. "
        "Digite LIBERAR para encerrar os fluxos e liberar todas as mesas: "
    ).strip()
    if confirmacao != "LIBERAR":
        raise SystemExit("Operação cancelada; nenhuma mesa foi alterada.")

    with app.app_context():
        mesas, atendimentos, contas = liberar_mesas_de_teste()
        print(
            f"Mesas liberadas: {mesas}; atendimentos de teste encerrados: "
            f"{atendimentos}; contas de mesa encerradas: {contas}."
        )
