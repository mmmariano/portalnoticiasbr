#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nova_noticia.py - cria UMA notícia nova (real, da internet) no Portal de Notícias BR.

Coloque este arquivo na raiz do site (C:\\Users\\mtema\\OneDrive\\Desktop\\portalnoticiasbr)
e rode:   python nova_noticia.py

O que ele faz:
  1. Lê a pasta do site (noticias/, index.html, sitemap.xml, llms.txt...).
  2. Busca no feed RSS da Agência Brasil a notícia mais recente que ainda não está no site.
  3. Abre a página da matéria, pega título, resumo, parágrafos, foto e crédito.
  4. Baixa a foto para img/ (evita o bloqueio de imagem externa).
  5. Cria noticias/<slug>.html no mesmo layout das outras matérias.
  6. Atualiza a página inicial (index.html):
       - coloca a notícia como primeiro slide do hero (carrossel do topo)
       - coloca a notícia em DESTAQUE no topo ("Em destaque")
       - atualiza a lista "Mais lidas"
       - adiciona o card na seção da editoria (ou cria a seção se não existir)
  7. Atualiza índice de notícias, letreiro, menu, sitemap.xml e llms.txt.

Só usa a biblioteca padrão do Python (sem pip install).

Opções:
  python nova_noticia.py --quantidade 3        cria 3 notícias de uma vez
  python nova_noticia.py --feed URL_DO_RSS     usa outro feed RSS
  python nova_noticia.py --pasta C:\\caminho    usa outra pasta do site

