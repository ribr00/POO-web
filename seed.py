"""Insere dados iniciais de demonstração sem repetir os registros existentes."""

# Importa o site para poder abrir uma conexão com o banco.
from app import app
# Importa as tabelas que receberão os dados de demonstração.
from models import Cliente, Mesa, Produto, db


# Produtos de exemplo: nome, preço, categoria e ingredientes opcionais.
PRODUTOS_INICIAIS = [
    ("X-tudo", 18.00, "Hambúrguer", "Pão, hambúrguer, queijo, presunto, bacon, ovo, alface, tomate e maionese."),
    ("X-salada", 12.00, "Hambúrguer", "Pão, hambúrguer, queijo, alface, tomate e maionese."),
    ("Batata frita com bacon", 15.00, "Porção", None),
    ("Batata rústica com calabresas", 16.00, "Porção", None),
    ("Torta de limão", 9.00, "Sobremesa", None),
    ("Brownie", 7.00, "Sobremesa", None),
    ("Coca Cola", 5.00, "Bebidas", None),
    ("Suco natural de laranja", 8.00, "Bebidas", None),
]

# Clientes de teste já existentes no programa de terminal original.
CLIENTES_INICIAIS = [
    ("Lana", "41991929394", "123.321.222-00"),
    ("Rafael", "41999999999", "234.432.333-11"),
]

# Mesas iniciais: número da mesa e capacidade de pessoas.
MESAS_INICIAIS = [
    (1, 4),
    (2, 2),
    (3, 6),
    (4, 10),
    (5, 2),
    (6, 4),
    (7, 2),
    (8, 4),
    (9, 6),
    (10, 8),
    (11, 4),
    (12, 10),
    (13, 6),
    (14, 8),
    (15, 10),
    (16, 3),
    (17, 2),
    (18, 3),
    (19, 8),
    (20, 3),
]


def popular_banco():
    """Cria produtos, clientes e mesas de exemplo que ainda não existem."""
    # Verifica cada produto para que executar este arquivo duas vezes não duplique dados.
    for nome, preco, categoria, ingredientes in PRODUTOS_INICIAIS:
        # Procura o produto pelo nome.
        produto = Produto.query.filter_by(nome=nome).first()
        if produto is None:
            # Se ainda não existe, cria e prepara o produto para gravar.
            db.session.add(
                Produto(
                    nome=nome,
                    preco=preco,
                    categoria=categoria,
                    ingredientes=ingredientes,
                )
            )
        else:
            # Se já existe, atualiza categoria e ingredientes sem criar outro produto.
            produto.categoria = categoria
            produto.ingredientes = ingredientes

    # Cadastra os clientes de demonstração somente se o CPF ainda não estiver no banco.
    for nome, telefone, cpf in CLIENTES_INICIAIS:
        if Cliente.query.filter_by(cpf=cpf).first() is None:
            db.session.add(Cliente(nome=nome, telefone=telefone, cpf=cpf))

    # Cadastra as mesas iniciais sem duplicar as que já existem.
    for numero, capacidade in MESAS_INICIAIS:
        if Mesa.query.filter_by(numero=numero).first() is None:
            db.session.add(Mesa(numero=numero, capacidade=capacidade))

    # Grava no banco todos os novos itens e atualizações preparados acima.
    db.session.commit()


# Este bloco roda apenas se o usuário executar "python seed.py".
if __name__ == "__main__":
    # Abre o contexto Flask para o script conseguir usar banco e modelos.
    with app.app_context():
        # Insere ou atualiza os dados de exemplo.
        popular_banco()
        # Exibe o banco efetivamente usado e os registros visíveis pela aplicação.
        print(f"Banco usado: {db.engine.url.database}")
        print(
            "Registros: "
            f"{Produto.query.count()} produtos, "
            f"{Cliente.query.count()} clientes, "
            f"{Mesa.query.filter_by(ocupada=False).count()} mesas livres, "
            f"{Mesa.query.filter_by(ocupada=True).count()} mesas ocupadas."
        )
