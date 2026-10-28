"""Aplicação web da hamburgueria: recebe telas, valida dados e coordena o banco.

Uma requisição normalmente percorre este caminho:
 navegador -> rota abaixo -> validação -> banco (se necessário) -> template HTML.
"""

# Converte a imagem do QR em texto para o navegador conseguir mostrá-la na página.
import base64
# Compara a senha do caixa de forma mais segura do que comparar textos diretamente.
import hmac
# Lê configurações secretas que serão definidas no Windows antes de iniciar o site.
import os
# Ajuda a retirar pontos, traços e espaços do CPF.
import re
# Cria senhas aleatórias para proteger sessões e QRs.
import secrets
# Fornece a data e a hora em que a saída foi registrada.
from datetime import datetime, timezone
# Cria um arquivo temporário em memória para guardar a imagem do QR.
from io import BytesIO

# Biblioteca que desenha os códigos QR.
import qrcode
# Ferramentas do Flask: site, páginas HTML, formulários, sessões e redirecionamentos.
from flask import Flask, abort, flash, render_template, request, redirect, session, url_for
# Identifica erros de duplicidade ao gravar dados no banco.
from sqlalchemy.exc import IntegrityError
# Permite descobrir as colunas que já existem no banco.
from sqlalchemy import inspect, text

# Importa as tabelas e a conexão com o banco definidas em models.py.
from models import AtendimentoMesa, Cliente, Conta, Mesa, Pedido, PedidoItem, Produto, db

# Cria a aplicação Flask, que recebe as visitas do navegador.
app = Flask(__name__)
# Define que o banco é SQLite e que o arquivo fica na pasta instance do Flask.
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///hamburgueria_real.db"
# Usa uma chave do Windows; se não existir, gera uma temporária para esta execução.
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
# A senha do caixa fica fora do código, em uma variável de ambiente do Windows.
app.config["CASHIER_PASSWORD"] = os.environ.get("CASHIER_PASSWORD")
# Endereço público do site, usado para criar links que funcionem ao ler o QR.
app.config["PUBLIC_BASE_URL"] = os.environ.get("PUBLIC_BASE_URL")
# Conecta o Flask ao banco definido em models.py.
db.init_app(app)

# O contexto permite ao Flask acessar o banco durante a configuração inicial.
with app.app_context():
    # Cria as tabelas que ainda não existem; as que existem não são apagadas.
    db.create_all()
    # Estas verificações são uma atualização simples para bancos antigos.
    # O código compara as colunas atuais com as necessárias e só acrescenta as que faltam.
    # Para alterações maiores ou remoção/renomeação de colunas, use migrações próprias.
    # Lê os nomes das colunas atuais da tabela de produtos.
    colunas_produto = {coluna["name"] for coluna in inspect(db.engine).get_columns("produtos")}
    # Acrescenta a categoria a bancos antigos que ainda não tinham essa coluna.
    if "categoria" not in colunas_produto:
        db.session.execute(
            text("ALTER TABLE produtos ADD COLUMN categoria VARCHAR(50) NOT NULL DEFAULT 'Geral'")
        )
        # Salva a alteração estrutural no banco.
        db.session.commit()
    if "ingredientes" not in colunas_produto:
        db.session.execute(text("ALTER TABLE produtos ADD COLUMN ingredientes VARCHAR(500)"))
        for nome, ingredientes in {
            "X-salada": "Pão, hambúrguer, queijo, alface, tomate e maionese.",
            "X-tudo": "Pão, hambúrguer, queijo, presunto, bacon, ovo, alface, tomate e maionese.",
        }.items():
            db.session.execute(
                text(
                    "UPDATE produtos SET ingredientes = :ingredientes "
                    "WHERE lower(nome) = lower(:nome)"
                ),
                {"nome": nome, "ingredientes": ingredientes},
            )
        db.session.commit()
    # Lê as colunas existentes nos pedidos para atualizar bancos antigos.
    colunas_pedido = {coluna["name"] for coluna in inspect(db.engine).get_columns("pedidos")}
    # Liga cada pedido à mesa correspondente, se o banco ainda não tiver essa coluna.
    if "mesa_id" not in colunas_pedido:
        db.session.execute(text("ALTER TABLE pedidos ADD COLUMN mesa_id INTEGER"))
        db.session.commit()
    # Estas colunas guardam o QR e o horário de saída, para contas e pedidos presenciais.
    for tabela, definicoes in {
        "contas": {
            "qr_token": "VARCHAR(64)",
            "saiu_em": "DATETIME",
        },
        "atendimentos_mesa": {
            "qr_token": "VARCHAR(64)",
            "saiu_em": "DATETIME",
        },
    }.items():
        # Lê as colunas da tabela que está sendo atualizada.
        colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns(tabela)}
        # Acrescenta apenas colunas ausentes para preservar os dados que já existem.
        for nome, tipo in definicoes.items():
            if nome not in colunas:
                db.session.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"))
        # Salva as alterações da tabela atual.
        db.session.commit()


