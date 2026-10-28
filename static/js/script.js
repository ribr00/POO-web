// Percorre os botões de produto criados pelo template.
document.querySelectorAll(".item-selecionar").forEach((botao) => {
    // Localiza o cartão, o campo de quantidade e a mensagem deste produto.
    const cartao = botao.closest(".item");
    // Encontra o campo de quantidade cujo ID foi informado no botão.
    const campo = document.getElementById(botao.dataset.quantidadeId);
    // Encontra a área do cartão que informa a quantidade selecionada.
    const mensagem = cartao?.querySelector(".item-status");

    // Se o HTML não tiver todos os elementos esperados, não tenta alterar a página.
    if (!cartao || !campo || !mensagem) {
        // Encerra este botão e continua a configuração dos demais.
        return;
    }

    // Atualiza o cartão e a mensagem conforme a quantidade atual.
    const atualizarSelecao = () => {
        // Converte o valor digitado em número para validar e comparar.
        const quantidade = Number(campo.value);
        // Considera selecionado somente um valor numérico maior que zero.
        const selecionado = Number.isFinite(quantidade) && quantidade > 0;

        // Só destaca o produto e mostra a quantidade se ela for maior que zero.
        cartao.classList.toggle("selecionado", selecionado);
        // Mostra a quantidade no cartão ou limpa a mensagem quando não há itens.
        mensagem.textContent = selecionado ? `No pedido: ${quantidade}` : "";
        // Atualiza o nome acessível do botão para leitores de tela.
        botao.setAttribute(
            // Usa o nome acessível apropriado para selecionado ou não selecionado.
            "aria-label",
            // Informa o produto e a quantidade atuais quando já está no pedido.
            selecionado
                ? `${botao.dataset.nomeProduto} no pedido, quantidade ${quantidade}`
                // Oferece uma instrução clara antes de adicionar o produto.
                : `Adicionar ${botao.dataset.nomeProduto} ao pedido`,
        );
    };

    // Ao clicar no produto, seleciona uma unidade se ele ainda não estiver no pedido.
    botao.addEventListener("click", () => {
        // Não substitui uma quantidade que a pessoa já escolheu.
        if (Number(campo.value) === 0) {
            // Seleciona uma unidade como quantidade inicial.
            campo.value = "1";
            // Dispara o evento para atualizar também o destaque visual.
            campo.dispatchEvent(new Event("input", { bubbles: true }));
        }
    });

    // Atualiza o destaque também quando a quantidade muda pelo controle numérico.
    // Observa a digitação e a confirmação do valor no campo.
    campo.addEventListener("input", atualizarSelecao);
    campo.addEventListener("change", atualizarSelecao);
});

// Localiza o seletor que alterna entre consumo no local e pedido para viagem.
const tipoPedido = document.getElementById("tipo_pedido");
// Localiza o grupo de campos que informa a mesa.
const grupoMesa = document.getElementById("grupo-mesa");
// Localiza o seletor da mesa que será enviado no formulário.
const campoMesa = document.getElementById("mesa");

// Só configura a mesa se os três elementos relacionados existirem nesta página.
if (tipoPedido && grupoMesa && campoMesa) {
    // Atualiza a visibilidade e as regras do campo de mesa.
    const atualizarMesa = () => {
        // O consumo local exige uma mesa; viagem não exige.
        const consumoLocal = tipoPedido.value === "mesa";
        // Esconde o grupo da mesa quando o pedido for para viagem.
        grupoMesa.hidden = !consumoLocal;
        // Desativa o seletor escondido para não enviar seu valor.
        campoMesa.disabled = !consumoLocal;
        // Exige a escolha da mesa somente para consumo no local.
        campoMesa.required = consumoLocal;
    };

    // Recalcula o estado do campo sempre que o tipo de pedido for alterado.
    tipoPedido.addEventListener("change", atualizarMesa);
    // Aplica o estado correto também ao carregar a página.
    atualizarMesa();
}