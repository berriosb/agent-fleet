# Stack de memoria de vault para Hermes (hwiki + node-search + hermes-vcc)

Guia de operacion del stack que convierte un vault Markdown en memoria de
Hermes. Probado en el perfil `aura` con el vault
`~/Proyectos/AI/memorias-bastian` (2026-10-29).

## Por que este stack y no una DB vectorial propia

El problema que se queria resolver NO era "la busqueda es lenta" — `grep -rn`
sobre 327 notas tarda **0.096 s**. El problema era el **numero de rondas de
herramienta**: cada ronda es una llamada completa al modelo sobre 127k-497k
tokens de contexto. Medido en 37 sesiones de empleo: p90 = 30 tool calls antes
de la primera respuesta, 74.8% de las llamadas tocaban el vault.

Benchmark de 7 consultas reales (mismo vault, mismo corpus):

| Metrica | `grep` + `read_file` | `hwiki` (`wiki_memory_search`) |
|---|---|---|
| Latencia mediana | 39.3 ms | 40.7 ms |
| Caracteres utiles devueltos | 2.735 | **16.439** |
| Rondas hasta responder | **28** | **7** |

Empate en latencia, 4x menos rondas. `grep` devuelve *rutas*; `hwiki` devuelve
el *snippet con la respuesta dentro*.

## Principio: no meter GPU en el camino caliente

El vault ya **es** un LLM-wiki en el sentido de Karpathy (abril 2026):
markdown en git, `index.md` como catalogo, wikilinks como sintesis, y
**embeddings opcionales** — a escala de cientos de paginas, indice + `grep`
basta. Ese es el modelo; no hay que construir una DB vectorial encima.

Regla operativa para vaults de este tamano (~300 paginas):

- **FTS5/BM25 es el backend.** hwiki solo invoca qmd si `backend != "fts5"`
  (`search.py:708-710`). Con FTS5 el camino caliente es 100% CPU.
- **qmd queda instalado pero manual.** En hardware con GPU chica (MX250 de
  2 GB), `qmd query` carga embedding + reranker + expansion de query a la vez
  y muere con `ErrorOutOfDeviceMemory`; `vsearch` tarda 11,9 s en GPU y
  **70 s en CPU**. Si se invoca a mano, va con `QMD_FORCE_CPU=1`.
- **ollama puede quedar idle**: 0 modelos cargados, es solo el servidor.

Antes de agregar embeddings, responder: el problema era la lentitud de la
busqueda o el **numero de rondas**? Si fueron las rondas, los embeddings no
ayudan: agregan latencia, no eliminan vueltas.

## hwiki — el vault como memoria

`hwiki` indexa una carpeta de markdown y expone `wiki_memory_search`,
`wiki_memory_read`, `wiki_memory_write`, `wiki_memory_status`. Ademas inyecta
prefetch automatico antes de cada turno (28 ms medidos).

Instalar: `hermes -p <perfil> plugins install hwiki --yes-deps --enable`

Config en `~/.hermes/profiles/<perfil>/hwiki.json`:

```json
{
  "wiki_path": "/ruta/al/vault",
  "backend": "fts5",
  "memory_dir": "Agentes/<Agente>/hwiki-memory",
  "exclude": ["_archived/*", "Templates/*", ".claude/*"],
  "auto_recall": true,
  "mirror_builtin_memory": false,
  "demote_paths": ["_archived/*"]
}
```

Claves que importan:

- **`memory_dir`** — donde escribe hwiki. Debe ser una subcarpeta del workspace
  del agente dentro del vault, nunca una nota curada. Sin esto, hwiki escribe
  sus notas auto-mantenidas en cualquier parte del vault.
- **`exclude`** — `Templates/` no son notas (no tienen frontmatter por diseno);
  `_archived/` es historico. Excluir reduce el ruido del recall.
- **`mirror_builtin_memory: false`** — si es `true`, hwiki escribe una copia de
  `MEMORY.md`/`USER.md` dentro del vault. Duplica la memoria y contamina.
- **`demote_paths`** — baja la posicion de paths ruidosos en el ranking sin
  excluirlos.

Indexar y consultar:
```bash
hermes -p <perfil> hwiki index
hermes -p <perfil> hwiki search "consulta"
hermes -p <perfil> hwiki status
```

El indice vive en `$HERMES_HOME/hwiki-index.sqlite` (descartable, se
reconstruye). Tablas: `pages` (una por nota) y `chunks` (FTS5 externo con
`bm25()`). Para consultar a mano:
```sql
SELECT path, title, heading, snippet(chunks,3,'','',' … ',24),
       bm25(chunks, 0.0, 4.0, 2.0, 1.0) AS rank
FROM chunks WHERE chunks MATCH ? ORDER BY rank LIMIT 5;
```

**Usa el backend real de hwiki** (`build_match_query` + `bm25` + stopwords) si
quieres medir lo que mide la tool en produccion — no SQL crudo sobre
`pages_fts` (esa tabla no existe).

### Trampa: el recall automatico necesita parche para vaults en espanol

