"""Gera PDFs de briefing de teste no formato 'Direcionamento de demandas' da Agency."""

from fpdf import FPDF

OUTPUT_DIR = "docs/test-briefings"

BRIEFINGS_DEMO = [
    {
        "filename": "briefing-client_delta-instagram-abril2026.pdf",
        "answers": {
            "1": "Campanha Instagram Abril 2026 - ClientDelta",
            "2": (
                "12 posts para feed (4 posts estaticos, 4 carrosseis, 4 reels), "
                "8 stories ao longo do mes, 2 collabs com influenciadoras."
            ),
            "3": "Instagram (feed, stories, reels e collabs).",
            "4": (
                "Consolidar a colecao outono/inverno lancada em marco e iniciar "
                "a comunicacao pre-Dia das Maes (maio). Aumentar o engajamento "
                "com a comunidade e impulsionar vendas no e-commerce com foco "
                "em presentes e looks para o outono."
            ),
            "5": (
                "Mulheres de 25-40 anos, classe B/A, que acompanham tendencias "
                "de moda e buscam pecas versateis para o dia a dia e ocasioes "
                "especiais. Publico secundario: filhas buscando presentes para "
                "o Dia das Maes."
            ),
            "6": (
                "Mensagem-chave: 'ClientDelta - Presente perfeito para quem voce ama'. "
                "Acao esperada: acessar o e-commerce pelo link na bio, montar "
                "kits de presente e aproveitar frete gratis acima de R$299."
            ),
            "7": (
                "Manter a estetica minimalista e sofisticada da campanha de marco. "
                "Paleta de cores outonais: burgundy, caramelo, off-white, marrom, "
                "com toques de rosa antigo para a campanha de Dia das Maes. "
                "Referencia: @amaro e @mariafilo. "
                "Fotos do lookbook + fotos lifestyle com modelos reais serao fornecidas. "
                "Reels devem ter transicoes suaves e musica trending."
            ),
            "8": "Feed: 1080x1350px (retrato). Reels: 1080x1920px. Stories: 1080x1920px.",
            "9": "28/03/2026 (para comecar a publicar em 01/04).",
            "10": (
                "Semana 1 (01-07/04): ultimos looks da colecao outono/inverno com "
                "depoimentos de clientes. Semana 2 (08-14/04): lancamento da linha "
                "'Essenciais' com pecas basicas premium. Semana 3 (15-21/04): Pascoa "
                "(20/04) com campanha especial 'Vista-se de chocolate' e desconto de 20 porcento. "
                "Semana 4 (22-30/04): aquecimento Dia das Maes com guia de presentes "
                "e kits exclusivos. Codigo de desconto: ClientDeltaMAES. "
                "Collabs com @luisaaccorsi e @thaisdemare (confirmadas). "
                "Todos os reels devem ter legenda e musica trending. "
                "Nao mencionar concorrentes. Manter codigo ClientDelta15 ativo do mes anterior."
            ),
        },
    },
]