def normalizar_cpf(cpf):
    """Recebe CPF com ou sem pontuação e devolve somente os dígitos."""
    # Mantém apenas os números, aceitando CPF digitado com pontos ou traço.
    return re.sub(r"\D", "", cpf)


def imagem_qr(url):
    """Recebe um endereço e devolve a imagem QR como texto Base64 para o HTML."""
    # Transforma o endereço da saída em uma imagem QR.
    imagem = qrcode.make(url)
    # Abre um arquivo temporário na memória, sem criar arquivo no disco.
    arquivo = BytesIO()
    # Guarda o desenho no formato PNG.
    imagem.save(arquivo, format="PNG")
    # Converte a imagem para texto Base64, que pode ser colocado dentro do HTML.
    return base64.b64encode(arquivo.getvalue()).decode("ascii")


def url_saida_qr(token):
    """Monta o endereço que deve ser codificado no QR de saída."""
    # Cria o caminho do site que será aberto quando a catraca ler o QR.
    caminho = url_for("registrar_saida", token=token)
    # Procura o endereço público configurado para o servidor.
    base_url = app.config.get("PUBLIC_BASE_URL")
    if base_url:
        # Junta o endereço público e o caminho, removendo barras duplicadas.
        return f"{base_url.rstrip('/')}{caminho}"
    # Se não houver endereço público, usa o endereço atual em que o site está rodando.
    return url_for("registrar_saida", token=token, _external=True)


def rota_caixa_requer_login():
    """Interrompe a rota se o caixa não estiver configurado ou autenticado."""
    # Sem senha configurada, bloqueia o caixa em vez de deixá-lo sem proteção.
    if not app.config.get("CASHIER_PASSWORD"):
        abort(503, description="Configure a variável de ambiente CASHIER_PASSWORD para habilitar o caixa.")
    # Só deixa prosseguir quem entrou com a senha do caixa nesta sessão.
    if not session.get("caixa_autenticado"):
        abort(403)


# A rota "/" é a página inicial que o cliente vê.
@app.route('/')
def pagina_inicial():
    """Exibe as opções iniciais, sem consultar nem alterar o banco."""
    # Lê o HTML principal na pasta templates.
    return render_template('base.html')


# A rota "/CLIENTE" recebe o formulário de quem já tem cadastro.
@app.route('/CLIENTE', methods=['GET', 'POST'])
def cliente():
    """Mostra o login no GET e valida o CPF enviado no POST."""
    # POST significa que o cliente enviou o formulário.
    if request.method == 'POST':
        # Lê o CPF e remove pontos e traços.
        cpf = normalizar_cpf(request.form.get("cpf", ""))
        # Procura no banco o cliente com esse CPF.
        cliente_cadastrado = Cliente.query.filter_by(cpf=cpf).first()
        # Se não encontrar, mostra uma mensagem e mantém o cliente na página de login.
        if cliente_cadastrado is None:
            return render_template(
                "cliente.html",
                erro="CPF não encontrado. Confira o número ou faça seu cadastro.",
            ), 404

        # Guarda o identificador do cliente na sessão do navegador.
        session["cliente_id"] = cliente_cadastrado.id
        # Depois do login, manda o cliente para montar o pedido.
        return redirect(url_for("comanda"))

    # GET significa que a pessoa apenas abriu a tela, então mostramos o formulário.
    return render_template('cliente.html')