`build_match_query` tiene dos defectos que el vault en espanol expone:

1. **Asimetría índice/query.** El índice usa el tokenizador `unicode61`, que
   **pliega diacríticos** ("selección" se indexa como `seleccion`). El query
   builder no los pliega, así que la palabra real nunca matchea.
2. **Fragmentación.** El regex `[A-Za-z0-9_]...` rompe palabras acentuadas:
   `"qué proceso de selección"` → `['qu','proceso','de','selecci','n']`. El
   fragmento `qu` matchea **2.977 chunks** y entra al OR de toda query.

Además `_STOPWORDS` solo trae inglés: "de", "con", "para" matchean cualquier
nota. Efecto neto: el recall que se inyecta antes de cada turno trae páginas
irrelevantes, rotuladas como contexto autoritativo.

**Solución aplicada en este equipo:** parche en el checkout del plugin
(`~/.hermes/profiles/aura/plugins/hwiki`, rama `fix/spanish-stopwords`) con
`_fold()` (NFKD) + ~70 stopwords en español. Patch versionado en
`~/Proyectos/AI/patches-hwiki/` — ver su README para reaplicarlo tras un
`plugins update`. Tests upstream: 13/13.

**Al medir recall, mide por el provider, no por SQL crudo:** el backend real
aplica `RankingPartitionBackend` (per-page cap, `demote_paths`) que un `SELECT`
directo se salta.

## node-search — elegir que nota abrir

Selector acotado de candidatos por frontmatter, tags, backlinks y grafo de
wikilinks. Devuelve *por que* leer cada archivo, no prosa.

Instalar: `hermes -p <perfil> plugins install node-search --yes-deps --enable`

Configurar el root permitido (en `.env` del perfil — es lo que lee el plugin):
```
NODE_SEARCH_ALLOWED_ROOTS="/ruta/al/vault"
```

Tool: `node_search(scope=..., query=..., limit=...)`.
- `scope` es **relativo** al allowed root: `Personal/Empleo` -> esa subcarpeta.
- `query` es **regex por defecto** sobre campos indexados (path, basename,
  frontmatter, links, headings). NO busca en el cuerpo del markdown.
- Sin `query`, `mode=topic_context` devuelve 0 resultados — necesita una
  semilla regex.
- Registra en el toolset `file`.

**Trampa de arranque**: si el plugin no carga, el discovery solo avisa por log y
la tool nunca aparece. Revisar `logs/agent.log`:
```
Failed to load plugin 'node-search': No module named 'yaml'
```
Se arregla con `hermes pm repair` **con `HERMES_HOME` del perfil correcto**
(sin `HERMES_HOME` repara el perfil `default`). Despues hay que **reiniciar
el gateway**: las tools se registran al arranque del proceso.

Verificacion de que la tool quedo registrada:
```python
from tools.registry import registry
print(registry.get_entry('node_search'))   # -> ToolEntry(toolset='file')
```

## hermes-vcc — compresion determinista

Contexto: `hermes -p <perfil> config set context.engine hermes-vcc`.
Compacta el contexto por extraccion algoritmica (regex) en vez de pedir un
resumen a un modelo: cero tokens, determinista, y como el prompt no cambia el
**prompt cache sigue funcionando**. Ataca directamente el bloat de 127k-497k
tokens por llamada.

## qmd — cuando la semantica si justifica el costo

`qmd` (tobi/qmd) es el motor de hibrido BM25 + vector + rerank.
Instalar sin permisos root: `npm install -g --prefix ~/.local @tobilu/qmd`.
Los scripts de `node-llama-cpp` requieren:
```bash
npm config set allow-scripts=node-llama-cpp,tree-sitter-go,... --location=user
```
Collection: `qmd collection add /ruta/al/vault --name <nombre>`, luego
`qmd embed -c <nombre>` (descarga modelos: 0.3-1.6 GB, puede tardar 20+ min).

**Medido — por que NO es el default de hwiki**:

| Backend | Latencia | Nota |
|---|---|---|
| `fts5` | 40.7 ms | el que corre en el prefetch |
| `qmd search` (BM25) | 1.410 ms | subprocess + arranque |
| `qmd vsearch` (vectorial) | >40 s | hasta terminar el embed |
| `qmd query` (hibrido + rerank LLM) | >180 s | carga el modelo de reranking |

`backend: qmd` en hwiki construye `HybridBackend(fts, qmd)` con fusion RRF.
Como el prefetch corre antes de **cada turno**, meter 1.4 s+ en la ruta caliente
empeora lo que se esta arreglando. **Default: `fts5`.** qmd queda instalado
para uso manual (`qmd query "..." -c <coleccion>`).

## Regla operativa que sale de todo esto

**Una consulta de vault = una llamada.** Nunca "grep y luego abrir los 3
primeros hits": eso son 4 rondas. Prefija `wiki_memory_search` (devuelve
excerpts con la respuesta) o `node_search` (devuelve candidatos con el por
que), y abre solo los 2-3 archivos que vas a citar.
