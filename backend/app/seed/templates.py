"""Biblioteca inicial de templates por segmento (12 categorias x 3 variações)."""

from sqlalchemy.orm import Session

from app.core.catalog import STYLE_PRESETS
from app.models import Template

CATEGORIES: dict[str, dict] = {
    "produtos": {
        "label": "Apresentação de produtos",
        "image_style": "studio product photography, clean background, soft shadows, high detail",
        "hook": "Conheça a novidade!",
        "product_img": "product on a clean studio background with soft light",
        "place_img": "modern store display with products",
        "cta": "Garanta o seu pelo WhatsApp!",
        "benefit": "Qualidade que você sente no primeiro uso.",
    },
    "restaurantes": {
        "label": "Restaurantes",
        "image_style": "professional food photography, restaurant interior, warm cinematic light, shallow depth of field",
        "hook": "Fome de algo especial?",
        "product_img": "gourmet dish plated beautifully on a rustic table",
        "place_img": "cozy modern restaurant interior with warm lights and happy customers",
        "cta": "Reserve sua mesa ou peça pelo WhatsApp!",
        "benefit": "Ingredientes frescos e sabor de verdade em cada prato.",
    },
    "lanchonetes": {
        "label": "Lanchonetes",
        "image_style": "juicy burger and fries close-up, vibrant street food photography, dramatic light",
        "hook": "Bateu aquela vontade?",
        "product_img": "juicy cheeseburger with melted cheese and crispy fries",
        "place_img": "modern snack bar counter with neon lights",
        "cta": "Peça agora pelo WhatsApp e receba rapidinho!",
        "benefit": "Lanches caprichados, feitos na hora.",
    },
    "pizzarias": {
        "label": "Pizzarias",
        "image_style": "italian pizza photography, wood fired oven, melted mozzarella, warm tones",
        "hook": "Hoje é dia de pizza!",
        "product_img": "fresh pizza with melted mozzarella and basil coming out of a wood fired oven",
        "place_img": "rustic pizzeria with wood fired oven and warm ambience",
        "cta": "Peça sua pizza pelo WhatsApp!",
        "benefit": "Massa artesanal e forno a lenha para uma pizza inesquecível.",
    },
    "clinicas_estetica": {
        "label": "Clínicas de estética",
        "image_style": "clean aesthetic clinic, soft pastel light, skincare, elegant minimal spa",
        "hook": "Realce a sua beleza natural.",
        "product_img": "woman with glowing skin receiving a facial skincare treatment",
        "place_img": "modern minimalist aesthetic clinic room with soft light",
        "cta": "Agende sua avaliação pelo WhatsApp!",
        "benefit": "Procedimentos seguros com profissionais especializados.",
    },
    "clinicas_medicas": {
        "label": "Clínicas médicas",
        "image_style": "modern medical clinic, clean bright environment, friendly doctor, trustworthy healthcare",
        "hook": "Sua saúde merece atenção.",
        "product_img": "friendly doctor talking with a patient in a bright modern office",
        "place_img": "modern clean medical clinic reception",
        "cta": "Agende sua consulta pelo WhatsApp!",
        "benefit": "Atendimento humanizado e equipe qualificada.",
    },
    "barbearias": {
        "label": "Barbearias",
        "image_style": "classic barbershop, moody lighting, vintage chair, beard grooming close-up",
        "hook": "Seu visual no próximo nível.",
        "product_img": "barber trimming a beard with precision in a classic barbershop",
        "place_img": "stylish vintage barbershop interior with leather chairs",
        "cta": "Agende seu horário pelo WhatsApp!",
        "benefit": "Cortes modernos e acabamento impecável.",
    },
    "saloes_beleza": {
        "label": "Salões de beleza",
        "image_style": "beauty salon, glossy hair, soft glamorous light, elegant feminine aesthetic",
        "hook": "Hora de se sentir incrível!",
        "product_img": "woman with shiny styled hair in a beauty salon",
        "place_img": "elegant beauty salon interior with mirrors and soft lights",
        "cta": "Agende seu horário pelo WhatsApp!",
        "benefit": "Cabelo, unhas e maquiagem com quem entende.",
    },
    "academias": {
        "label": "Academias",
        "image_style": "modern gym, energetic athletes training, dramatic contrast lighting, fitness",
        "hook": "Chegou a hora de mudar.",
        "product_img": "athlete lifting weights in a modern gym with dramatic light",
        "place_img": "spacious modern gym with equipment and big windows",
        "cta": "Venha fazer uma aula experimental!",
        "benefit": "Equipamentos modernos e acompanhamento profissional.",
    },
    "lojas_roupas": {
        "label": "Lojas de roupas",
        "image_style": "fashion editorial photography, clothing store, stylish outfits, studio lighting",
        "hook": "Nova coleção chegou!",
        "product_img": "stylish outfits on display in a modern fashion boutique",
        "place_img": "modern clothing store interior with racks and warm light",
        "cta": "Confira no Instagram ou chame no WhatsApp!",
        "benefit": "Peças exclusivas para todos os estilos.",
    },
    "imobiliarias": {
        "label": "Imobiliárias",
        "image_style": "real estate photography, modern house exterior, bright living room, golden hour",
        "hook": "O imóvel dos seus sonhos está aqui.",
        "product_img": "modern house with garden at golden hour",
        "place_img": "bright spacious living room with large windows",
        "cta": "Agende uma visita pelo WhatsApp!",
        "benefit": "Imóveis selecionados e atendimento personalizado.",
    },
    "servicos": {
        "label": "Prestadores de serviços",
        "image_style": "professional service worker, clean workspace, trustworthy, natural light",
        "hook": "Precisa de um serviço de confiança?",
        "product_img": "professional technician working carefully with tools",
        "place_img": "clean organized professional workspace",
        "cta": "Solicite um orçamento pelo WhatsApp!",
        "benefit": "Qualidade, pontualidade e garantia no serviço.",
    },
    "empresas": {
        "label": "Empresas em geral",
        "image_style": "corporate photography, modern office, diverse team, clean professional look",
        "hook": "Conheça quem faz a diferença.",
        "product_img": "professional team collaborating in a modern office",
        "place_img": "modern office building facade with glass",
        "cta": "Fale com a gente pelo WhatsApp!",
        "benefit": "Soluções sob medida para o seu negócio.",
    },
}