# A rota "/CADASTRAR" mostra o formulário e salva novos clientes.
@app.route('/CADASTRAR', methods=['GET', 'POST'])
def cadastrar():
    """Mostra o cadastro no GET; no POST, valida e grava um novo cliente."""
    # Só processa os campos quando o formulário é enviado.
    if request.method == 'POST':
        # Lê os campos enviados e remove espaços extras no começo e no fim.
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        # Normaliza o CPF para guardar somente seus 11 números.
        cpf = normalizar_cpf(request.form.get("cpf", ""))

        # Interrompe o cadastro se faltar nome, telefone ou algum número do CPF.
        if not nome or not telefone or len(cpf) != 11:
            abort(400, description="Informe nome, telefone e um CPF com 11 dígitos.")
        # Impede cadastrar outra pessoa usando um CPF que já está salvo.
        if Cliente.query.filter_by(cpf=cpf).first() is not None:
            abort(409, description="Já existe um cadastro com este CPF.")

        # Monta um novo objeto Cliente com os dados do formulário.
        cliente_novo = Cliente(nome=nome, telefone=telefone, cpf=cpf)
        # Prepara o novo cliente para ser gravado.
        db.session.add(cliente_novo)
        try:
            # Grava o cadastro no banco.
            db.session.commit()
        except IntegrityError:
            # Desfaz a tentativa se o banco também detectar CPF duplicado.
            db.session.rollback()
            abort(409, description="Já existe um cadastro com este CPF.")

        # Mantém a pessoa conectada logo depois de criar a conta.
        session["cliente_id"] = cliente_novo.id
        # Depois do cadastro, manda a pessoa para o cardápio.
        return redirect(url_for("comanda"))

    # Para uma visita GET, apenas exibe o formulário de cadastro.
    return render_template('cadastrar.html')


# Clientes conectados podem atualizar o telefone ou excluir o cadastro.
@app.route('/CADASTRO/OPCOES', methods=['GET', 'POST'])
def opcoes_cadastro():
    """Permite ao cliente autenticado atualizar ou excluir seus dados pessoais."""
    # Recupera da sessão o identificador do cliente conectado.
    cliente_id = session.get("cliente_id")
    # Bloqueia o acesso se não houver cliente conectado.
    if cliente_id is None:
        # Retorna erro de acesso proibido para a pessoa não autenticada.
        abort(403)

    # Busca no banco os dados do cliente associado à sessão.
    cliente_atual = db.session.get(Cliente, cliente_id)
    # Verifica se o registro ainda existe no banco.
    if cliente_atual is None:
        # Remove da sessão um identificador que não aponta mais para um cadastro.
        session.pop("cliente_id", None)
        # Informa que o cadastro desta sessão não está mais disponível.
        abort(403, description="O cadastro desta sessão não está mais disponível.")

    # Processa a ação somente quando o formulário for enviado.
    if request.method == "POST":
        # Exige a confirmação do CPF associado ao cliente conectado antes de alterar dados.
        # Lê o CPF digitado e remove pontos, traços, espaços e outros caracteres não numéricos.
        cpf_confirmacao = normalizar_cpf(request.form.get("cpf", ""))
        # Compara o CPF informado com o CPF salvo para o cliente conectado.
        if cpf_confirmacao != cliente_atual.cpf:
            # Interrompe a ação se os CPFs não corresponderem.
            abort(403, description="O CPF informado não corresponde ao cadastro conectado.")

        # Lê o nome da ação enviada pelo formulário.
        acao = request.form.get("acao")
        # Verifica se o cliente pediu para atualizar o telefone.
        if acao == "atualizar_telefone":
            # Lê o novo telefone e remove espaços extras.
            telefone = request.form.get("telefone", "").strip()
            # Exige um telefone preenchido e com no máximo 30 caracteres.
            if not telefone or len(telefone) > 30:
                # Interrompe a atualização e explica o formato aceito.
                abort(400, description="Informe um telefone com até 30 caracteres.")
            # Atualiza o telefone do cliente na sessão atual.
            cliente_atual.telefone = telefone
            # Persiste a alteração no banco de dados.
            db.session.commit()
            # Prepara uma mensagem de sucesso para a próxima página.
            flash("Telefone atualizado com sucesso.")
            # Retorna à página de opções do cadastro.
            return redirect(url_for("opcoes_cadastro"))

        # Verifica se o cliente pediu para excluir o cadastro.
        if acao == "excluir_cadastro":
            # Exige que a confirmação explícita tenha sido marcada no formulário.
            if request.form.get("confirmar_exclusao") != "1":
                # Interrompe a exclusão se a confirmação não foi enviada.
                abort(400, description="Confirme a exclusão do cadastro.")

            # Busca os pedidos anteriores vinculados ao cliente que será excluído.
            pedidos = Pedido.query.filter_by(cliente_id=cliente_atual.id).all()
            # Percorre os pedidos para preservar o histórico sem manter o vínculo pessoal.
            for pedido in pedidos:
                # Remove dos pedidos o vínculo com o cliente excluído.
                pedido.cliente = None
                # Substitui o nome pessoal por um rótulo genérico no histórico.
                pedido.cliente_nome = "Cliente removido"

            # Marca o cadastro para exclusão no banco.
            db.session.delete(cliente_atual)
            # Salva a exclusão e as alterações feitas nos pedidos anteriores.
            db.session.commit()
            # Remove da sessão o identificador do cliente excluído.
            session.pop("cliente_id", None)
            # Remove da sessão o identificador de uma conta que possa estar ativa.
            session.pop("conta_id", None)
            # Prepara uma mensagem explicando que o histórico foi preservado.
            flash("Cadastro excluído. Os pedidos anteriores foram mantidos sem seus dados pessoais.")
            # Redireciona para a página inicial depois da exclusão.
            return redirect(url_for("pagina_inicial"))

        # Rejeita qualquer ação diferente das opções permitidas.
        abort(400, description="Opção de cadastro inválida.")

    # Exibe a página de opções com os dados do cliente conectado.
    return render_template("opcoes_cadastro.html", cliente=cliente_atual)


