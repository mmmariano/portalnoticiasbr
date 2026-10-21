#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mais-noticia.py - cria notícia(s) real(is) da internet no Portal de Notícias BR (portalnoticiasbr.site).

Coloque na raiz do site (junto de build.py e noticias-dados.json) e rode:   python mais-noticia.py

O que faz:
  1. Lê os feeds RSS da Agência Brasil (economia, mundo, esportes, saúde, educação, cultura), um por editoria,
     e pega a notícia mais recente de cada que ainda não está no portal.
  2. Abre a matéria, pega título, resumo, parágrafos, foto e crédito (CC BY 3.0 BR, crédito automático).
  3. Baixa a foto para img/ (se a foto tiver crédito de terceiros, usa foto ilustrativa).
  4. Salva a matéria em noticias-dados.json e roda build.py, que refaz home, arquivo, matérias,
     sitemap.xml, rss.xml e llms.txt com SEO completo.
Só usa a biblioteca padrão do Python.

Opções:
  python mais-noticia.py --quantidade 6       cria 6 notícias (uma por feed, em rodízio)
  python mais-noticia.py --feed URL_DO_RSS    usa outro feed (pode repetir)
Depois rode push.cmd para publicar.
"""
import argparse, html, json, os, re, subprocess, sys, textwrap, unicodedata, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# Feeds por editoria (Agência Brasil). Este portal prioriza economia, mundo, esportes, saúde, educação e cultura
# (o portal "Notícias do Brasil" usa o feed geral, então as pautas não se repetem). Troque à vontade com --feed.
DEFAULT_FEEDS = [f"https://agenciabrasil.ebc.com.br/rss/{s}/feed.xml" for s in
                 ("economia", "internacional", "esportes", "saude", "educacao", "cultura")]
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


# ----------------------------------------------------------------- criar matéria
def criar_noticia(raiz, dados, item, feed_host):
    cat = categoria_de(item["link"], item["cats"])
    completo = feed_host in FULL_CONTENT_HOSTS
    slug = slugify(item["title"])
    if any(d["slug"] == slug for d in dados):
        return None
    print(f"-> {item['title']}\n   {item['link']}")
    pag = dict(paras=[], img="", credito="", desc="")
    try:
        pag = analisar_pagina(item["link"])
    except Exception as e:
        print("   ! não consegui abrir a matéria, uso só o resumo do feed:", e)
    resumo = item["desc"] or strip_tags(pag["desc"])
    if completo and len(pag["paras"]) >= 2:
        tot, paras = 0, []
        for p in pag["paras"][:5]:
            if tot + len(p) > 1800 and paras:
                break
            paras.append(p)
            tot += len(p)
    else:
        paras = [resumo] if resumo else []
    if not paras:
        print("   ! sem texto utilizável, pulando.")
        return None
    lead = cut(resumo or paras[0], 190)
    if lead.strip() == paras[0].strip() and len(paras) > 1:
        lead = cut(paras[1], 190)
    try:
        dt = parsedate_to_datetime(item["pub"])
        dt = dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        dt = datetime.now()
    legenda, foto, credito = "", pag["img"] or item["img"], pag["credito"]
    if completo and foto and not any(x in credito.lower() for x in CREDITO_PROIBIDO):
        arq = baixar_imagem(foto, raiz / "img", slug)
        if arq:
            legenda = (f"Foto: {credito}" if credito else "Foto: Agência Brasil") + " (licença CC BY 3.0 BR)"
    elif foto and completo:
        print("   (foto com crédito de terceiros; usando foto ilustrativa)")
    fonte = f'<a href="{esc(item["link"])}" target="_blank" rel="noopener nofollow">{"Agência Brasil" if completo else esc_text(feed_host)}</a>'
    if completo:
        fonte += " · conteúdo sob licença CC BY 3.0 BR"
    n = dict(slug=slug, cat=cat, title=item["title"], lead=lead, date=dt.strftime("%Y-%m-%d"), hora=dt.strftime("%H:%M"),
             mins=str(max(2, round(sum(len(p.split()) for p in paras) / 200))),
             body=[esc_text(p) for p in paras], facts=[], src=fonte, caption="", legenda=legenda, q=cat)
    dados.append(n)
    return n


def main():
    ap = argparse.ArgumentParser(description="Cria notícia(s) real(is) no Portal de Notícias BR")
    ap.add_argument("--feed", action="append", help="URL de um feed RSS (pode repetir)")
    ap.add_argument("--quantidade", type=int, default=1)
    ap.add_argument("--pasta", default=None)
    a = ap.parse_args()
    raiz = Path(a.pasta) if a.pasta else Path(__file__).resolve().parent
    dados_f = raiz / "noticias-dados.json"
    if not dados_f.exists():
        raise SystemExit(f"Não achei noticias-dados.json em {raiz}. Rode o script na raiz do site.")
    (raiz / "img").mkdir(exist_ok=True)
    dados = json.loads(dados_f.read_text(encoding="utf-8"))
    estado_f = raiz / ".noticias_importadas.json"
    usados = set(json.loads(estado_f.read_text(encoding="utf-8"))) if estado_f.exists() else set()

    feeds = a.feed or DEFAULT_FEEDS
    filas = []
    for feed in feeds:
        try:
            print("Lendo feed:", feed)
            filas.append((urllib.parse.urlparse(feed).netloc, [i for i in ler_feed(feed) if i["link"] not in usados]))
        except Exception as e:
            print("   ! falhou:", e)
    criadas = 0
    while criadas < a.quantidade and any(f for _, f in filas):   # rodízio entre os feeds
        for host, fila in filas:
            if criadas >= a.quantidade:
                break
            while fila:
                it = fila.pop(0)
                try:
                    n = criar_noticia(raiz, dados, it, host)
                except Exception as e:
                    print("   ! erro nessa matéria, tentando a próxima:", e)
                    continue
                usados.add(it["link"])
                if n:
                    criadas += 1
                    print(f"   OK: noticias/{n['slug']}.html  [{n['cat']}]")
                    break
    estado_f.write_text(json.dumps(sorted(usados), ensure_ascii=False, indent=1), encoding="utf-8")
    if not criadas:
        print("Nenhuma notícia nova criada (feeds sem itens novos ou sem acesso à internet).")
        return
    dados_f.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([sys.executable, str(raiz / "build.py")], cwd=raiz, check=True)
    print(f"\nPronto: {criadas} notícia(s) criada(s). Agora rode o push.cmd para publicar.")


if __name__ == "__main__":
    main()
