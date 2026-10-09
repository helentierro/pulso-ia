#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PULSO IA - agregador RSS de noticias de inteligencia artificial.

Descarga feeds gratuitos (sin API key), limpia el texto, clasifica por
categoria, agrupa noticias equivalentes entre medios y genera
data/news.json + data/news.js (el ultimo para abrir con doble clic).

Uso:  python fetch_news.py
"""
import json
import os
import re
import gzip
import html
import sys
import socket
import traceback
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from email.utils import parsedate_to_datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
OUT_JSON = os.path.join(DATA_DIR, "news.json")
OUT_JS = os.path.join(DATA_DIR, "news.js")

MAX_POR_FEED = 14
MAX_TOTAL = 130
MAX_EDAD_HORAS = 96
EDAD_BLOG = 336
EDAD_PAPER = 96
EDAD_ES = 60
UMBRAL_CLUSTER = 0.6
LARGO_RESUMEN = 300

CATEGORIAS = ["modelos", "producto", "empresas", "investigacion", "politica", "hardware"]

ETIQUETAS = {
    "modelos": "Modelos",
    "producto": "Producto",
    "empresas": "Empresas",
    "investigacion": "Investigacion",
    "politica": "Politica",
    "hardware": "Hardware",
}

FUENTES = [
    ("OpenAI", "https://openai.com/news/rss.xml", "modelos", 4, "oficial", EDAD_BLOG),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", "investigacion", 4, "oficial", EDAD_BLOG),
    ("Google AI", "https://blog.google/technology/ai/rss/", "producto", 3, "oficial", EDAD_BLOG),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml", "producto", 3, "oficial", EDAD_BLOG),
    ("Microsoft", "https://blogs.microsoft.com/feed/", "empresas", 3, "oficial", EDAD_BLOG),
    ("Azure", "https://azure.microsoft.com/en-us/blog/feed/", "producto", 2, "oficial", EDAD_BLOG),
    ("AWS ML", "https://aws.amazon.com/blogs/machine-learning/feed/", "producto", 2, "oficial", EDAD_BLOG),
    ("Google Cloud", "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/", "producto", 2, "oficial", EDAD_BLOG),
    ("NVIDIA", "https://blogs.nvidia.com/feed/", "hardware", 3, "oficial", EDAD_BLOG),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "empresas", 3, "prensa", EDAD_BLOG),
    ("SiliconANGLE", "https://siliconangle.com/feed/", "empresas", 2, "prensa", EDAD_BLOG),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "producto", 3, "prensa", EDAD_BLOG),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab", "producto", 2, "prensa", EDAD_BLOG),
    ("The Decoder", "https://the-decoder.com/feed/", "modelos", 3, "prensa", EDAD_BLOG),
    ("MIT Tech Review", "https://www.technologyreview.com/topic/artificial-intelligence/feed", "investigacion", 3, "prensa", EDAD_BLOG),
    ("Import AI", "https://importai.substack.com/feed", "investigacion", 2, "prensa", EDAD_BLOG),
    ("MarkTechPost", "https://www.marktechpost.com/feed/", "modelos", 1, "prensa", EDAD_BLOG),
    ("arXiv cs.AI", "http://export.arxiv.org/rss/cs.AI", "investigacion", 2, "paper", EDAD_PAPER),
    ("arXiv cs.LG", "http://export.arxiv.org/rss/cs.LG", "investigacion", 1, "paper", EDAD_PAPER),
    ("GNews ES", "https://news.google.com/rss/search?q=(%22inteligencia+artificial%22+OR+%22IA+generativa%22+OR+%22modelo+de+lenguaje%22)+when:2d&hl=es-419&gl=MX&ceid=MX%3Aes-419", "producto", 1, "es", EDAD_ES),
    ("GNews Modelos", "https://news.google.com/rss/search?q=(%22nuevo+modelo%22+OR+GPT+OR+Claude+OR+Gemini)+when:2d&hl=es-419&gl=MX&ceid=MX%3Aes-419", "modelos", 1, "es", EDAD_ES),
    ("GNews Empresas", "https://news.google.com/rss/search?q=(OpenAI+OR+Anthropic+OR+Meta)+(inversi%C3%B3n+OR+acuerdo+OR+empleo)+when:3d&hl=es-419&gl=MX&ceid=MX%3Aes-419", "empresas", 1, "es", EDAD_ES),
    ("GNews Politica", "https://news.google.com/rss/search?q=%22inteligencia+artificial%22+(regulaci%C3%B3n+OR+ley+OR+%22Uni%C3%B3n+Europea%22)+when:3d&hl=es-419&gl=MX&ceid=MX%3Aes-419", "politica", 1, "es", EDAD_ES),
    ("GNews Hardware", "https://news.google.com/rss/search?q=(Nvidia+OR+GPU+OR+%22chip%22)+IA+when:2d&hl=es-419&gl=MX&ceid=MX%3Aes-419", "hardware", 1, "es", EDAD_ES),
    # --- Anadidas para ampliar cobertura (verificadas 200) ---
    ("Ahead of AI", "https://magazine.sebastianraschka.com/feed", "investigacion", 3, "prensa", EDAD_BLOG),
    ("Last Week in AI", "https://lastweekin.ai/feed", "investigacion", 2, "prensa", EDAD_BLOG),
    ("Simon Willison", "https://simonwillison.net/atom/everything/", "producto", 3, "prensa", EDAD_BLOG),
    ("The Rundown AI", "https://www.therundown.ai/feed", "producto", 2, "prensa", EDAD_BLOG),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss", "politica", 2, "prensa", EDAD_BLOG),
]

PALABRAS = {
    "modelos": [
        "gpt", "chatgpt", "claude", "gemini", "llama", "mistral", "deepseek", "qwen",
        "grok", "frontier model", "language model", "foundation model", "reasoning model",
        "multimodal", "fine-tun", "context window", "small language model", "open weights",
        "modelo", "modelos", "llm", "rag", "agente", "agentes", "agents", "superinteligencia",
        "distillation", "inferencia", "reasoning",
    ],
    "empresas": [
        "funding", "raises", "valuation", "startup", "acquisition", "acquires", "acquired",
        "merger", "ipo", "revenue", "profit", "layoffs", "hires", "partnership",
        "collaboration", "investors", "venture", "billion", "million", "series a",
        "financiaci\u00f3n", "inversi\u00f3n", "ronda", "mill\u00f3n", "millones", "billon",
        "adquiere", "alianza", "socios", "empleo", "sueldos", "accionista",
    ],
    "investigacion": [
        "paper", "preprint", "arxiv", "research", "study", "studies", "scientists",
        "benchmark", "dataset", "evaluation", "state-of-the-art", "sota", "ablation",
        "neural network", "alignment", "interpretability", "hallucination", "cognitive",
        "aprendizaje", "teor\u00eda", "estudio", "investigaci\u00f3n", "tesis", "art\u00edculo",
        "hallazgo", "publicado", "docencia",
    ],
    "hardware": [
        "gpu", "tpu", "nvidia", "blackwell", "rubin", "hopper", "hbm", "wafer", "foundry",
        "semiconductor", "chip", "chips", "silicon", "datacenter", "data center", "cluster",
        "compute", "asic", "tsmc", "acelerador", "procesador", "centro de datos",
        "supercomputador", "memoria",
    ],
    "politica": [
        "regulation", "regulatory", "policy", "legislation", "law", "bill", "senate",
        "congress", "ai act", "copyright", "lawsuit", "sued", "court", "ban", "banned",
        "antitrust", "privacy", "gdpr", "export control", "compliance", "guardrails",
        "regulaci\u00f3n", "ley", "normativa", "europea", "europeo", "uni\u00f3n europea",
        "congreso", "senado", "demanda", "tribunal", "prohibici\u00f3n", "seguridad",
    ],
    "producto": [
        "app", "feature", "launch", "launches", "launched", "rolls out", "assistant",
        "copilot", "chatbot", "api", "plugin", "integration", "browser", "available",
        "subscription", "beta", "rollout", "workspace", "generative", "aplicaci\u00f3n",
        "funci\u00f3n", "lanza", "lanzamiento", "disponible", "navegador", "asistente",
        "integraci\u00f3n", "suscripci\u00f3n", "v\u00eddeo",
    ],
}

VACIAS = {
    "the", "and", "for", "with", "that", "this", "from", "has", "have", "are", "was",
    "were", "will", "its", "his", "her", "their", "you", "your", "our", "not", "but",
    "all", "can", "new", "more", "into", "out", "how", "why", "what", "when", "who",
    "about", "after", "over", "than", "then", "they", "them", "these", "those", "which",
    "while", "del", "las", "los", "una", "uno", "unos", "unas", "con", "por", "para",
    "como", "mas", "pero", "que", "sus", "ya", "son", "fue", "hay", "ante", "entre",
    "sobre", "tras", "hasta", "desde", "este", "esta", "estos", "estas", "asi", "muy",
    "cada", "todo", "toda", "esto", "aqui", "hace", "announces", "launches", "says",
}

ENTIDADES = [
    ("OpenAI", ["openai", "chatgpt", "sam altman"]),
    ("Anthropic", ["anthropic", "claude"]),
    ("Google", ["google", "gemini", "deepmind", "alphabets"]),
    ("Microsoft", ["microsoft", "copilot", "azure"]),
    ("Meta", ["meta ai", "llama", "zuckerberg"]),
    ("Nvidia", ["nvidia", "jensen huang", "blackwell"]),
    ("xAI", ["xai", "grok"]),
    ("Amazon", ["amazon", "aws", "bedrock"]),
    ("Apple", ["apple", "tim cook"]),
    ("Mistral", ["mistral"]),
    ("DeepSeek", ["deepseek"]),
    ("Qwen", ["qwen", "alibaba"]),
    ("Hugging Face", ["hugging face"]),
    ("Perplexity", ["perplexity"]),
    ("Cohere", ["cohere"]),
    ("IBM", ["ibm", "watsonx"]),
    ("Elon Musk", ["elon musk"]),
    ("Sam Altman", ["sam altman"]),
    ("UE", ["uni\u00f3n europea", "european union", "ai act", "bruselas", "brussels"]),
    ("EEUU", ["estados unidos", "washington", "united states", "white house"]),
    ("ElevenLabs", ["elevenlabs"]),
    ("Suno", ["suno"]),
    ("Runway", ["runway ml"]),
    ("Midjourney", ["midjourney"]),
    ("Cursor", ["cursor ai", "anysphere"]),
    ("LangChain", ["langchain", "llamaindex"]),
    ("Databricks", ["databricks"]),
    ("CoreWeave", ["coreweave"]),
]

RUIDO = [
    r"the post .{0,140} appeared first on .{0,60}",
    r"continue reading.{0,60}",
    r"read more.{0,60}",
    r"\[caption[^\]]{0,200}\]",
    r"\[photo[^\]]{0,200}\]",
    r"image:\s*\S+",
    r"click here.{0,60}",
    r"^\s*anuncio[s]?\b.{0,120}",
    r"^\s*publicidad\b.{0,120}",
    r"^\s*newsletter.{0,120}",
    r"^\s*suscr[i\u00ed]bete.{0,120}",
    r"^\s*listen to this article.{0,60}",
    r"getty images.{0,80}",
]

UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0 Safari/537.36 PulsoIA/2.0",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.7",
    "Accept-Encoding": "gzip",
}


class Redireccion308(HTTPRedirectHandler):
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, 301, msg, headers)


OPENER = build_opener(Redireccion308)


def local(etiqueta):
    return etiqueta.rsplit("}", 1)[-1].lower() if "}" in etiqueta else etiqueta.lower()


def texto_bruto(el):
    if el is None:
        return ""
    partes = [el.text or ""]
    for hijo in el:
        partes.append(texto_bruto(hijo))
        partes.append(hijo.tail or "")
    return " ".join(partes)


def sin_espacios(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def limpiar(texto, quitar_cola=True):
    s = re.sub(r"<[^>]+>", " ", texto or "")
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u2028", " ").replace("\u200b", "")
    for patron in RUIDO:
        s = re.sub(patron, " ", s, flags=re.I | re.M)
    if quitar_cola:
        s = re.sub(r"\s+[\|\u2013\u2014]\s+[^\|\u2013\u2014]{2,45}$", "", s)
    s = sin_espacios(s).strip(" -\u00b7|\u2013\u2014:,.")
    return re.sub(r"^[\-\u2022\u00b7\|\s]+", "", s)


def limpiar_titulo(titulo):
    t = html.unescape(titulo or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\$[^$]{1,60}\$", " ", t)
    t = re.sub(r"\\[a-zA-Z]{2,10}", " ", t)
    t = sin_espacios(t).strip(" -\u00b7|\u2013\u2014")
    m = re.match(r"^(.{25,}?)\s+[\-|\u2013\u2014]\s+([^\-|\u2013\u2014]{2,45})$", t)
    if m and m.group(2).strip():
        return m.group(1).strip(), m.group(2).strip()
    return t, ""


def parse_fecha(valor):
    if not valor:
        return None
    valor = valor.strip()
    dt = None
    try:
        dt = parsedate_to_datetime(valor)
    except Exception:
        try:
            dt = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def leer_bytes(url):
    peticion = Request(url, headers=UA_HEADERS)
    with OPENER.open(peticion, timeout=25) as respuesta:
        crudo = respuesta.read()
        if respuesta.headers.get("Content-Encoding") == "gzip":
            crudo = gzip.decompress(crudo)
    return crudo


def descargar(url, intentos=2):
    error = ""
    for intento in range(intentos):
        try:
            return ET.fromstring(leer_bytes(url))
        except HTTPError as e:
            error = "HTTP {}".format(e.code)
            if e.code in (401, 403, 404, 410, 451):
                break
        except URLError as e:
            error = "red: {}".format(str(getattr(e, "reason", e))[:55])
        except socket.timeout:
            error = "red: timeout"
        except ET.ParseError as e:
            error = "xml: {}".format(str(e)[:55])
        except Exception as e:
            error = "{}: {}".format(type(e).__name__, str(e)[:55])
    raise RuntimeError(error or "sin respuesta")


def mapa_de(el):
    mapa = {}
    for hijo in el.iter():
        mapa.setdefault(local(hijo.tag), hijo)
    return mapa


def items_de(root):
    return [el for el in root.iter() if local(el.tag) in ("item", "entry")]


def imagen_de(mapa):
    for nombre in ("enclosure", "thumbnail", "content", "image", "title"):
        nodo = mapa.get(nombre)
        if nodo is None:
            continue
        for atributo in ("url", "href"):
            valor = (nodo.get(atributo) or "").strip()
            if valor.startswith("http") and re.search(r"\.(jpe?g|png|webp|avif)", valor, re.I):
                return valor
    return ""


def enlace_de(el):
    por_texto = []
    por_href = []
    for hijo in el:
        if local(hijo.tag) != "link":
            continue
        texto = (hijo.text or "").strip()
        if texto.startswith("http"):
            por_texto.append(texto)
        href = (hijo.get("href") or "").strip()
        if not href.startswith("http"):
            continue
        rel = (hijo.get("rel") or "").lower()
        tipo = (hijo.get("type") or "").lower()
        if rel == "self":
            continue
        peso = 0 if rel in ("", "alternate") else 1
        if tipo and "html" not in tipo:
            peso += 2
        por_href.append((peso, href))
    if por_texto:
        return por_texto[0]
    if por_href:
        por_href.sort(key=lambda x: x[0])
        return por_href[0][1]
    return ""


def clasificar(texto):
    bajo = (texto or "").lower()
    puntos = [(categoria, sum(1 for p in lista if p in bajo))
              for categoria, lista in PALABRAS.items()]
    puntos.sort(key=lambda x: x[1], reverse=True)
    if not puntos or puntos[0][1] < 2:
        return None
    if puntos[1][1] > 0 and puntos[0][1] < puntos[1][1] * 1.35:
        return None
    return puntos[0][0]


CORTO_SIGNIFICATIVO = {
    "gpt", "ai", "llm", "agi", "moe", "sora", "grok", "api", "gpu", "tpu",
    "o1", "o3", "o4", "v2", "v3", "v4", "v5", "4o", "r1", "nvidia", "aws",
}

RUIDO_TITULO = [
    r"olimpiada", r"requisitos", r"convocatoria", r"inscripci", r"\btaller\b",
    r"\bcurso\b", r"\bbecas?\b", r"concurso", r"tr\u00e1mite", r"c\u00f3mo crear",
    r"c\u00f3mo usar", r"qu\u00e9 es", r"trucos", r"plantillas", r"gu\u00eda de",
    r"qu\u00e9ered\u00eds", r"webinar", r"infograf\u00eda", r"\breceta\b",
    r"regala", r"descuento", r"cup\u00f3n", r"promoci\u00f3n", r"\boferta\b",
    r"hor\u00f3scopo", r"zodiaco", r"\brecipe\b",
]

FRASES_IA = [
    "inteligencia artificial", "aprendizaje autom\u00e1tico", "aprendizaje automatico",
    "machine learning", "modelo de lenguaje", "modelos de lenguaje", "centro de datos",
    "red neuronal", "redes neuronales", "aprendizaje profundo", "deep learning",
    "generativa", "generativo", "automatizaci\u00f3n", "automatizacion",
    "asistente virtual", "multimodal", "fine-tuning", "fine tuning", "inferencia",
    "c\u00e1mputo", "supercomputadora", "open source", "c\u00f3digo abierto",
]

PALABRAS_IA = [
    "ia", "ai", "gpt", "gpu", "tpu", "llm", "chip", "chips", "nvidia", "openai",
    "anthropic", "claude", "gemini", "deepseek", "chatbot", "copilot", "midjourney",
    "sora", "perplexity", "mistral", "llama", "tsmc", "intel", "amd", "algoritmo",
    "robot", "robotica", "agente", "agentes", "modelo", "modelos", "dataset",
    "prompt", "prompts", "asistente", "openai", "datacenter", "hbm", "blackwell",
]

RE_IA = re.compile(
    "|".join([r"\b" + re.escape(p) + r"\b" for p in PALABRAS_IA] + [re.escape(f) for f in FRASES_IA]),
    re.I,
)


def es_noticia_ai(titulo):
    return bool(RE_IA.search(titulo or ""))


def significativas(titulo):
    palabras = re.findall(r"[a-z0-9\u00c0-\u024f]+", (titulo or "").lower())
    return {p for p in palabras
            if (len(p) > 3 or p in CORTO_SIGNIFICATIVO) and p not in VACIAS}


def entidad_de(texto):
    bajo = (texto or "").lower()
    for nombre, claves in ENTIDADES:
        for clave in claves:
            if clave in bajo:
                return nombre
    return ""


def resumen_de_google(html_desc, titulo):
    m = re.search(r"<a[^>]*>(.*?)</a>", html_desc or "", re.S | re.I)
    if not m:
        return ""
    texto = limpiar(m.group(1), quitar_cola=False)
    if len(texto) < 45 or texto.lower() == (titulo or "").lower():
        return ""
    return texto[:LARGO_RESUMEN].rsplit(" ", 1)[0] + "..."


def recortar(texto):
    if len(texto) <= LARGO_RESUMEN:
        return texto
    return texto[:LARGO_RESUMEN].rsplit(" ", 1)[0] + "..."


def procesar(nombre, url, cat_defecto, prioridad, tipo, edad_horas=EDAD_BLOG):
    try:
        root = descargar(url)
    except Exception as e:
        return [], {"name": nombre, "kind": tipo, "ok": False, "count": 0, "error": str(e)[:60]}

    ahora = datetime.now(timezone.utc)
    es_google = "news.google." in url
    vistos = set()
    items = []
    leidos = 0
    sin_fecha = 0
    sin_enlace = 0
    titulo_mal = 0
    viejo = 0
    repetido = 0

    for el in items_de(root)[: MAX_POR_FEED * 3]:
        mapa = mapa_de(el)
        nodo_titulo = mapa.get("title")
        if nodo_titulo is None:
            continue
        leidos += 1

        titulo, pista_editor = limpiar_titulo(texto_bruto(nodo_titulo))
        if len(titulo) < 15 or len(titulo) > 220:
            titulo_mal += 1
            continue
        if es_google:
            bajo = titulo.lower()
            if any(re.search(p, bajo) for p in RUIDO_TITULO) or not es_noticia_ai(titulo):
                titulo_mal += 1
                continue

        enlace = enlace_de(el)
        if not enlace:
            sin_enlace += 1
            continue

        fecha = None
        for clave in ("pubdate", "published", "updated", "date", "created", "issued", "modified"):
            nodo = mapa.get(clave)
            if nodo is not None:
                fecha = parse_fecha(nodo.text)
                if fecha:
                    break
        if not fecha:
            sin_fecha += 1
            continue
        if ahora - fecha > timedelta(hours=edad_horas):
            viejo += 1
            continue
        if fecha > ahora + timedelta(hours=6):
            viejo += 1
            continue

        resumen = ""
        nodo_desc = mapa.get("description")
        html_desc = texto_bruto(nodo_desc) if nodo_desc is not None else ""
        if es_google:
            resumen = resumen_de_google(html_desc, titulo)
        else:
            for clave in ("description", "summary", "encoded", "content", "subtitle"):
                nodo = mapa.get(clave)
                if nodo is not None:
                    resumen = limpiar(texto_bruto(nodo), quitar_cola=False)
                    if resumen:
                        break
            if resumen.lower() == titulo.lower():
                resumen = ""
            else:
                resumen = recortar(resumen)

        fuente = pista_editor if es_google else ""
        if len(fuente) < 2:
            fuente = nombre

        categoria = clasificar(titulo + " " + resumen) or cat_defecto
        if categoria not in CATEGORIAS:
            categoria = cat_defecto

        llave = re.sub(r"[^a-z0-9]", "", titulo.lower())[:80]
        if llave in vistos:
            repetido += 1
            continue
        vistos.add(llave)

        items.append({
            "title": titulo,
            "link": enlace,
            "summary": resumen,
            "source": fuente,
            "feed": nombre,
            "kind": tipo,
            "category": categoria,
            "entity": entidad_de(titulo),
            "published": fecha.isoformat().replace("+00:00", "Z"),
            "image": imagen_de(mapa),
            "priority": prioridad,
            "_sig": significativas(titulo),
            "_ts": fecha.timestamp(),
        })

    items.sort(key=lambda x: x["_ts"], reverse=True)
    items = items[:MAX_POR_FEED]
    estado = {"name": nombre, "kind": tipo, "ok": bool(items), "count": len(items),
              "leidos": leidos, "sin_fecha": sin_fecha, "sin_enlace": sin_enlace,
              "titulo_mal": titulo_mal, "viejo": viejo, "repetido": repetido,
              "error": "" if items else "0 validos de {} | titulo {} | viejo {} | sin_fecha {} | sin_enlace {}".format(
                  leidos, titulo_mal, viejo, sin_fecha, sin_enlace)}
    return items, estado


def agrupar(items):
    grupos = []
    for item in items:
        firma = item["_sig"]
        if len(firma) < 3:
            grupos.append([item])
            continue
        puesto = False
        for grupo in grupos:
            base = grupo[0]["_sig"]
            if len(base) < 3:
                continue
            union = len(firma | base)
            if union and len(firma & base) / union >= UMBRAL_CLUSTER:
                grupo.append(item)
                puesto = True
                break
        if not puesto:
            grupos.append([item])
    return grupos


def cargar_previo():
    try:
        with open(OUT_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def construir(ahora, todos, salud, transcurrido):
    grupos = agrupar(todos)
    noticias = []
    for grupo in grupos:
        grupo.sort(key=lambda x: x["_ts"], reverse=True)
        principal = grupo[0]
        horas = max(0.0, (ahora.timestamp() - principal["_ts"]) / 3600.0)
        otras = [g for g in grupo[1:5] if g["source"] != principal["source"]]
        noticias.append({
            "title": principal["title"],
            "link": principal["link"],
            "summary": principal["summary"],
            "source": principal["source"],
            "feed": principal["feed"],
            "kind": principal["kind"],
            "category": principal["category"],
            "entity": principal["entity"],
            "published": principal["published"],
            "image": principal["image"] or (grupo[1]["image"] if len(grupo) > 1 else ""),
            "flash": horas < 1.2,
            "age_h": round(horas, 1),
            "heat": round(max(0.0, 1.0 - horas / 26.0)
                          + (1.3 if len(grupo) > 1 else 0.0)
                          + (0.25 if principal["summary"] else 0.0)
                          + (0.20 if (principal["image"] or (grupo[1]["image"] if len(grupo) > 1 else "")) else 0.0)
                          + principal["priority"] * 0.12, 3),
            "also": [{"source": o["source"], "link": o["link"]} for o in otras],
        })

    noticias.sort(key=lambda x: x["heat"], reverse=True)
    agrupadas = len(todos) - len(noticias)
    noticias = noticias[:MAX_TOTAL]
    portada = noticias[0] if noticias else None
    resto = sorted(noticias[1:], key=lambda x: x["published"], reverse=True) if noticias else []

    conteo = {c: 0 for c in CATEGORIAS}
    entidades = {}
    for n in noticias:
        conteo[n["category"]] = conteo.get(n["category"], 0) + 1
        if n.get("entity"):
            entidades[n["entity"]] = entidades.get(n["entity"], 0) + 1

    return {
        "generated_at": ahora.isoformat().replace("+00:00", "Z"),
        "checked_at": ahora.isoformat().replace("+00:00", "Z"),
        "took_sec": round(transcurrido, 1),
        "interval_min": 15,
        "feeds_total": len(FUENTES),
        "feeds_ok": len([s for s in salud if s["ok"]]),
        "grouped": agrupadas,
        "count": len(noticias),
        "labels": ETIQUETAS,
        "by_category": conteo,
        "top_entities": [{"name": k, "count": v}
                         for k, v in sorted(entidades.items(), key=lambda x: x[1], reverse=True)[:9]],
        "sources": sorted({n["feed"] for n in noticias}),
        "health": salud,
        "lead": portada,
        "items": resto,
    }


def main():
    inicio = datetime.now(timezone.utc)
    print("  PULSO IA - descargando {} fuentes en paralelo...".format(len(FUENTES)))

    resultados = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futuros = [(f[0], pool.submit(procesar, *f)) for f in FUENTES]
        for nombre, futuro in futuros:
            try:
                items, estado = futuro.result()
            except Exception as e:
                items = []
                estado = {"name": nombre, "kind": "?", "ok": False, "count": 0,
                          "error": "{}: {}".format(type(e).__name__, str(e)[:50])}
            resultados.append((nombre, items, estado))

    orden = {f[0]: i for i, f in enumerate(FUENTES)}
    resultados.sort(key=lambda r: orden.get(r[0], 999))

    todos = []
    salud = []
    for nombre, items, estado in resultados:
        todos.extend(items)
        salud.append(estado)
        if estado["ok"]:
            print("  OK    {:<18} {:>2} de {:>2}".format(nombre, estado["count"], estado["leidos"]))
        else:
            print("  FALLA {:<18} {}".format(nombre, estado["error"]))

    ahora = datetime.now(timezone.utc)
    payload = construir(ahora, todos, salud, (ahora - inicio).total_seconds())
    anteriores = None

    if not todos:
        previo = cargar_previo()
        if previo.get("lead") or previo.get("items"):
            print("  AVISO  sin items nuevos -> conservo el archivo anterior")
            anteriores = previo

    if anteriores is not None:
        for clave in ("generated_at", "labels", "by_category", "top_entities",
                      "sources", "lead", "items", "count"):
            if clave in anteriores:
                payload[clave] = anteriores[clave]
        payload["stale"] = True
    else:
        payload["stale"] = not todos

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("window.PULSO_DATA = ")
        json.dump(payload, f, ensure_ascii=False)
        f.write(";\n")

    portada = payload.get("lead") or {}
    print("")
    print("  {} noticias | {} duplicadas agrupadas | {}/{} feeds ok | {}s".format(
        payload.get("count", 0), payload.get("grouped", 0), payload["feeds_ok"],
        payload["feeds_total"], payload["took_sec"]))
    if portada.get("title"):
        print("  Portada: {}".format(portada["title"][:76]))
    print("  {}".format(OUT_JSON))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