# A rota "/SEM_CADASTRO" registra que uma pessoa precisa ser atendida pelo garçom.
@app.route('/SEM_CADASTRO', methods=['GET', 'POST'])
def sem_cadastro():
    """Registra no banco uma chamada presencial associada a uma mesa livre."""
    # O formulário só oferece mesas que não estão ocupadas.
    mesas_disponiveis = Mesa.query.filter_by(ocupada=False).order_by(Mesa.numero).all()
    # Após salvar, o redirecionamento traz confirmado=1 para mostrar a confirmação.
    confirmado = request.args.get("confirmado") == "1"
    # POST significa que a pessoa escolheu uma mesa e enviou o formulário.
    if request.method == 'POST':
        # Lê o identificador da mesa e converte o texto para número inteiro.
        mesa_id = request.form.get("mesa", type=int)
        # Busca essa mesa no banco; se não houver número, não encontra mesa.
        mesa = db.session.get(Mesa, mesa_id) if mesa_id else None
        # Não permite registrar uma mesa inexistente ou que já esteja ocupada.
        if mesa is None or mesa.ocupada:
            abort(409, description="Essa mesa não está disponível. Escolha uma mesa livre.")
        # Verifica se já existe uma chamada ainda não encerrada para a mesa.
        atendimento_aberto = AtendimentoMesa.query.filter_by(mesa_id=mesa.id).filter(
            AtendimentoMesa.status != "saida registrada"
        ).first()
        # Evita abrir duas chamadas para a mesma mesa.
        if atendimento_aberto is not None:
            abort(409, description="Já existe um atendimento aberto para essa mesa.")

        # Registra no banco que o cliente pediu atendimento presencial.
        db.session.add(AtendimentoMesa(mesa=mesa))
        # Marca a mesa ocupada até o cliente sair com o QR.
        mesa.ocupada = True
        # Salva a chamada e o estado da mesa juntos.
        db.session.commit()
        # Redireciona para exibir a confirmação sem reenviar o formulário.
        return redirect(url_for("sem_cadastro", confirmado=1))

    # Mostra a tela de atendimento, as mesas livres e se a chamada foi confirmada.
    return render_template(
        'sem_cadastro.html',
        confirmado=confirmado,
        mesas=mesas_disponiveis,
    )