Conteúdo da Agência Brasil é licenciado em CC BY 3.0 BR (uso livre com crédito);
o crédito e o link da fonte são colocados automaticamente em cada matéria.
Para feeds de OUTROS sites, o script usa só título + resumo + link (sem copiar o texto
completo nem a foto).
"""
import argparse, html, json, os, re, sys, textwrap, unicodedata, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_FEEDS = ["https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"]
FULL_CONTENT_HOSTS = {"agenciabrasil.ebc.com.br"}      # CC BY 3.0 BR
UA = "Mozilla/5.0 (compatible; PortalNoticiasBR-bot/1.0)"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
SECOES = {  # trecho da URL -> editoria do portal
    "politica": "Política", "economia": "Economia", "meio-ambiente": "Meio Ambiente",
    "esportes": "Esportes", "educacao": "Educação", "internacional": "Mundo",
    "saude": "Saúde", "justica": "Justiça", "cultura": "Cultura", "geral": "Brasil",
    "direitos-humanos": "Direitos Humanos", "tecnologia": "Tecnologia", "turismo": "Turismo",
}
CORES = ["#3c5990", "#14827a", "#4c9c52", "#6e46aa", "#c1121f", "#b8860b", "#0e88ab"]


# ----------------------------------------------------------------- rede
def http_get(url, binary=False, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if binary:
            return data, r.headers.get("Content-Type", "")
        enc = r.headers.get_content_charset() or "utf-8"
        return data.decode(enc, errors="replace")


# ----------------------------------------------------------------- utilidades
def slugify(t, n=80):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    if len(t) > n:
        t = t[:n].rsplit("-", 1)[0]
    return t or "noticia"


def esc(t):
    return html.escape(t, quote=True)


def esc_text(t):
    return html.escape(t, quote=False)


def strip_tags(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def cut(t, n):
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip(",;:.- ") + "…"


def categoria_de(link, cats):
    path = urllib.parse.urlparse(link).path.lower().split("/")
    for p in path:
        if p in SECOES:
            return SECOES[p]
    for c in cats:
        k = slugify(c)
        if k in SECOES:
            return SECOES[k]
    return "Brasil"


def hid(cat):
    return cat.lower().replace(" ", "-")


# ----------------------------------------------------------------- RSS
def ler_feed(url):
    xml = http_get(url, binary=True)[0]
    root = ET.fromstring(xml)
    itens = []
    for it in root.iter("item"):
        g = lambda tag: (it.findtext(tag) or "").strip()
        img = ""
        for e in it:
            tag = e.tag.split("}")[-1]
            if tag in ("enclosure", "content", "thumbnail") and e.get("url"):
                t = e.get("type", "")
                if not t or t.startswith("image"):
                    img = e.get("url")
                    break
        itens.append(dict(title=g("title"), link=g("link"), desc=strip_tags(g("description")),
                          pub=g("pubDate"), cats=[c.text or "" for c in it.findall("category")], img=img))
    if not itens:  # Atom
        for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
            ns = "{http://www.w3.org/2005/Atom}"
            lk = e.find(ns + "link")
            itens.append(dict(title=(e.findtext(ns + "title") or "").strip(),
                              link=(lk.get("href") if lk is not None else ""),
                              desc=strip_tags(e.findtext(ns + "summary") or ""),
                              pub=(e.findtext(ns + "updated") or ""), cats=[], img=""))
    return [i for i in itens if i["title"] and i["link"]]


# ----------------------------------------------------------------- página da matéria
class Pagina(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.in_p = False
        self.buf = []
        self.paras = []
        self.imgs = []
        self.meta = {}

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag in self.SKIP:
            self.skip += 1
        if tag == "meta":
            k = a.get("property") or a.get("name")
            if k and a.get("content"):
                self.meta.setdefault(k, a["content"])
        if tag == "img" and a.get("src"):
            self.imgs.append(a)
        if tag == "p" and not self.skip:
            self.in_p, self.buf = True, []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "p" and self.in_p:
            self.in_p = False
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if t:
                self.paras.append(t)

    def handle_data(self, d):
        if self.in_p and not self.skip:
            self.buf.append(d)


RUIM = ("compartilhe", "ver mais", "edição:", "leia mais", "continuar lendo", "todos os direitos",
        "política de privacidade", "versão em áudio", "siga-nos")
CREDITO_PROIBIDO = ("reuters", "proibida", "direitos reservados", "getty", "afp", "divulgação/")


def analisar_pagina(url):
    p = Pagina()
    p.feed(http_get(url))
    paras, vistos = [], set()
    for t in p.paras:
        tl = t.lower()
        if len(t) < 70 or any(x in tl for x in RUIM) or t in vistos:
            continue
        vistos.add(t)
        paras.append(t)
    img = p.meta.get("og:image") or p.meta.get("twitter:image") or ""
    credito = ""
    for a in p.imgs:
        src = a.get("src", "")
        if "loading_v2" in src or "/files/" not in src:
            continue
        if a.get("title", "").strip():
            credito = a["title"].strip()
            break
    return dict(paras=paras, img=img, credito=credito,
                desc=p.meta.get("og:description") or p.meta.get("description") or "")


# ----------------------------------------------------------------- imagens
def baixar_imagem(url, img_dir, slug):
    try:
        data, ctype = http_get(url, binary=True)
    except Exception as e:
        print("   ! não consegui baixar a foto:", e)
        return None
    if len(data) < 3000:
        return None
    ext = ".jpg"
    for k, v in ((".png", "png"), (".webp", "webp"), (".gif", "gif")):
        if v in ctype.lower() or url.lower().split("?")[0].endswith(k):
            ext = k
    nome = slug + ext
    (img_dir / nome).write_bytes(data)
    return nome


def criar_svg(img_dir, slug, cat, titulo):
    cor = CORES[sum(map(ord, cat)) % len(CORES)]
    linhas = textwrap.wrap(titulo, 30)[:5]
    txt = "".join(f'<text x="90" y="{330 + i * 80}" font-size="64" font-weight="700" fill="#fff">{esc_text(l)}</text>'
                  for i, l in enumerate(linhas))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 840" font-family="DejaVu Sans,Arial,sans-serif">'
           f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{cor}"/>'
           f'<stop offset="1" stop-color="#10172a"/></linearGradient></defs><rect width="1600" height="840" fill="url(#g)"/>'
           f'<rect x="85" y="113" width="12" height="124" fill="#fcbf49"/>'
           f'<text x="125" y="165" font-size="46" font-weight="700" fill="#fff">{esc_text(cat.upper())}</text>{txt}'
           f'<text x="90" y="790" font-size="34" font-weight="700" fill="#fff">portalnoticiasbr.site</text></svg>')
    nome = slug + ".svg"
    (img_dir / nome).write_text(svg, encoding="utf-8")
    return nome


# ----------------------------------------------------------------- HTML do portal
def card(a, prefix):
    return (f'<a class="cd" href="{prefix}noticias/{a["slug"]}.html"><figure><img src="{prefix}img/{a["img"]}" '
            f'alt="Foto: {esc(a["title"])}" width="800" height="500" loading="lazy"></figure>'
            f'<div class="b"><span class="tg">{esc_text(a["cat"])}</span><h3>{esc_text(a["title"])}</h3>'
            f'<p>{esc_text(a["lead"])}</p><small>{a["meta"]}</small></div></a>')


def ler_cards(idx_html):
    out = []
    for m in re.finditer(r'<a class="cd" href="\.\./noticias/([a-z0-9-]+)\.html">.*?<img src="\.\./img/([^"]+)".*?'
                         r'<span class="tg">([^<]+)</span><h3>([^<]+)</h3><p>([^<]*)</p><small>([^<]+)</small>',
                         idx_html, re.S):
        out.append(dict(slug=m[1], img=m[2], cat=html.unescape(m[3]), title=html.unescape(m[4]),
                        lead=html.unescape(m[5]), meta=m[6]))
    return out


def set_meta(head, pattern, novo):
    return re.sub(pattern, lambda m: m.group(1) + novo + m.group(3), head, count=1, flags=re.S)


def montar_head(head, n, dominio):
    url = f"{dominio}/noticias/{n['slug']}.html"
    img_abs = f"{dominio}/img/{n['img']}"
    titulo_pag = f"{n['title']} | Portal de Notícias BR"
    head = set_meta(head, r"(<title>)(.*?)(</title>)", esc_text(titulo_pag))
    head = set_meta(head, r'(<meta name="description" content=")(.*?)(">)', esc(n["lead"]))
    head = set_meta(head, r'(<link rel="canonical" href=")(.*?)(">)', url)
    head = set_meta(head, r'(<meta property="og:title" content=")(.*?)(">)', esc(titulo_pag))
    head = set_meta(head, r'(<meta property="og:description" content=")(.*?)(">)', esc(n["lead"]))
    head = set_meta(head, r'(<meta property="og:url" content=")(.*?)(">)', url)
    head = set_meta(head, r'(<meta property="og:image" content=")(.*?)(">)', img_abs)
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": n["title"],
          "description": n["lead"], "image": [img_abs],
          "datePublished": n["iso"], "dateModified": n["iso"],
          "author": {"@type": "Organization", "name": "Portal de Notícias BR"},
          "publisher": {"@type": "Organization", "name": "Portal de Notícias BR",
                        "logo": {"@type": "ImageObject", "url": f"{dominio}/favicon.png"}},
          "mainEntityOfPage": url, "inLanguage": "pt-BR", "articleSection": n["cat"]}
    ld_tag = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>"
    if "application/ld+json" in head:
        head = re.sub(r'<script type="application/ld\+json">.*?</script>', lambda m: ld_tag, head, count=1, flags=re.S)
    else:
        head = head.replace("</head>", ld_tag + "</head>")
    return head


def montar_artigo(n):
    paras = "".join(f"<p>{esc_text(p)}</p>" for p in n["paras"])
    fonte = (f'<p class="src">Fonte: <a href="{esc(n["link"])}" target="_blank" rel="noopener nofollow">{esc_text(n["fonte"])}</a>'
             f'{" · " + esc_text(n["licenca"]) if n["licenca"] else ""}</p>')
    legenda = esc_text(n["legenda"])
    return (f'<figure class="cv"><img src="../img/{n["img"]}" alt="Foto: {esc(n["title"])}" width="1600" height="686" '
            f'style="object-fit:cover"><small>{legenda}</small></figure>'
            f'<article class="ar"><span class="tg">{esc_text(n["cat"])}</span><h1>{esc_text(n["title"])}</h1>'
            f'<p class="ld">{esc_text(n["lead"])}</p>'
            f'<div class="mt">Por Redação Portal de Notícias BR · <time datetime="{n["data"]}">{n["dlabel"]}</time> · '
            f'{n["mins"]} min de leitura</div>{paras}{fonte}</article>')


def atualizar_letreiro(s, titulo):
    def troca(m):
        spans = re.findall(r"<span>(.*?)</span>", m.group(1), re.S)
        if not spans:
            return m.group(0)
        meia = spans[: len(spans) // 2] if len(spans) % 2 == 0 else spans
        novo = f"● {esc_text(titulo)}"
        if novo in meia:
            return m.group(0)
        lista = [novo] + meia
        return '<div class="tk"><div>' + "".join(f"<span>{x}</span>" for x in lista * 2) + "</div></div>"
    return re.sub(r'<div class="tk"><div>(.*?)</div></div>', troca, s, count=1, flags=re.S)


def garantir_menu(s, cat):
    h = hid(cat)
    if f'#{h}">{cat}</a>' in s:
        return s
    return re.sub(r'(<a href="((?:\.\./)?)noticias/index\.html">Todas</a>)',
                  lambda m: f'<a href="{m.group(2)}index.html#{h}">{esc_text(cat)}</a>' + m.group(1), s, count=1)


# ----------------------------------------------------------------- programa principal
def criar_noticia(raiz, item, feed_host, dominio):
    noticias, img_dir = raiz / "noticias", raiz / "img"
    img_dir.mkdir(exist_ok=True)
    cat = categoria_de(item["link"], item["cats"])
    completo = feed_host in FULL_CONTENT_HOSTS
    slug = slugify(item["title"])
    if (noticias / f"{slug}.html").exists():
        return None

    print(f"-> {item['title']}\n   {item['link']}")
    pag = dict(paras=[], img="", credito="", desc="")
    try:
        pag = analisar_pagina(item["link"])
    except Exception as e:
        print("   ! não consegui abrir a matéria, uso só o resumo do feed:", e)

    # texto
    resumo = item["desc"] or strip_tags(pag["desc"])
    if completo and len(pag["paras"]) >= 2:
        paras = pag["paras"][:5]
        # junta o limite de tamanho (~1800 caracteres) sem cortar parágrafo no meio
        tot, ok = 0, []
        for p in paras:
            if tot + len(p) > 1800 and ok:
                break
            ok.append(p)
            tot += len(p)
        paras = ok
    else:
        paras = [resumo] if resumo else []
    if not paras:
        print("   ! sem texto utilizável, pulando.")
        return None
    lead = cut(resumo or paras[0], 190)
    if lead.strip() == paras[0].strip() and len(paras) > 1:
        lead = cut(paras[1], 190)

    # data
    try:
        dt = parsedate_to_datetime(item["pub"])
        dt = dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        try:
            dt = datetime.fromisoformat(item["pub"].replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            dt = datetime.now()

    # imagem (só reaproveita foto se a fonte permite e o crédito não é de terceiros)
    arquivo, legenda = None, "Arte: Portal de Notícias BR"
    foto = pag["img"] or item["img"]
    credito = pag["credito"]
    if completo and foto and not any(x in credito.lower() for x in CREDITO_PROIBIDO):
        arquivo = baixar_imagem(foto, img_dir, slug)
        if arquivo:
            legenda = (f"Foto: {credito}" if credito else "Foto: Agência Brasil") + " (licença CC BY 3.0 BR)"
    elif foto and completo:
        print("   (foto com crédito de terceiros; usando arte do portal)")
    if not arquivo:
        arquivo = criar_svg(img_dir, slug, cat, item["title"])

    palavras = sum(len(p.split()) for p in paras)
    n = dict(slug=slug, title=item["title"], lead=lead, cat=cat, paras=paras, img=arquivo,
             link=item["link"], fonte="Agência Brasil" if completo else feed_host,
             licenca="conteúdo sob licença CC BY 3.0 BR" if completo else "",
             legenda=legenda, iso=dt.strftime("%Y-%m-%dT%H:%M:00-03:00"), data=dt.strftime("%Y-%m-%d"),
             dlabel=f"{dt.day} {MESES[dt.month - 1]} {dt.year}", mins=max(2, round(palavras / 200)))
    n["meta"] = f"{n['dlabel']} · {n['mins']} min de leitura"

    # --- página
    idx_path = noticias / "index.html"
    idx = idx_path.read_text(encoding="utf-8")
    existentes = ler_cards(idx)
    modelos = [p for p in noticias.glob("*.html") if p.name != "index.html"]
    if not modelos:
        raise SystemExit("Não achei nenhuma matéria modelo em noticias/.")
    modelo = max(modelos, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")
    bi = modelo.find("<body")
    a0, a1 = modelo.find('<figure class="cv">'), modelo.find('<main class="w">')
    a2 = modelo.find("</main>", a1) + len("</main>")
    if min(bi, a0, a1) < 0:
        raise SystemExit("O modelo de matéria não tem a estrutura esperada.")
    rel = [c for c in existentes if c["cat"] == cat][:3]
    rel += [c for c in existentes if c not in rel][: 3 - len(rel)]
    main_rel = ('<main class="w"><h2 class="sc">Leia também</h2><div class="gr">'
                + "".join(card(c, "../") for c in rel) + "</div></main>")
    pagina = (montar_head(modelo[:bi], n, dominio) + modelo[bi:a0] + montar_artigo(n) + main_rel + modelo[a2:])
    (noticias / f"{slug}.html").write_text(pagina, encoding="utf-8")

    # --- índice de notícias
    idx = idx.replace('<div class="gr"><a class="cd"', '<div class="gr">' + card(n, "../") + '<a class="cd"', 1)
    if f'data-c="{cat}"' not in idx:
        idx = idx.replace('</div><input id="q"', f'<button data-c="{esc(cat)}">{esc_text(cat)}</button></div><input id="q"', 1)
    idx_path.write_text(idx, encoding="utf-8")

    # --- home (seção da categoria + destaque no topo)
    home_path = raiz / "index.html"
    home = home_path.read_text(encoding="utf-8")
    h = hid(cat)

    # 1) Atualiza / cria a seção da categoria (mais recente primeiro)
    m = re.search(
        r'(<h2 class="sc" id="%s"[^>]*>.*?</h2>\s*<div class="gr">)' % re.escape(h),
        home, re.S | re.I,
    )
    if m:
        home = home[: m.end()] + card(n, "") + home[m.end():]
        print(f"   ✓ index.html: notícia adicionada na seção #{h}")
    else:
        sec = (
            f'<h2 class="sc" id="{h}">{esc_text(cat)}'
            f'<a href="noticias/index.html">Ver todas →</a></h2>'
            f'<div class="gr">{card(n, "")}</div>'
        )
        if "</main>" in home:
            home = home.replace("</main>", sec + "</main>", 1)
            print(f"   ✓ index.html: criada nova seção #{h}")
        else:
            print("   ! não achei </main> no index.html – seção não foi criada")

    # 2) Coloca a notícia nova em destaque no topo (bloco "Em destaque")
    big = (
        f'<a class="big" href="noticias/{n["slug"]}.html">'
        f'<img src="img/{n["img"]}" alt="Foto: {esc(n["title"])}" loading="lazy">'
        f'<div><span class="tg">{esc_text(n["cat"])}</span>'
        f'<h3>{esc_text(n["title"])}</h3>'
        f'<p>{esc_text(n["lead"])}</p></div></a>'
    )
    home2, nsub = re.subn(
        r'(<h2 class="sc">Em destaque</h2><div class="mag">)\s*<a class="big".*?</a>',
        r"\1" + big,
        home, count=1, flags=re.S,
    )
    if nsub:
        home = home2
        print("   ✓ index.html: notícia colocada em destaque (topo)")
    else:
        # fallback: tenta inserir logo após <div class="mag">
        home2, nsub = re.subn(
            r'(<div class="mag">)',
            r"\1" + big,
            home, count=1,
        )
        if nsub:
            home = home2
            print("   ✓ index.html: notícia inserida no bloco mag (fallback)")
        else:
            print("   ! não achei o bloco 'Em destaque' – destaque não atualizado")

    # 3) Atualiza "Mais lidas" (coloca a nova como nº 1 e reordena)
    def atualiza_mais_lidas(m):
        links = re.findall(
            r'<a href="noticias/[^"]+\.html"><b>\d+</b><span>[^<]+</span></a>',
            m.group(1),
        )
        novo = (
            f'<a href="noticias/{n["slug"]}.html"><b>1</b>'
            f'<span>{esc_text(n["title"])}</span></a>'
        )
        links = [lk for lk in links if n["slug"] not in lk][:4]
        lista = [novo]
        for i, lk in enumerate(links, start=2):
            lista.append(re.sub(r"<b>\d+</b>", f"<b>{i}</b>", lk, count=1))
        return '<aside class="rk"><h3>Mais lidas</h3>' + "".join(lista) + "</aside>"

    home2, nsub = re.subn(
        r'<aside class="rk"><h3>Mais lidas</h3>(.*?)</aside>',
        atualiza_mais_lidas,
        home, count=1, flags=re.S,
    )
    if nsub:
        home = home2
        print("   ✓ index.html: 'Mais lidas' atualizado")

    # 4) Atualiza o slide (hero) do topo — coloca a nova notícia como primeiro slide
    novo_slide = (
        f'<article class="sl on">'
        f'<img src="img/{n["img"]}" alt="Foto: {esc(n["title"])}" loading="lazy">'
        f'<div class="t"><span class="tg">{esc_text(n["cat"])}</span>'
        f'<h2><a href="noticias/{n["slug"]}.html">{esc_text(n["title"])}</a></h2>'
        f'<p>{esc_text(n["lead"])}</p></div></article>'
    )

    def troca_hero(m):
        bloco = m.group(0)
        slides = re.findall(r'<article class="sl(?:\s+on)?">.*?</article>', bloco, re.S)
        slides = [s for s in slides if n["slug"] not in s]
        slides = [re.sub(r'class="sl\s+on"', 'class="sl"', s) for s in slides]
        lista = [novo_slide] + slides[:4]  # novo + até 4 antigos = 5 no total
        abertura = re.search(r'^.*?(?=<article class="sl)', bloco, re.S)
        controles = re.search(r'(<div class="ct">.*)$', bloco, re.S)
        if not abertura or not controles:
            return bloco
        return abertura.group(0) + "".join(lista) + controles.group(1)

    home2, nsub = re.subn(
        r'(?:<div|<section)[^>]*class="hero"[^>]*>.*?<div class="ct">.*?</div>\s*(?:</div>|</section>)',
        troca_hero,
        home, count=1, flags=re.S,
    )
    if nsub:
        home = home2
        print("   ✓ index.html: slide (hero) atualizado com a nova notícia")
    else:
        print("   ! não achei o bloco hero/slide – slide não atualizado")

    home_path.write_text(home, encoding="utf-8")

    # --- letreiro + menu em TODAS as páginas
    for f in list(raiz.glob("*.html")) + list(noticias.glob("*.html")):
        s = f.read_text(encoding="utf-8")
        s2 = garantir_menu(atualizar_letreiro(s, n["title"]), cat)
        if s2 != s:
            f.write_text(s2, encoding="utf-8")

    # --- sitemap e llms.txt
    sm = raiz / "sitemap.xml"
    if sm.exists():
        s = sm.read_text(encoding="utf-8")
        s = s.replace("</urlset>", f'<url><loc>{dominio}/noticias/{slug}.html</loc><lastmod>{n["data"]}</lastmod>'
                                   f'<changefreq>monthly</changefreq><priority>0.7</priority></url>\n</urlset>')
        hoje = datetime.now().strftime("%Y-%m-%d")
        for loc in (f"{dominio}/", f"{dominio}/noticias/"):
            s = re.sub(r"(<loc>%s</loc><lastmod>)[^<]*(</lastmod>)" % re.escape(loc), r"\g<1>%s\g<2>" % hoje, s)
        sm.write_text(s, encoding="utf-8")
    ll = raiz / "llms.txt"
    if ll.exists():
        s = ll.read_text(encoding="utf-8")
        s = s.replace("## Notícias\n", f"## Notícias\n- [{n['title']}]({dominio}/noticias/{slug}.html): {n['lead']}\n", 1)
        ll.write_text(s, encoding="utf-8")
    return n


def main():
    ap = argparse.ArgumentParser(description="Cria notícia(s) real(is) no Portal de Notícias BR")
    ap.add_argument("--feed", action="append", help="URL de um feed RSS (pode repetir)")
    ap.add_argument("--quantidade", type=int, default=1)
    ap.add_argument("--pasta", default=None)
    a = ap.parse_args()

    raiz = Path(a.pasta) if a.pasta else Path(__file__).resolve().parent
    if not (raiz / "noticias" / "index.html").exists():
        alt = Path(r"C:\Users\mtema\OneDrive\Desktop\portalnoticiasbr")
        if (alt / "noticias" / "index.html").exists():
            raiz = alt
        else:
            raise SystemExit(f"Não achei noticias/index.html em {raiz}. Rode o script na raiz do site.")
    print("Pasta do site:", raiz)

    home = (raiz / "index.html").read_text(encoding="utf-8")
    m = re.search(r'<link rel="canonical" href="(https?://[^/"]+)', home)
    dominio = m.group(1) if m else "https://portalnoticiasbr.site"

    estado_f = raiz / ".noticias_importadas.json"
    usados = set(json.loads(estado_f.read_text(encoding="utf-8"))) if estado_f.exists() else set()

    criadas = 0
    for feed in (a.feed or DEFAULT_FEEDS):
        if criadas >= a.quantidade:
            break
        host = urllib.parse.urlparse(feed).netloc
        print("Lendo feed:", feed)
        try:
            itens = ler_feed(feed)
        except Exception as e:
            print("   ! falhou:", e)
            continue
        for it in itens:
            if criadas >= a.quantidade:
                break
            if it["link"] in usados:
                continue
            try:
                n = criar_noticia(raiz, it, host, dominio)
            except SystemExit:
                raise
            except Exception as e:
                print("   ! erro ao criar essa matéria, tentando a próxima:", e)
                continue
            usados.add(it["link"])
            if n:
                criadas += 1
                print(f"   OK: noticias/{n['slug']}.html  [{n['cat']}]")
    estado_f.write_text(json.dumps(sorted(usados), ensure_ascii=False, indent=1), encoding="utf-8")
    if not criadas:
        print("Nenhuma notícia nova criada (feed sem itens novos ou sem acesso à internet).")
    else:
        print(f"\nPronto: {criadas} notícia(s) criada(s). Agora rode o push.cmd para publicar.")


if __name__ == "__main__":
    main()