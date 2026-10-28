"""Modelos que descrevem as tabelas e relações do banco de dados do site.

Cada classe é uma tabela; cada instância é um registro; cada coluna é um campo.
"""

# Importa a ferramenta que transforma classes Python em tabelas do banco.
from flask_sqlalchemy import SQLAlchemy

# Cria a conexão compartilhada; app.py conecta essa variável ao site.
db = SQLAlchemy()


# Cada objeto Cliente representa uma pessoa cadastrada na tabela "clientes".
class Cliente(db.Model):
    """Dados de uma pessoa que pode fazer login com CPF."""
    # Define o nome que a tabela terá dentro do banco.
    __tablename__ = "clientes"

    # ID numérico único que o banco cria para cada cliente.
    id = db.Column(db.Integer, primary_key=True)
    # Nome obrigatório, limitado a 100 caracteres.
    nome = db.Column(db.String(100), nullable=False)
    # Telefone obrigatório, limitado a 30 caracteres.
    telefone = db.Column(db.String(30), nullable=False)
    # CPF obrigatório e único; o índice deixa a busca por CPF mais rápida.
    cpf = db.Column(db.String(11), nullable=False, unique=True, index=True)


# Cada objeto Produto representa um item disponível no cardápio.
class Produto(db.Model):
    """Produto que aparece no cardápio, com preço, categoria e ingredientes."""
    # Nome da tabela de produtos no banco.
    __tablename__ = 'produtos'
    
    # ID único de cada produto.
    id = db.Column(db.Integer, primary_key=True)
    # Nome obrigatório do produto.
    nome = db.Column(db.String(100), nullable=False)
    # Preço obrigatório do produto.
    preco = db.Column(db.Float, nullable=False)
    # Categoria do produto; se não for informada, será "Geral".
    categoria = db.Column(db.String(50), nullable=False, default="Geral")
    # Ingredientes exibidos como descrição opcional no cardápio.
    ingredientes = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        # Forma curta de identificar o produto durante a depuração.
        return f'<Produto {self.nome}>'


# Cada objeto Mesa guarda número, capacidade e se a mesa está ocupada.
class Mesa(db.Model):
    """Mesa física e seu estado atual de ocupação."""
    # Nome da tabela no banco.
    __tablename__ = "mesas"

    # ID interno da mesa.
    id = db.Column(db.Integer, primary_key=True)
    # Número que o cliente vê; não pode se repetir.
    numero = db.Column(db.Integer, nullable=False, unique=True)
    # Quantas pessoas podem sentar nessa mesa.
    capacidade = db.Column(db.Integer, nullable=False)
    # Verdadeiro quando alguém está usando a mesa; começa livre.
    ocupada = db.Column(db.Boolean, nullable=False, default=False)


# Guarda a chamada de atendimento presencial feita por alguém sem cadastro.
class AtendimentoMesa(db.Model):
    """Chamada presencial de uma mesa, acompanhada até a saída."""
    # Nome da tabela no banco.
    __tablename__ = "atendimentos_mesa"

    # Identificador único desta chamada.
    id = db.Column(db.Integer, primary_key=True)
    # ID da mesa relacionada; aponta para a tabela "mesas".
    mesa_id = db.Column(db.Integer, db.ForeignKey("mesas.id"), nullable=False)
    # Situação: aguardando garçom, pago ou saída registrada.
    status = db.Column(db.String(30), nullable=False, default="aguardando garçom")
    # Código secreto e individual que será colocado no QR de saída.
    qr_token = db.Column(db.String(64), nullable=True)
    # Data e hora em que a catraca/navegador registrou a saída.
    saiu_em = db.Column(db.DateTime, nullable=True)

    # Permite acessar a mesa completa usando atendimento.mesa.
    mesa = db.relationship("Mesa")


# Cada objeto Pedido representa um pedido feito pelo cliente no site.
class Pedido(db.Model):
    """Cabeçalho do pedido; seus produtos ficam em PedidoItem."""
    # Nome da tabela.
    __tablename__ = "pedidos"

    # Identificador único do pedido.
    id = db.Column(db.Integer, primary_key=True)
    # ID do cliente cadastrado; pode ficar vazio para pedido sem cadastro.
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    # Guarda o nome do cliente caso ele não tenha cadastro.
    cliente_nome = db.Column(db.String(100), nullable=True)
    # Número da mesa em formato de texto para exibir/imprimir o pedido.
    mesa = db.Column(db.String(20), nullable=False)
    # ID da mesa relacionada na tabela de mesas.
    mesa_id = db.Column(db.Integer, db.ForeignKey("mesas.id"), nullable=True)

    # Permite consultar o cliente associado ao pedido.
    cliente = db.relationship("Cliente")
    # Permite consultar a mesa usando pedido.mesa_relacionada.
    mesa_relacionada = db.relationship("Mesa")
    # Lista de itens que compõem este pedido.
    itens = db.relationship(
        "PedidoItem",
        back_populates="pedido",
        # Se o pedido for apagado, seus itens também são apagados.
        cascade="all, delete-orphan",
    )
    # Cada pedido pode ter uma única conta; uselist=False indica um objeto só.
    conta = db.relationship("Conta", back_populates="pedido", uselist=False)


# Cada objeto PedidoItem é uma linha: produto + quantidade + observação no pedido.
class PedidoItem(db.Model):
    """Uma linha do pedido: produto, quantidade, observação e preço registrado."""
    # Nome da tabela.
    __tablename__ = "pedido_itens"

    # Identificador único da linha do pedido.
    id = db.Column(db.Integer, primary_key=True)
    # ID do pedido ao qual esta linha pertence.
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False)
    # ID do produto escolhido no cardápio.
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    # Quantidade desse produto pedida pelo cliente.
    quantidade = db.Column(db.Integer, nullable=False)
    # Observação opcional, por exemplo "sem cebola".
    observacao = db.Column(db.String(250), nullable=True)
    # Copia o preço no momento da compra, mesmo se o preço do cardápio mudar depois.
    preco_unitario = db.Column(db.Float, nullable=False)

    # Permite acessar o pedido a que esta linha pertence.
    pedido = db.relationship("Pedido", back_populates="itens")
    # Permite acessar os detalhes do produto desta linha.
    produto = db.relationship("Produto")


# Conta guarda pagamento e QR do pedido online.
class Conta(db.Model):
    """Conta do pedido, incluindo status de pagamento e QR de saída."""
    # Nome da tabela.
    __tablename__ = "contas"

    # Identificador único da conta.
    id = db.Column(db.Integer, primary_key=True)
    # ID do pedido que esta conta cobra; unique garante uma conta por pedido.
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False, unique=True)
    # Situação da conta: começa pendente e muda depois do pagamento.
    status = db.Column(db.String(20), nullable=False, default="pendente")
    # Pix, cartão de débito ou crédito, conforme escolha no formulário.
    forma_pagamento = db.Column(db.String(30), nullable=True)
    # Código secreto que será colocado no QR individual de saída.
    qr_token = db.Column(db.String(64), nullable=True)
    # Data e hora em que a saída foi registrada.
    saiu_em = db.Column(db.DateTime, nullable=True)

    # Permite acessar o pedido desta conta com conta.pedido.
    pedido = db.relationship("Pedido", back_populates="conta")

    @property
    def total(self):
        # Soma quantidade vezes preço de cada item para obter o total da conta.
        return sum(item.quantidade * item.preco_unitario for item in self.pedido.itens)