# A rota "/COMANDA" mostra o cardápio e salva os produtos escolhidos.
@app.route('/COMANDA', methods=['GET', 'POST'])
def comanda():
    """Mostra o cardápio no GET e cria pedido/itens/conta no POST."""
    # Busca os produtos do cardápio em ordem de cadastro.
    produtos = Produto.query.order_by(Produto.id).all()
    # Define títulos legíveis e a ordem padrão das categorias do cardápio.
    titulos_categoria = {
        "hambúrguer": "HAMBÚRGUER - LANCHES",
        "porção": "PORÇÕES",
        "sobremesa": "SOBREMESAS",
        "bebidas": "BEBIDAS",
        "drinks": "DRINKS",
    }
    # Junta os produtos pela categoria que já está salva no banco.
    # Cada chave é o texto da categoria; o valor é a lista de produtos daquele grupo.
    produtos_por_categoria = {}
    for produto in produtos:
        categoria = (produto.categoria or "Geral").strip()
        produtos_por_categoria.setdefault(categoria, []).append(produto)

    # Prepara os grupos na ordem combinada para o template mostrar um título por grupo.
    # O template recebe pares (título visível, lista de produtos) para repetir cada seção.
    grupos_produtos = []
    categorias_em_ordem = ["hambúrguer", "porção", "sobremesa", "bebidas", "drinks"]
    for categoria_chave in categorias_em_ordem:
        # Compara sem diferenciar maiúsculas e minúsculas.
        categoria_encontrada = next(
            (
                categoria
                for categoria in produtos_por_categoria
                if categoria.casefold() == categoria_chave
            ),
            None,
        )
        if categoria_encontrada is not None:
            # Retira a categoria do dicionário para não mostrá-la de novo abaixo.
            grupos_produtos.append(
                (
                    titulos_categoria[categoria_chave],
                    produtos_por_categoria.pop(categoria_encontrada),
                )
            )

    # Também mostra categorias personalizadas que não estão na lista padrão.
    for categoria, itens in produtos_por_categoria.items():
        grupos_produtos.append((categoria.upper(), itens))

    # Busca as mesas livres para oferecer no formulário.
    mesas = Mesa.query.filter_by(ocupada=False).order_by(Mesa.numero).all()

    # POST significa que o cliente enviou quantidades e escolheu uma mesa.
    if request.method == 'POST':
        tipo_pedido = request.form.get("tipo_pedido", "mesa")
        if tipo_pedido not in {"mesa", "viagem"}:
            abort(400, description="Selecione consumo no local ou para viagem.")

        mesa = None
        if tipo_pedido == "mesa":
            # Lê o identificador da mesa selecionada no formulário.
            mesa_id = request.form.get("mesa", type=int)
            # Procura a mesa no banco.
            mesa = db.session.get(Mesa, mesa_id) if mesa_id else None
            # Bloqueia mesa inexistente ou ocupada, mesmo que alguém altere o formulário.
            if mesa is None or mesa.ocupada:
                abort(409, description="Essa mesa não está disponível. Escolha uma mesa livre.")

        # Busca o cliente que fez login; quem não tem login fica como pedido sem cadastro.
        cliente_id = session.get("cliente_id")
        cliente_atual = db.session.get(Cliente, cliente_id) if cliente_id else None
        nome_pedido = request.form.get("nome_pedido", "").strip()
        if len(nome_pedido) > 100:
            abort(400, description="O nome deve ter até 100 caracteres.")
        # Cria o pedido e associa o cliente e a mesa, se houver cliente conectado.
        novo_pedido = Pedido(
            cliente=cliente_atual,
            cliente_nome=cliente_atual.nome if cliente_atual else nome_pedido or None,
            mesa=str(mesa.numero) if mesa else "Para viagem",
            mesa_relacionada=mesa,
        )

        # Passa por cada produto do banco para ler a quantidade que chegou do formulário.
        for produto in produtos:
            # O nome do campo usa o ID do produto; produto sem quantidade vale zero.
            quantidade_texto = request.form.get(f"qtd_{produto.id}", "0")
            try:
                # Converte a quantidade digitada de texto para número inteiro.
                quantidade = int(quantidade_texto)
            except ValueError:
                # Avisa se alguém enviou letras ou outro valor que não seja inteiro.
                abort(400, description="A quantidade dos produtos deve ser um número inteiro.")
            # Quantidades negativas não fazem sentido para um pedido.
            if quantidade < 0:
                abort(400, description="A quantidade dos produtos não pode ser negativa.")
            # Só cria uma linha de pedido se o cliente pediu pelo menos uma unidade.
            if quantidade:
                novo_pedido.itens.append(
                    PedidoItem(
                        # Guarda o produto escolhido, a quantidade e a observação.
                        produto=produto,
                        quantidade=quantidade,
                        observacao=request.form.get(f"obs_{produto.id}", "").strip() or None,
                        # Copia o preço atual para o pedido, preservando o valor desta compra.
                        preco_unitario=produto.preco,
                    )
                )

        # Não permite criar uma conta sem nenhum produto.
        if not novo_pedido.itens:
            abort(400, description="Selecione pelo menos um produto para fazer o pedido.")

        # A mesa fica ocupada até que o QR de saída seja lido.
        if mesa is not None:
            mesa.ocupada = True
        # Prepara o pedido para ser salvo no banco.
        db.session.add(novo_pedido)
        # Grava o pedido para obter seu ID antes de criar a conta relacionada.
        db.session.flush()
        # Toda compra tem uma conta, inicialmente pendente de pagamento.
        conta = Conta(pedido=novo_pedido)
        db.session.add(conta)
        # Grava o pedido, os itens, a mesa ocupada e a conta.
        db.session.commit()
        # Guarda o número da conta na sessão para só este navegador acessá-la.
        session["conta_id"] = conta.id
        # Manda o cliente conferir o total e selecionar o pagamento.
        return redirect(url_for("pagamento", conta_id=conta.id))

    cliente_id = session.get("cliente_id")
    cliente_atual = db.session.get(Cliente, cliente_id) if cliente_id else None

    # GET mostra cardápio e mesas livres na tela de comanda.
    # Envia a lista original para validar o pedido e os grupos para desenhar o cardápio.
    return render_template(
        'comanda.html',
        produtos=produtos,
        grupos_produtos=grupos_produtos,
        mesas=mesas,
        cliente=cliente_atual,
    )


