"""Libera mesas após testes, encerrando os atendimentos e QR codes de teste."""

from datetime import datetime, timezone

# Importa a aplicação para acessar a configuração do banco de dados.
from app import app
# Importa os modelos que representam atendimentos, contas, mesas e pedidos.
from models import AtendimentoMesa, Conta, Mesa, Pedido, db


# Define a rotina que encerra fluxos de teste e libera as mesas ocupadas.
def liberar_mesas_de_teste():
    """Marca como encerrados os fluxos de mesa abertos e libera todas as mesas."""
    # Usa o mesmo instante para registrar o encerramento de todos os fluxos.
    agora = datetime.now(timezone.utc)

    # Busca atendimentos presenciais que ainda não registraram a saída.
    atendimentos = AtendimentoMesa.query.filter(
        AtendimentoMesa.status != "saida registrada"
    ).all()
    # Encerra cada atendimento encontrado e registra quando ocorreu a saída.
    for atendimento in atendimentos:
        atendimento.status = "saida registrada"
        atendimento.saiu_em = agora

    # Busca contas de pedidos associados a mesas cuja saída ainda não foi registrada.
    contas = (
        Conta.query.join(Pedido, Conta.pedido_id == Pedido.id)
        .filter(Pedido.mesa_id.isnot(None), Conta.saiu_em.is_(None))
        .all()
    )
    # Registra o encerramento das contas de mesa encontradas.
    for conta in contas:
        conta.saiu_em = agora

    # Busca todas as mesas que ainda aparecem como ocupadas.
    mesas = Mesa.query.filter_by(ocupada=True).all()
    # Marca como livres as mesas encontradas.
    for mesa in mesas:
        mesa.ocupada = False

    # Persiste em uma única transação todas as alterações feitas.
    db.session.commit()
    # Retorna quantos registros foram alterados em cada categoria.
    return len(mesas), len(atendimentos), len(contas)


# Executa o procedimento de confirmação somente quando este arquivo é iniciado diretamente.
if __name__ == "__main__":
    # Exige uma confirmação digitada para evitar liberar mesas por engano.
    confirmacao = input(
        "Use somente após confirmar que estes dados são de teste. "
        "Digite LIBERAR para encerrar os fluxos e liberar todas as mesas: "
    ).strip()
    # Cancela a operação quando a confirmação não corresponde exatamente ao esperado.
    if confirmacao != "LIBERAR":
        raise SystemExit("Operação cancelada; nenhuma mesa foi alterada.")

    # Abre o contexto necessário para consultar e atualizar o banco da aplicação.
    with app.app_context():
        # Executa a limpeza e recebe as quantidades de registros afetados.
        mesas, atendimentos, contas = liberar_mesas_de_teste()
        # Informa ao usuário o resultado da operação.
        print(
            f"Mesas liberadas: {mesas}; atendimentos de teste encerrados: "
            f"{atendimentos}; contas de mesa encerradas: {contas}."
        )
