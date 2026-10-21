#!/usr/bin/env python3
"""Busca 1 foto UNICA do Pexels para cada materia. Uso: python pexels.py SUA_CHAVE
Chave gratis em https://www.pexels.com/api/ . Gera imagens.json (nao repete IDs)."""
import json, sys, os, time, urllib.request, urllib.parse
KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PEXELS_API_KEY", "")
if not KEY: sys.exit("Informe a chave: python pexels.py SUA_CHAVE")
Q = {  # palavras-chave em ingles (o Pexels responde melhor)
"segundo-turno-25-de-outubro":"voting election","governadores-segundo-turno":"government building brasilia","datafolha-flavio-47-lula-45-segundo-turno":"survey poll people",
"fenaj-manifesta-indignacao-com-formato-do-debate-da-tv-band":"television debate studio","moradores-da-mare-se-mobilizam-para-divulgar-locais-de-votacao":"favela community rio",
"tre-rj-alterou-apenas-um-local-de-votacao-no-estado-confira":"polling station","mp-pede-ao-tse-divulgacao-ampla-de-mudancas-em-locais-de-votacao":"courthouse justice",
"ipca-setembro-082-acumulado-458":"supermarket prices","selic-13-75-proximo-copom":"central bank money","inpe-mma-el-nino-pantanal":"pantanal wetland",
"cerrado-lidera-focos-caatinga":"wildfire savanna","cop31-antalya-9-a-20-novembro":"climate conference","gp-sao-paulo-2026-sem-sprint":"formula one race car",
"bortoleto-interlagos-contrato-2030":"racing circuit grandstand","embratur-projeta-10-milhoes-turistas":"tourists rio beach","origem-turistas-argentina-chile-eua":"airport travelers",
"marco-legal-ia-pl-2338-camara":"artificial intelligence robot","especialista-seo-mateus-maranho":"seo laptop analytics","enem-2026-8-e-15-de-novembro":"students exam classroom",
"revalida-2026-2-divulgado-resultado-de-casos-de-logistica-e-de-saude":"doctor stethoscope","hipertensao-atinge-28-de-criancas-e-adolescentes-mostra-estudo":"blood pressure child",
"orgao-especial-do-tjrj-confirma-vasco-x-boca-juniors-no-maracana":"maracana football stadium","nobel-paz-2026-navi-pillay":"oslo city hall",
"dolar-ibovespa-balancos-bancos-21-outubro":"stock market screen","receita-devolucao-recorde-41-bilhoes-imposto-de-renda-2026":"tax documents calculator",
"sus-oferece-nove-medicamentos-oncologicos-de-alta-tecnologia":"pharmacy medicine","itamaraty-classifica-declaracoes-de-milei-como-inaceitaveis":"diplomacy flags meeting",
"flamengo-supera-botafogo-no-classico-carioca-do-nbb":"basketball game","pediatras-alertam-para-riscos-de-brinquedos-com-ia":"child robot toy",
"quedas-mais-de-330-mil-criancas-internadas-em-10-anos":"child playground"}
def get(q, page):
    u = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": 30, "page": page, "orientation": "landscape", "locale": "pt-BR"})
    r = urllib.request.Request(u, headers={"Authorization": KEY, "User-Agent": "portalnoticiasbr"})
    return json.load(urllib.request.urlopen(r, timeout=20))["photos"]
out, used = {}, set()
if os.path.exists("imagens.json"):
    out = json.load(open("imagens.json", encoding="utf-8")); used = {v["id"] for v in out.values()}
for slug, q in Q.items():
    if slug in out: continue
    for page in (1, 2, 3):
        hit = next((p for p in get(q, page) if p["id"] not in used), None)
        if hit: break
    if not hit: print("sem foto:", slug); continue
    used.add(hit["id"])
    out[slug] = {"id": hit["id"], "url": hit["src"]["landscape"], "page": hit["url"], "by": hit["photographer"], "alt": hit.get("alt") or q}
    print("ok", slug, hit["id"]); time.sleep(0.4)
json.dump(out, open("imagens.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "fotos unicas salvas em imagens.json. Agora rode: python build.py")