# A rota "/PAGAR/<id>" mostra o resumo e registra uma forma de pagamento.
@app.route('/PAGAR/<int:conta_id>', methods=['GET', 'POST'])
def pagamento(conta_id):
    """Exibe o total e registra a escolha demonstrativa de forma de pagamento."""
    # Busca a conta pelo número que aparece no endereço.
    conta = db.session.get(Conta, conta_id)
    # Se não existir uma conta com esse número, mostra erro 404.
    if conta is None:
        abort(404)
    # Impede outro navegador de acessar a conta de uma pessoa.
    if session.get("conta_id") != conta.id:
        abort(403)
    # Depois da saída, volta para o início.
    if conta.saiu_em is not None:
        return redirect(url_for("pagina_inicial"))
    # Se já pagou, mostra novamente o QR, sem cobrar ou gerar outro.
    if conta.status == "pago":
        return redirect(url_for("qr_saida_online", conta_id=conta.id))
    # Só uma conta pendente pode receber pagamento.
    if conta.status != "pendente":
        abort(409, description="Essa conta não está aguardando pagamento.")

    # Calcula o total somando quantidade vezes preço de cada item.
    total = conta.total
    # Traduz os valores enviados pelo formulário para nomes que serão salvos.
    formas_pagamento = {
        "pix": "Pix",
        "debito": "Cartão de débito",
        "credito": "Cartão de crédito",
    }

    # POST significa que o cliente confirmou uma forma de pagamento.
    if request.method == "POST":
        # Lê a opção selecionada.
        forma = request.form.get("forma_pagamento", "")
        # Confere no servidor que a opção é uma das três permitidas.
        if forma not in formas_pagamento:
            abort(400, description="Selecione uma forma de pagamento válida.")

        # Registra a forma e marca a conta como paga (simulação, sem cobrar de verdade).
        conta.forma_pagamento = formas_pagamento[forma]
        conta.status = "pago"
        # Cria um código secreto e único para o QR de saída desta conta.
        conta.qr_token = secrets.token_urlsafe(32)
        # Salva o pagamento e o código do QR.
        db.session.commit()
        # Depois do pagamento, mostra o QR pessoal do cliente.
        return redirect(url_for("qr_saida_online", conta_id=conta.id))

    # GET exibe os itens, o total e o formulário de pagamento.
    return render_template("pagamento.html", conta=conta, total=total)


