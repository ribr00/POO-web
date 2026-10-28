// Percorre os botões de produto criados pelo template.
document.querySelectorAll(".item-selecionar").forEach((botao) => {
    // Localiza o cartão, o campo de quantidade e a mensagem deste produto.
    const cartao = botao.closest(".item");
    const campo = document.getElementById(botao.dataset.quantidadeId);
    const mensagem = cartao?.querySelector(".item-status");

    // Se o HTML não tiver todos os elementos esperados, não tenta alterar a página.
    if (!cartao || !campo || !mensagem) {
        return;
    }

    // Atualiza o cartão e a mensagem conforme a quantidade atual.
    const atualizarSelecao = () => {
        const quantidade = Number(campo.value);
        const selecionado = Number.isFinite(quantidade) && quantidade > 0;

        // Só destaca o produto e mostra a quantidade se ela for maior que zero.
        cartao.classList.toggle("selecionado", selecionado);
        mensagem.textContent = selecionado ? `No pedido: ${quantidade}` : "";
        // Atualiza o nome acessível do botão para leitores de tela.
        botao.setAttribute(
            "aria-label",
            selecionado
                ? `${botao.dataset.nomeProduto} no pedido, quantidade ${quantidade}`
                : `Adicionar ${botao.dataset.nomeProduto} ao pedido`,
        );
    };

    // Ao clicar no produto, seleciona uma unidade se ele ainda não estiver no pedido.
    botao.addEventListener("click", () => {
        if (Number(campo.value) === 0) {
            campo.value = "1";
            campo.dispatchEvent(new Event("input", { bubbles: true }));
        }
    });

    // Atualiza o destaque também quando a quantidade muda pelo controle numérico.
    campo.addEventListener("input", atualizarSelecao);
    campo.addEventListener("change", atualizarSelecao);
});

const tipoPedido = document.getElementById("tipo_pedido");
const grupoMesa = document.getElementById("grupo-mesa");
const campoMesa = document.getElementById("mesa");

if (tipoPedido && grupoMesa && campoMesa) {
    const atualizarMesa = () => {
        const consumoLocal = tipoPedido.value === "mesa";
        grupoMesa.hidden = !consumoLocal;
        campoMesa.disabled = !consumoLocal;
        campoMesa.required = consumoLocal;
    };

    tipoPedido.addEventListener("change", atualizarMesa);
    atualizarMesa();
}