BRIEFINGS = [
    {
        "filename": "briefing-client_alpha-instagram-marco2026.pdf",
        "answers": {
            "1": "Campanha Instagram Marco 2026 - ClientAlpha",
            "2": (
                "8 posts para feed (4 posts estaticos, 2 carrosseis, 2 reels), "
                "4 stories ao longo do mes."
            ),
            "3": "Instagram (feed e stories).",
            "4": (
                "Fortalecer a presenca digital da ClientAlpha no Instagram durante "
                "marco, destacando a qualidade das peliculas e acessorios "
                "para celular. Aproveitar o Dia do Consumidor (15/03) para "
                "uma campanha promocional."
            ),
            "5": (
                "Publico final: usuarios de smartphones que buscam protecao "
                "de tela premium. Idade 18-45 anos."
            ),
            "6": (
                "Mensagem-chave: 'Protecao premium para seu smartphone'. "
                "Acao esperada: visitar o site e encontrar um revendedor proximo."
            ),
            "7": (
                "Manter a identidade visual da marca (azul escuro e branco). "
                "Estilo clean e tecnologico. Referencia: posts anteriores "
                "da @hpaboratory no Instagram."
            ),
            "8": "Feed: 1080x1080px. Stories: 1080x1920px. Reels: 1080x1920px.",
            "9": "28/02/2026 (para comecar a publicar em 01/03).",
            "10": (
                "Incluir o Dia do Consumidor (15/03) como tema de pelo menos "
                "2 posts. Usar fotos dos produtos mais vendidos. "
                "Evitar mencionar precos nos posts organicos."
            ),
        },
    },
    {
        "filename": "briefing-hotel10-instagram-abril2026.pdf",
        "answers": {
            "1": "Conteudo Instagram Abril 2026 - ClientBeta",
            "2": (
                "12 posts para feed (5 posts estaticos, 4 carrosseis, 3 reels), "
                "8 stories ao longo do mes."
            ),
            "3": "Instagram (feed e stories).",
            "4": (
                "Promover as experiencias do ClientBeta durante o outono, "
                "destacando a gastronomia, o spa e os pacotes de fim de semana. "
                "Aumentar reservas diretas pelo Instagram."
            ),
            "5": (
                "Casais e familias de classe media-alta que buscam "
                "experiencias de hospedagem premium no sul do Brasil. "
                "Idade 30-55 anos."
            ),
            "6": (
                "Mensagem-chave: 'Seu refuugio de outono perfeito'. "
                "Acao esperada: clicar no link da bio para fazer reserva direta."
            ),
            "7": (
                "Tom quente e acolhedor. Fotos reais do hotel (banco de imagens "
                "do cliente disponivel). Cores terrosas e douradas para remeter "
                "ao outono. Referencia: @fazendasenalba e @hotelurbano."
            ),
            "8": "Feed: 1080x1080px e 1080x1350px. Stories: 1080x1920px.",
            "9": "25/03/2026 (para comecar a publicar em 01/04).",
            "10": (
                "Incluir Pascoa (05/04) como tema de 2 posts especiais. "
                "Destacar o restaurante e o menu de outono. "
                "1 reels com tour pelo hotel. "
                "Nao usar imagens de banco generico, apenas fotos reais."
            ),
        },
    },
    {
        "filename": "briefing-client_gamma-linkedin-marco2026.pdf",
        "answers": {
            "1": "Conteudo LinkedIn Marco 2026 - ClientGamma",
            "2": (
                "6 posts para LinkedIn (3 posts com imagem, 2 carrosseis "
                "informativos, 1 video/reels institucional)."
            ),
            "3": "LinkedIn.",
            "4": (
                "Posicionar a ClientGamma como referencia em solucoes agricolas "
                "e tecnologia no agronegocio. Atrair potenciais parceiros "
                "comerciais e fortalecer a marca empregadora."
            ),
            "5": (
                "Produtores rurais de medio e grande porte, engenheiros "
                "agronomos e profissionais do agronegocio. "
                "Tambem potenciais colaboradores para vagas abertas."
            ),
            "6": (
                "Mensagem-chave: 'Inovacao que transforma o campo'. "
                "Acao esperada: visitar o site da ClientGamma e entrar em "
                "contato com a equipe comercial."
            ),
            "7": (
                "Tom institucional e profissional. Cores da marca (verde "
                "e branco). Fotos reais das operacoes e maquinarios. "
                "Evitar linguagem informal."
            ),
            "8": "LinkedIn: 1200x627px (paisagem) e 1080x1080px (quadrado).",
            "9": "28/02/2026.",
            "10": (
                "Incluir post sobre o Dia da Agua (22/03) com foco em "
                "sustentabilidade. Mencionar a participacao da empresa "
                "na Agrishow se confirmada. "
                "Todos os textos devem ser aprovados pelo juridico."
            ),
        },
    },
    {
        "filename": "briefing-client_delta-instagram-marco2026.pdf",
        "answers": {
            "1": "Campanha Instagram Marco 2026 - ClientDelta",
            "2": (
                "10 posts para feed (3 posts estaticos, 3 carrosseis, "
                "4 reels), 6 stories."
            ),
            "3": "Instagram (feed, stories e reels).",
            "4": (
                "Lancar a nova colecao outono/inverno da ClientDelta e gerar "
                "desejo nos seguidores. Aumentar o trafego para o "
                "e-commerce e as vendas online."
            ),
            "5": (
                "Mulheres de 25-40 anos, classe B/A, que acompanham "
                "tendencias de moda e valorizam pecas versateis."
            ),
            "6": (
                "Mensagem-chave: 'Vista-se para o que esta por vir'. "
                "Acao esperada: acessar o e-commerce pelo link na bio "
                "e comprar pecas da nova colecao."
            ),
            "7": (
                "Estetica minimalista e sofisticada. Paleta de cores "
                "outonais: burgundy, caramelo, off-white, marrom. "
                "Referencia: @amaro e @mariafilo. "
                "Fotos do lookbook da colecao serao fornecidas."
            ),
            "8": "Feed: 1080x1350px (retrato). Reels: 1080x1920px.",
            "9": "01/03/2026 (lancamento no dia 05/03).",
            "10": (
                "O lancamento oficial e dia 05/03 - programar contagem "
                "regressiva nos stories a partir de 03/03. "
                "Incluir Dia da Mulher (08/03) com campanha especial. "
                "Todos os reels devem ter legenda e musica trending. "
                "Codigo de desconto exclusivo Instagram: ClientDelta15."
            ),
        },
    },
    {
        "filename": "briefing-client_epsilon-instagram-marco2026.pdf",
        "answers": {
            "1": "Conteudo Instagram Marco 2026 - ClientEpsilon Hotels",
            "2": (
                "8 posts para feed (3 posts estaticos, 2 carrosseis, "
                "3 reels), 5 stories."
            ),
            "3": "Instagram (feed, stories e reels).",
            "4": (
                "Promover os hoteis da rede ClientEpsilon como destino ideal "
                "para o feriado de Carnaval (final de fevereiro/inicio "
                "de marco) e viagens de outono. Gerar reservas diretas."
            ),
            "5": (
                "Viajantes de 28-50 anos que buscam hoteis boutique "
                "com experiencias diferenciadas. Casais e grupos de amigos."
            ),
            "6": (
                "Mensagem-chave: 'Experiencias que ficam na memoria'. "
                "Acao esperada: reservar diretamente pelo site ou WhatsApp."
            ),
            "7": (
                "Estilo lifestyle e aspiracional. Cores suaves e naturais. "
                "Fotos reais dos hoteis com hospedes (banco de imagens "
                "do cliente). Referencia: @selfrankfurt e @uxuapraia."
            ),
            "8": "Feed: 1080x1080px e 1080x1350px. Reels: 1080x1920px.",
            "9": "25/02/2026.",
            "10": (
                "Destacar pelo menos 2 unidades diferentes da rede. "
                "1 reels com 'tour' por um dos hoteis. "
                "Incluir depoimento real de hospede se disponivel. "
                "Post sobre sustentabilidade (hotel tem selo verde). "
                "Nao mencionar tarifas nos posts, apenas 'consulte valores'."
            ),
        },
    },
]