# Esta tela só mostra o QR pago ao mesmo cliente que criou aquela conta.
@app.route('/PAGAMENTO/QR/<int:conta_id>')
def qr_saida_online(conta_id):
    """Mostra o QR online somente para a sessão dona de uma conta paga."""
    # Busca a conta que será mostrada.
    conta = db.session.get(Conta, conta_id)
    if conta is None:
        abort(404)
    # O QR não pode ser visto por quem não tem a conta na sessão.
    if session.get("conta_id") != conta.id:
        abort(403)
    # Só mostra o QR se pagou e ainda não saiu do restaurante.
    if conta.status != "pago" or not conta.qr_token or conta.saiu_em is not None:
        abort(403)
    # Monta o endereço individual que será codificado na imagem QR.
    url_saida = url_saida_qr(conta.qr_token)
    # Renderiza a página QR com a imagem, o número da mesa e o tipo de fluxo.
    return render_template(
        "qr_saida.html",
        imagem_qr=imagem_qr(url_saida),
        mesa=conta.pedido.mesa,
        online=True,
    )


# A rota "/CAIXA" pede a senha do caixa para proteger as ações presenciais.
@app.route('/CAIXA', methods=['GET', 'POST'])
def caixa_login():
    """Mostra o login do caixa ou valida a senha enviada pelo formulário."""
    # Lê a senha configurada fora do código.
    senha_caixa = app.config.get("CASHIER_PASSWORD")
    # Sem senha, não deixa a tela do caixa funcionar sem proteção.
    if not senha_caixa:
        abort(503, description="Configure a variável de ambiente CASHIER_PASSWORD para habilitar o caixa.")

    # Quem já entrou não precisa digitar a senha novamente.
    if session.get("caixa_autenticado"):
        return redirect(url_for("caixa_atendimentos"))
    # No começo ainda não há mensagem de erro.
    erro = None
    # POST significa que o caixa digitou e enviou uma senha.
    if request.method == "POST":
        # Lê a senha digitada.
        senha = request.form.get("senha", "")
        # Compara com a senha configurada sem uma comparação simples de textos.
        if hmac.compare_digest(senha, senha_caixa):
            # Marca esta sessão do navegador como autenticada para o caixa.
            session["caixa_autenticado"] = True
            # Após entrar, mostra os atendimentos presenciais.
            return redirect(url_for("caixa_atendimentos"))
        # Se a senha não bate, mostra uma mensagem na tela.
        erro = "Senha incorreta."
    # Exibe o formulário de senha, incluindo a mensagem se a senha falhou.
    return render_template("caixa_login.html", erro=erro)


# O caixa pode encerrar a sessão usando o botão "Sair".
@app.route('/CAIXA/SAIR', methods=['POST'])
def caixa_sair():
    """Remove da sessão a marca de autenticação do caixa."""
    # Confere primeiro se quem pediu para sair é mesmo o caixa conectado.
    rota_caixa_requer_login()
    # Apaga a informação de login do caixa desta sessão.
    session.pop("caixa_autenticado", None)
    # Volta para a tela de login.
    return redirect(url_for("caixa_login"))


# Esta página lista clientes sem cadastro que aguardam atendimento presencial.
@app.route('/CAIXA/ATENDIMENTOS')
def caixa_atendimentos():
    """Lista para o caixa os atendimentos presenciais que ainda aguardam pagamento."""
    # Só permite acesso ao caixa autenticado.
    rota_caixa_requer_login()
    # Busca os atendimentos que ainda aguardam pagamento no caixa.
    atendimentos = (
        AtendimentoMesa.query
        .filter(AtendimentoMesa.status == "aguardando garçom")
        .order_by(AtendimentoMesa.id)
        .all()
    )
    # Envia os atendimentos encontrados para a tela HTML do caixa.
    return render_template("caixa.html", atendimentos=atendimentos)