VARIANTS = [
    ("promocao", "comercial", "Oferta relâmpago", "Vídeo direto ao ponto com destaque para a promoção."),
    ("apresentacao", "moderno", "Apresentação moderna", "Apresenta a empresa, diferenciais e chamada para ação."),
    ("institucional", "elegante", "Institucional elegante", "Tom sofisticado para reforçar marca e confiança."),
]

EXTRA_VARIANTS = {
    "produtos": [("produto", "moderno", "Lançamento moderno", "Galeria, produto em destaque, destaques e preço."),
                 ("produto", "comercial", "Oferta de produto", "Visual de varejo com selo de preço chamativo."),
                 ("produto", "elegante", "Produto premium", "Tom sofisticado para itens de alto valor."),
                 ("produto", "tecnologico", "Produto tech", "Estilo tecnológico para eletrônicos e gadgets.")],
    "restaurantes": [("produto", "criativo", "Prato em destaque", "Foco total em um prato ou combo.")],
    "clinicas_medicas": [("institucional", "profissional", "Confiança médica", "Tom sóbrio e acolhedor.")],
    "empresas": [("anuncio", "tecnologico", "Tech launch", "Estilo tecnológico para produtos e SaaS.")],
    "academias": [("anuncio", "criativo", "Energia total", "Ritmo acelerado e chamadas fortes.")],
}


def _blueprint(cat: dict, video_type: str) -> list[dict]:
    hook = {"role": "hook", "title": cat["hook"], "narration": f"{cat['hook']} Conheça a {{empresa}}.",
            "image": cat["place_img"], "share": 0.16}
    product = {"role": "product", "title": "{produto}", "narration": "{descricao_curta}",
               "image": cat["product_img"], "share": 0.2}
    benefit = {"role": "benefit", "title": "Por que escolher a {empresa}?", "narration": cat["benefit"],
               "image": cat["place_img"], "share": 0.18}
    diff = {"role": "differential", "title": "{diferencial_1}", "narration": "{diferenciais_frase}",
            "image": cat["product_img"], "share": 0.18}
    offer = {"role": "offer", "title": "{oferta}", "narration": "{oferta_frase}",
             "image": cat["product_img"], "share": 0.16}
    cta = {"role": "cta", "title": "{cta}", "narration": "{cta} {contato_frase}",
           "image": cat["place_img"], "share": 0.12}
    if video_type == "promocao":
        return [hook, offer, product, diff, cta]
    if video_type == "institucional":
        return [hook, benefit, diff, product, cta]
    if video_type == "produto":
        return [hook, product, diff, offer, cta]
    return [hook, product, benefit, diff, offer, cta]


def build_templates() -> list[dict]:
    out = []
    for slug, cat in CATEGORIES.items():
        variants = EXTRA_VARIANTS[slug] if slug == "produtos" else VARIANTS + EXTRA_VARIANTS.get(slug, [])
        for video_type, style, name, desc in variants:
            preset = STYLE_PRESETS[style]
            out.append({
                "slug": f"{slug}-{video_type}-{style}",
                "category": slug,
                "name": f"{cat['label']} · {name}",
                "description": desc,
                "style": style,
                "video_type": video_type,
                "config": {
                    "category_label": cat["label"],
                    "format": "9:16",
                    "duration": 30,
                    "palette": preset["palette"],
                    "font": preset["font"],
                    "music_mood": preset["music"],
                    "transition": preset["transition"],
                    "motion": preset["motion"],
                    "text_animation": preset["animation"],
                    "image_style": cat["image_style"],
                    "cta": cat["cta"],
                    "blueprint": _blueprint(cat, video_type),
                },
            })
    return out


def seed_templates(db: Session) -> int:
    existing = {t.slug for t in db.query(Template.slug).all()}
    created = 0
    for data in build_templates():
        if data["slug"] in existing:
            continue
        db.add(Template(**data))
        created += 1
    db.commit()
    return created