QUESTIONS = [
    "1 - Qual e o titulo deste projeto?",
    (
        "2 - Quais tipos de materiais voce precisa e quantas unidades de cada? "
        '(ex.: "1 post de feed, 2 stories, 1 e-mail marketing")'
    ),
    (
        "3 - Em quais canais esses materiais serao publicados? "
        "(ex.: Instagram, LinkedIn, E-mail Marketing, Google Ads, OOH)"
    ),
    "4 - Qual e o principal objetivo desta acao ou campanha?",
    (
        "5 - Atraves das entregas deste projeto, "
        "falaremos com quem principalmente?"
    ),
    (
        "6 - Qual e a mensagem-chave e qual acao espera "
        "que o publico tome?"
    ),
    (
        "7 - Voce tem referencias visuais ou de estilo? "
        "(Atraves de link, print, ou descricao de cores, estilos, marcas)"
    ),
    (
        "8 - Quais sao as dimensoes ou formato? "
        "(Entregas fisicas necessitam de medida)"
    ),
    "9 - Qual e o prazo de entrega ideal?",
    (
        "10 - Existe alguma informacao, restricao ou requisito "
        "adicional que devamos considerar?"
    ),
]


def create_briefing_pdf(briefing: dict) -> str:
    pdf = FPDF()
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Header
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(0, 82, 204)  # Agency blue
    pdf.cell(0, 15, "Agency", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # Title
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(
        0, 10, "Direcionamento de demandas",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    pdf.ln(8)

    # Questions and answers
    pdf.set_font("Helvetica", "", 11)
    answers = briefing["answers"]

    for i, question in enumerate(QUESTIONS, 1):
        # Question
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(
            w=0, h=6, text=question,
            new_x="LMARGIN", new_y="NEXT",
        )

        # Answer
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(
            w=0, h=6, text=f"R: {answers[str(i)]}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    # Footer
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(0, 82, 204)
    pdf.cell(0, 10, "Agency", new_x="LMARGIN", new_y="NEXT", align="R")

    output_path = f"{OUTPUT_DIR}/{briefing['filename']}"
    pdf.output(output_path)
    return output_path


def main():
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if target == "demo":
        briefings = BRIEFINGS_DEMO
    elif target == "all":
        briefings = BRIEFINGS + BRIEFINGS_DEMO
    else:
        briefings = BRIEFINGS

    for briefing in briefings:
        path = create_briefing_pdf(briefing)
        print(f"Criado: {path}")
    print(f"\n{len(briefings)} briefings gerados em {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
