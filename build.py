#!/usr/bin/env python3
"""Gera o site inteiro (home, arquivo, materias, sitemap, rss, llms.txt, robots). Uso: python build.py"""
import json, os, re, html, datetime
from email.utils import format_datetime
B = "https://portalnoticiasbr.site"; NAME = "Portal de Notícias BR"
E = html.escape
arts = json.load(open("noticias-dados.json", encoding="utf-8"))
arts.sort(key=lambda a: a["date"], reverse=True)
imgs = json.load(open("imagens.json", encoding="utf-8")) if os.path.exists("imagens.json") else {}
CATS = ["Política","Economia","Meio Ambiente","Turismo","Esportes","Tecnologia","Educação","Mundo","Justiça","Saúde"]
MES = "jan fev mar abr mai jun jul ago set out nov dez".split()
def dt(d): y,m,dd = d.split("-"); return f"{int(dd)} {MES[int(m)-1]} {y}"
def cut(t, n):
    t = re.sub(r"<[^>]+>", "", html.unescape(t)).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
def img(a):
    p = imgs.get(a["slug"])
    if p: return p["url"], f'Foto: {p["by"]} / Pexels', p["alt"], True
    for ext in ("jpg", "png", "svg"):
        if os.path.exists(f'img/{a["slug"]}.{ext}'): return f'img/{a["slug"]}.{ext}', "Imagem ilustrativa", None, False
    write(f'img/{a["slug"]}.svg', f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#10172a"/><stop offset="1" stop-color="#c1121f"/></linearGradient></defs><rect width="1600" height="900" fill="url(#g)"/><text x="800" y="470" font-family="Georgia,serif" font-size="96" fill="#fcbf49" text-anchor="middle">{E(a["cat"])}</text></svg>')
    return f'img/{a["slug"]}.svg', "Imagem ilustrativa", None, False
def src(a, pre, full=False):
    u, cr, alt, ext = img(a)
    if ext: return u
    return (B + "/" if full else pre) + u
def alt(a): return f'{a["title"]}'
def jl(o): return '<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False) + "</script>"
def head(pre, title, desc, path, image, typ="website", extra=""):
    url = B + "/" + path
    return f'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{url}"><link rel="alternate" hreflang="pt-BR" href="{url}"><link rel="alternate" type="application/rss+xml" title="{NAME}" href="{B}/rss.xml"><meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1"><meta name="theme-color" content="#10172a"><meta name="author" content="{NAME}"><meta property="og:type" content="{typ}"><meta property="og:locale" content="pt_BR"><meta property="og:site_name" content="{NAME}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{image}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{image}"><link rel="icon" type="image/png" href="{pre}favicon.png"><link rel="apple-touch-icon" href="{pre}favicon.png"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="preconnect" href="https://images.pexels.com" crossorigin><link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Playfair+Display:wght@700;800&display=swap" onload="this.rel='stylesheet'"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Playfair+Display:wght@700;800&display=swap" media="print" onload="this.media='all'"><link rel="stylesheet" href="{pre}assets/style.css">{extra}</head>'''
def top(pre, cur=""):
    nav = "".join(f'<a href="{pre}index.html#{c.lower()}">{c}</a>' for c in CATS)
    tk = "".join(f'<span>● {E(a["title"])}</span>' for a in arts[:12]) * 2
    return f'''<body><a class="skip" href="#c">Pular para o conteúdo</a><div class="top"><div class="w"><span>{datetime.date.today().strftime("%d/%m/%Y")}</span><span>Fotos: Pexels · Dados: fontes citadas em cada matéria</span></div></div><header><div class="w"><a class="lg" href="{pre}index.html"><b>Portal</b>de Notícias BR</a><nav aria-label="Editorias">{nav}<a href="{pre}noticias/index.html">Todas</a></nav></div></header><div class="tk" aria-hidden="true"><div>{tk}</div></div>'''
def foot(pre): return f'''<footer><div class="w"><div><b class="lg" style="font-size:1.4rem;color:#fff">{NAME}</b><p>Notícias sobre o Brasil: política, economia, meio ambiente, turismo, esportes, tecnologia, educação, saúde e mundo.</p></div><div><a href="{pre}noticias/index.html">Todas as notícias</a> · <a href="{pre}rss.xml">RSS</a> · <a href="{pre}sitemap.xml">Sitemap</a> · <a href="{pre}llms.txt">llms.txt</a><p>Fotos do Pexels (licença gratuita); fontes de cada matéria no fim do texto.</p></div></div></footer>'''
def card(a, pre, first=False):
    return f'''<a class="cd" href="{pre}noticias/{a["slug"]}.html"><figure><img src="{src(a,pre)}" alt="{E(alt(a))}" width="800" height="500" {'' if first else 'loading="lazy" decoding="async"'}></figure><div class="b"><span class="tg">{a["cat"]}</span><h3>{E(a["title"])}</h3><p>{E(cut(a["lead"],150))}</p><small>{dt(a["date"])} · {a["mins"]} min de leitura</small></div></a>'''
def write(p, s): os.makedirs(os.path.dirname(p) or ".", exist_ok=True); open(p, "w", encoding="utf-8").write(s)
org = {"@type": "NewsMediaOrganization", "@id": B + "/#org", "name": NAME, "url": B + "/", "logo": {"@type": "ImageObject", "url": B + "/favicon.png"}}

# ---- HOME ----
hero = arts[:5]; big = arts[5]
sl = "".join(f'<article class="sl{" on" if i==0 else ""}"><img src="{src(a,"")}" alt="{E(alt(a))}" width="1600" height="900" {"fetchpriority=high" if i==0 else "loading=lazy"} decoding="async"><div class="t"><span class="tg">{a["cat"]}</span><h2><a href="noticias/{a["slug"]}.html">{E(a["title"])}</a></h2><p>{E(cut(a["lead"],160))}</p></div></article>' for i, a in enumerate(hero))
rk = "".join(f'<a href="noticias/{a["slug"]}.html"><b>{i+1}</b><span>{E(a["title"])}</span></a>' for i, a in enumerate(arts[:5]))
secs = "".join(f'<h2 class="sc" id="{c.lower()}">{c}<a href="noticias/index.html">Ver todas →</a></h2><div class="gr">{"".join(card(a,"") for a in arts if a["cat"]==c)}</div>' for c in CATS if any(a["cat"]==c for a in arts))
hd = f"{NAME}: política, economia, saúde e esportes"; hdesc = cut("Notícias atualizadas do Brasil e do mundo: segundo turno das eleições, economia, saúde, meio ambiente, esportes e tecnologia, com fontes citadas em cada matéria.", 155)
home = head("", hd, hdesc, "", src(arts[0], "", True), extra=jl({"@context": "https://schema.org", "@graph": [org, {"@type": "WebSite", "url": B + "/", "name": NAME, "inLanguage": "pt-BR", "publisher": {"@id": B + "/#org"}}, {"@type": "CollectionPage", "name": hd, "url": B + "/", "mainEntity": {"@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f'{B}/noticias/{a["slug"]}.html', "name": a["title"]} for i, a in enumerate(arts[:20])]}}]}))
home += top("") + f'<section class="hero" aria-label="Destaques">{sl}<div class="ct"><div class="dt"></div><button id="pv" aria-label="Anterior">‹</button><button id="nx" aria-label="Próximo">›</button></div></section><main class="w" id="c"><h1 class="sr">{NAME}: notícias sobre o Brasil</h1><h2 class="sc">Em destaque</h2><div class="mag"><a class="big" href="noticias/{big["slug"]}.html"><img src="{src(big,"")}" alt="{E(alt(big))}" width="1200" height="800" loading="lazy" decoding="async"><div><span class="tg">{big["cat"]}</span><h3>{E(big["title"])}</h3><p>{E(cut(big["lead"],150))}</p></div></a><aside class="rk"><h3>Mais lidas</h3>{rk}</aside></div>{secs}</main>' + foot("") + """<script>var s=document.querySelectorAll('.sl'),d=document.querySelector('.dt'),i=0,t;s.forEach(function(_,k){var e=document.createElement('i');e.onclick=function(){g(k)};d.appendChild(e)});function g(n){s[i].classList.remove('on');d.children[i].classList.remove('on');i=(n+s.length)%s.length;s[i].classList.add('on');d.children[i].classList.add('on')}function a(){clearInterval(t);t=setInterval(function(){g(i+1)},6000)}document.getElementById('pv').onclick=function(){g(i-1);a()};document.getElementById('nx').onclick=function(){g(i+1);a()};g(0);a()</script></body></html>"""
write("index.html", home)

# ---- ARQUIVO ----
fl = '<button class="on" data-c="">Todas</button>' + "".join(f'<button data-c="{c}">{c}</button>' for c in CATS if any(a["cat"]==c for a in arts))
arq = head("../", f"Todas as notícias | {NAME}", "Arquivo completo de notícias do Portal de Notícias BR, com filtro por editoria e busca.", "noticias/", src(arts[0], "../", True))
arq += top("../") + f'<main class="w" id="c"><h1 class="sc" style="font-size:2.4rem">Todas as notícias</h1><div class="fl">{fl}</div><input id="q" type="search" placeholder="Buscar notícia…" aria-label="Buscar notícia" style="width:100%;padding:.7rem 1rem;border:1px solid var(--ln);border-radius:10px;background:var(--cd);color:var(--fg);font:inherit"><div class="gr" style="margin-top:1.4rem">{"".join(card(a,"../") for a in arts)}</div></main>' + foot("../") + """<script>var B=document.querySelectorAll('.fl button'),C=document.querySelectorAll('.gr a'),Q=document.getElementById('q'),c='';function f(){C.forEach(function(x){var ok=(!c||x.querySelector('.tg').textContent==c)&&x.textContent.toLowerCase().indexOf(Q.value.toLowerCase())>-1;x.style.display=ok?'':'none'})}B.forEach(function(b){b.onclick=function(){c=b.dataset.c;B.forEach(function(y){y.classList.remove('on')});b.classList.add('on');f()}});Q.oninput=f</script></body></html>"""
write("noticias/index.html", arq)

# ---- MATERIAS ----
for a in arts:
    u, cr, _, _ = img(a); full = src(a, "../", True); path = f'noticias/{a["slug"]}.html'; url = f"{B}/{path}"
    ttl = cut(a["title"], 60) + f" | {NAME}" if len(a["title"]) > 60 else f'{a["title"]} | {NAME}'
    desc = cut(a["lead"], 155); iso = a["date"] + "T09:00:00-03:00"
    body = "".join(f"<p>{p}</p>" for p in a["body"])
    facts = f'<div class="fc"><h2>Em resumo</h2><ul>{"".join(f"<li>{f}</li>" for f in a["facts"])}</ul></div>' if a["facts"] else ""
    rel = [r for r in arts if r["cat"] == a["cat"] and r is not a][:3]
    rel = (rel + [r for r in arts if r not in rel and r is not a])[:3]
    ld = jl({"@context": "https://schema.org", "@graph": [{"@type": "NewsArticle", "headline": cut(a["title"], 110), "description": desc, "image": [full], "datePublished": iso, "dateModified": iso, "author": {"@type": "Organization", "name": NAME, "url": B + "/"}, "publisher": org, "mainEntityOfPage": url, "inLanguage": "pt-BR", "articleSection": a["cat"], "isAccessibleForFree": True},
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Início", "item": B + "/"}, {"@type": "ListItem", "position": 2, "name": a["cat"], "item": f'{B}/#{a["cat"].lower()}'}, {"@type": "ListItem", "position": 3, "name": a["title"], "item": url}]}]})
    pg = head("../", ttl, desc, path, full, "article", ld + f'<meta property="article:published_time" content="{iso}"><meta property="article:section" content="{a["cat"]}">')
    pg += top("../").replace("<body>", '<body><div class="pb" id="pb"></div>', 1)
    pg += f'<figure class="cv"><img src="{src(a,"../")}" alt="{E(alt(a))}" width="1600" height="686" fetchpriority="high" decoding="async" style="object-fit:cover"><small class="cr">{E(cr)}</small></figure><article class="ar" id="c"><nav class="bc" aria-label="Você está em"><a href="../index.html">Início</a> › <a href="../index.html#{a["cat"].lower()}">{a["cat"]}</a></nav><span class="tg">{a["cat"]}</span><h1>{E(a["title"])}</h1><p class="ld">{E(a["lead"])}</p><div class="mt">Por Redação {NAME} · <time datetime="{a["date"]}">{dt(a["date"])}</time> · {a["mins"]} min de leitura</div>{body}{facts}<p class="src">Fontes: {a["src"]}</p></article><main class="w"><h2 class="sc">Leia também</h2><div class="gr">{"".join(card(r,"../") for r in rel)}</div></main>' + foot("../")
    pg += '<script>var b=document.getElementById("pb");addEventListener("scroll",function(){var h=document.documentElement;b.style.width=(h.scrollTop/(h.scrollHeight-h.clientHeight)*100)+"%"})</script></body></html>'
    write(path, pg)

# ---- SITEMAP / RSS / LLMS / ROBOTS / HTACCESS ----
today = max(a["date"] for a in arts)
sm = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n<url><loc>{B}/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>\n<url><loc>{B}/noticias/</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>\n'
for a in arts: sm += f'<url><loc>{B}/noticias/{a["slug"]}.html</loc><lastmod>{a["date"]}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority><image:image><image:loc>{E(src(a,"",True))}</image:loc></image:image></url>\n'
write("sitemap.xml", sm + "</urlset>\n")
items = "".join(f'<item><title>{E(a["title"])}</title><link>{B}/noticias/{a["slug"]}.html</link><guid>{B}/noticias/{a["slug"]}.html</guid><pubDate>{format_datetime(datetime.datetime.fromisoformat(a["date"]+"T09:00:00-03:00"))}</pubDate><category>{a["cat"]}</category><description>{E(cut(a["lead"],200))}</description></item>' for a in arts[:30])
write("rss.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{NAME}</title><link>{B}/</link><description>Notícias do Brasil e do mundo</description><language>pt-BR</language>{items}</channel></rss>')
write("llms.txt", f"# {NAME}\n\n> Portal de notícias sobre o Brasil em português, com fontes citadas em cada matéria.\n\n## Páginas\n- [Início]({B}/)\n- [Todas as notícias]({B}/noticias/)\n- [RSS]({B}/rss.xml)\n\n## Notícias\n" + "".join(f'- [{a["title"]}]({B}/noticias/{a["slug"]}.html): {cut(a["lead"],160)}\n' for a in arts))
write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {B}/sitemap.xml\n")
write(".htaccess", 'AddDefaultCharset UTF-8\n<IfModule mod_deflate.c>\nAddOutputFilterByType DEFLATE text/html text/css application/xml application/rss+xml text/plain\n</IfModule>\n<IfModule mod_expires.c>\nExpiresActive On\nExpiresByType text/css "access plus 1 month"\nExpiresByType image/png "access plus 1 year"\nExpiresByType image/jpeg "access plus 1 year"\nExpiresByType text/html "access plus 10 minutes"\n</IfModule>\nRewriteEngine On\nRewriteCond %{HTTPS} off\nRewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]\n')
print(len(arts), "materias geradas;", "imagens Pexels:", len(imgs))