# O caixa usa esta rota depois de receber o pagamento presencial.
@app.route('/CAIXA/ATENDIMENTO/<int:atendimento_id>/PAGAR', methods=['POST'])
def caixa_confirmar_pagamento(atendimento_id):
    """Marca um atendimento presencial como pago e cria seu token de QR."""
    # Protege a operação: cliente comum não pode confirmar pagamento presencial.
    rota_caixa_requer_login()
    # Busca a chamada de atendimento pelo identificador.
    atendimento = db.session.get(AtendimentoMesa, atendimento_id)
    if atendimento is None:
        abort(404)
    # Evita confirmar duas vezes algo que já foi pago ou encerrado.
    if atendimento.status != "aguardando garçom":
        abort(409, description="Esse atendimento já foi pago ou encerrado.")

    # Marca a chamada como paga e cria seu código QR exclusivo.
    atendimento.status = "pago"
    atendimento.qr_token = secrets.token_urlsafe(32)
    # Salva a informação antes de mostrar o QR ao caixa.
    db.session.commit()
    # Abre a tela que o caixa pode mostrar ou entregar ao cliente.
    return redirect(url_for("caixa_qr_saida", atendimento_id=atendimento.id))


# O caixa consulta esta tela para mostrar novamente o QR de um atendimento pago.
@app.route('/CAIXA/ATENDIMENTO/<int:atendimento_id>/QR')
def caixa_qr_saida(atendimento_id):
    """Exibe novamente o QR presencial de um atendimento que já foi pago."""
    # Protege o QR para que apenas o caixa conectado possa vê-lo.
    rota_caixa_requer_login()
    # Procura o atendimento registrado para a mesa.
    atendimento = db.session.get(AtendimentoMesa, atendimento_id)
    if atendimento is None:
        abort(404)
    # QR de saída só pode existir depois do pagamento.
    if atendimento.status != "pago" or not atendimento.qr_token:
        abort(409, description="O QR de saída só é gerado após confirmar o pagamento.")

    # Monta o endereço que a catraca abrirá ao ler o QR.
    url_saida = url_saida_qr(atendimento.qr_token)
    # Mostra o mesmo template de QR usado no pagamento online.
    return render_template(
        "qr_saida.html",
        imagem_qr=imagem_qr(url_saida),
        mesa=atendimento.mesa.numero,
        online=False,
    )


# A catraca/navegador abre esta rota ao ler o QR individual do cliente.
@app.route('/SAIDA/<token>')
def registrar_saida(token):
    """Valida o token do QR, registra a saída e libera a mesa correspondente."""
    # Primeiro procura um atendimento presencial pago que use este código.
    atendimento = AtendimentoMesa.query.filter_by(qr_token=token, status="pago").first()
    # Se não for presencial, procura uma conta online paga e ainda não encerrada.
    conta = Conta.query.filter_by(qr_token=token, status="pago", saiu_em=None).first()
    # QR desconhecido, não pago ou já usado não pode liberar nenhuma mesa.
    if atendimento is None and conta is None:
        return render_template("saida.html", valido=False), 404

    # Se o QR veio do caixa, registra a saída no atendimento presencial.
    if atendimento is not None:
        atendimento.status = "saida registrada"
        # Guarda a data e hora em UTC para registrar quando aconteceu a saída.
        atendimento.saiu_em = datetime.now(timezone.utc)
        # A mesa fica livre para o próximo cliente.
        atendimento.mesa.ocupada = False
        # Guarda o número para mostrá-lo na confirmação final.
        numero_mesa = atendimento.mesa.numero
    else:
        # Se o QR veio de pedido online, registra o horário da saída da conta.
        conta.saiu_em = datetime.now(timezone.utc)
        # Libera a mesa vinculada ao pedido, se ela estiver associada.
        if conta.pedido.mesa_relacionada is not None:
            conta.pedido.mesa_relacionada.ocupada = False
        # O pedido online guarda o número da mesa como texto.
        numero_mesa = conta.pedido.mesa

    # Salva a saída e a liberação da mesa.
    db.session.commit()
    # Mostra a confirmação de que a saída foi registrada com sucesso.
    return render_template("saida.html", valido=True, mesa=numero_mesa)


# Só inicia o servidor quando este arquivo é executado diretamente.
if __name__ == "__main__":
    # Abre o site na porta 5000; 0.0.0.0 permite acesso de outros aparelhos na rede.
    app.run(host="0.0.0.0", port=5000)
