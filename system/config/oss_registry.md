# OSS reuse registry (EX3)

> **Living manifest** - for each swap-able **port** of the skeleton, the **default OSS
> brick** retained, its licence, its reuse mode and its wiring point.
> **Role:** context optimised at build time (one targeted line instead of re-digging through the whole `technique/` watch)
> **+** closing out the licence/dependency debt.
>
> **Authority:** `ARCHITECTURE.md` is the public reference and provides the public technical context.
> **Cycle (D70/D71/D116):** framed in the architecture -> **placed here, at its definitive location
> `system/config/`** -> **exact versions
> + pinned SHAs + re-verified licences frozen at (2)**. The _Version_ and
> _SHA_ columns marked **(2)** are therefore defined slots, not holes.
>
> **Plug-and-play OSS rule (D123/D98):** the skeleton lays down the **plumbing** (ports +
> stub adapters naming the default brick + `uv.lock` lockfile + this registry + config
> of the defaults + setup scripts). The **real wiring** (vendoring, glue, weights,
> empirical benches) = **production (3)**.
>
> **Modes:** `dep.` = installed dependency (lockfile)  -  `extract` = code copied into our tree
> (vendored, with provenance + SHA)  -  `inspi.` = we read and re-implement, **we do not
> copy** (mandatory for AGPL / no licence / non-OSI).
> **Statuses:** `frozen` (settled)  -  `framed` (leaning + interface frozen, binary decided at
> the bench (2))  -  `adopted` / `default`  -  `optional`  -  `open` (arbitration (2)). *Licences
> provisional until the pinning (2).*

## Table of ports -> default bricks

| Port (interface, LOT 1) | Role | Default brick | Fallback / alternative | Licence (prov.) | Mode | Version (2) | SHA (2) | Status | Decision |
|---|---|---|---|---|---|---|---|---|---|
| `Guard` | Reference monitor (the glue is **ours**) | - (in-house code) | inspi.: openclaw  -  nanoclaw  -  goose  -  nanobot  -  hermes-agent  -  gemini-cli | - | inspi. | - | - | frozen | D73/D89 |
| (frontier hygiene) | Secret redaction + recall fencing - defence in depth BEHIND the Guard, never in its place | **hermes-agent** (`redact.py`  -  fencing from `memory_manager.py`) | - | MIT (c) 2025 Nous Research | **copied / extracted** | `456f18b` | `456f18b` | **plundered** | D154 |
| (learning loop) | Detect the lesson at the end of a task  -  re-read one's own conversations  -  count the spend for real | **hermes-agent** (`background_review.py`  -  `session_search_tool.py`  -  `usage_pricing.py`) | - | MIT (c) 2025 Nous Research | **design reused, code rewritten** | `3ef6bbd` | `3ef6bbd` | **plundered** | D155 |
| (self-evolution) | Mutate prompts / skills by evolutionary search (GEPA) | ~~`hermes-agent-self-evolution`~~ | - (to be re-wired one day onto OUR mechanical grade: `make calibrate` / `golden.py`) | WARNING: **NO LICENSE file at all** | **rejected on the evidence** | - | `0a929e3` | **refused** | D155 / D148 |
| `GraphStore` | Local bi-temporal graph | **LadybugDB** (in-process graph, MIT/arm64, available today ; successor to Kuzu) | Graphiti-local (embedded FalkorDB-Lite backend, if merged/mature) | LadybugDB MIT  -  Graphiti Apache-2.0 | dep. | (2) | (2) | default | D103 / D121-B1 |
| `Embedder` | Dense embeddings (multilingual FR/EN) | **bge-m3** (BAAI) | - (consensus frozen, no bench) | MIT | dep. | (2) | (2) | frozen | D68 |
| `VectorIndex` | Vector database | **Qdrant in local SERVER mode** | usearch / LanceDB (embedded, option) | Apache-2.0 | dep. | (2) | (2) | default | D68 / D121-B2 |
| `Reranker` | Re-ranking | **bge-reranker-v2-m3** (BAAI) | - | MIT | dep. | (2) | (2) | frozen | D68 |
| (BM25 retrieval) | Keyword / hybrid RRF | **tantivy-py** | - | MIT | dep. | (2) | (2) | adopted | D68 |
| `Runner` | Running local models (behind the Guard) | **MLX / mlx-lm** (per model) | **llama.cpp** (fallback) ; oMLX/Ollama manager in config | MIT / MIT | dep. | (2) | (2) | framed | D104 |
| `Sandbox` (current tier) | macOS OS isolation | **anthropic/sandbox-runtime** (Seatbelt) | - | Apache-2.0 | extract | (2) | (2) | frozen | D99 |
| `Sandbox` (heavy tier) | Micro-VM confinement | apple/container | microsandbox | Apache-2.0 | dep. | (2) | (2) | open | D99 |
| `ToolPlugin` / MCP client | External tools (MCP) | official **MCP Python SDK** | - (embedded in goose/nanobot/hermes) | MIT | dep. | (2) | (2) | framed | D114 |
| (agent glue) | Typed multi-agent engine, wired **GUARD-SAFE** (model->our Runner, tools->our Invoker ; `agents/pydantic_bridge` adapter, (3)-5b) | **Pydantic AI** | Smolagents (code-as-action, to be benched) | MIT | dep. | (2) | (2) | framed | D93 / D125-B7 |
| (ingestion) | Document extraction (behind `SourceReader`) | **Docling** (first class ; sole-importer adapter `connect_docling`) | **PaddleOCR-VL** / **MinerU** (OCR fallbacks, same port ; `connect_paddleocr` / `connect_mineru`) | Docling MIT  -  PaddleOCR-VL Apache-2.0  -  MinerU "MinerU OSL" (Apache-2.0 base) in v2.x - WARNING: ex-AGPL-3.0 in v1 (`magic_pdf`) | dep. | (2) | (2) | adopted | D43 |
| `Classifier` | Sensitivity classification (PII) | **regex floor** (ours) + **Presidio** (**optional** accelerator) | - | MIT | dep. / inspi. | (2) | (2) | optional | D101 |
| (voice) | Voice -> ingestion (behind `SourceReader`, via a local audio API) | **WhisperKit** (local OpenAI-compatible server ; adapter = **HTTP client** `connect_whisperkit`, NOT a Python import) | - | MIT | dep. (server+client) | (2) | (2) | optional | D115 / D121-E4 |
| (YouTube) | Video URL -> transcription (behind `TranscriptFetcher` ; sole-importer adapter `connect_ytdlp`) | **yt-dlp** (metadata + `timedtext json3` subtitle tracks ; payload downloaded with stdlib `urllib`) | youtube-transcript-api (subtitles only, more fragile) ; **ASR fallback = WhisperKit** (local audio) | Unlicense | dep. | (2) | (2) | optional | subject 3 / AV1 |
| (constrained output) | Grammar-constrained / forced-JSON decoding | **Outlines** | XGrammar | Apache-2.0 | dep. | (2) | (2) | adopted | D104 |
| (secrets) | Encryption at rest | **SOPS** + **age** | - | MPL-2.0 / BSD-3 | dep. | (2) | (2) | adopted | D81 |
| `Backup` | Encrypted snapshots of the 3 stores (zero-knowledge, off-site) | **Kopia** | - | Apache-2.0 | dep. | (2) | (2) | adopted | D110/D118 |
| `Observability` | Self-hosted tracing + golden sets | **Langfuse** + **DeepEval** | Phoenix WARNING: (Elastic) | MIT / Apache-2.0 | dep. | (2) | (2) | adopted | D111 |
| (document production) | PDF deliverables | **Typst** | - | Apache-2.0 | dep. | (2) | (2) | adopted | D79/D51 |
| (fine-tuning) | SFT patterns / small model | **nanoGPT** / **nanochat** | - | MIT | extract / inspi. | (2) | (2) | port-P1 | D115 |

> **Port -> contract mapping (LOT 1).** Each port named above is laid down as an
> **interface contract** under `system/lib/mnemosyne/ports/` : Guard->`guard`, GraphStore->
> `graphstore`, Embedder->`embedder`, VectorIndex->`vectorindex`, Runner->`runner`, Sandbox->
> `sandbox`, ToolPlugin/MCP->`tools`, Classifier->`classifier`, Backup->`backup`, Observability->
> `observability`, Store/IntentLog->`store`, Scheduler->`scheduler`, I/O contract->`iocontract`,
> governance base->`core`. The port **names the default brick in its docstring** ; the
> **stub adapters** (the port implementation naming the brick) arrive with their engine lot
> (LOT 4b/5/6), not at LOT 1.

## WARNING: Licence debt - `inspi.` mode MANDATORY (read and re-implement, never copy)
- **AGPL**: khoj  -  firecrawl  -  daytona core.
- **No licence**: autoresearch  -  front-end-checklist.
- **Non-OSI**: oh-my-openagent (SUL)  -  llm-app (BSL).
- **Partial** (zones to avoid): onyx `ee/`  -  flowise `enterprise/`  -  Phoenix (Elastic).

## Mini-sheets (to be finalised at (2))

### Qdrant - `VectorIndex` (default)
- **Role.** Dense vector database (heavy document corpus), separate from the fact memory.
- **Deployment mode = local SERVER** (D121-B2) - **not** the embedded one: that one caps out at
  ~20k points and forbids concurrent access -> blocking at the target scale (2500+ docs).
  To propagate: bootstrap (D94), `.gitignore` (`.vectorstore/` unversioned), tree layout (D70).
- **Partition by sensitivity**: `sensible` index 100 % local and **physically isolated**
  (reinforces D27/D66 ; invariant 1).
- **Licence.** Apache-2.0 (to be re-verified (2)). **Client.** `qdrant-client` (Python, Apache-2.0).
- **To freeze (2).** Server version + image/binary + SHA ; setup script for the local server.

### bge-m3 - `Embedder` (default, frozen without a bench)
- **Role.** **Multilingual** dense embeddings (native FR/EN), head of the hybrid
  retrieval (dense + BM25 tantivy + bge-reranker-v2-m3 rerank).
- **Why frozen.** The embedding is a **generic** brick: we adopt the state-of-the-art
  consensus and freeze a sound swap-able default - **no bench** for the
  embedding (D68/D69). Stays swap-able behind `Embedder`.
- **Publisher / licence.** BAAI ; MIT (weights + code, to be re-verified (2)).
- **To freeze (2).** Exact version of the weights (HF revision) + SHA ; target quantisation for M4 ;
  paired reranker `bge-reranker-v2-m3` (same fields).

### Docling - document ingestion (`SourceReader`, first class, (3)-4b)
- **Role.** PDF / office / html / image extraction -> **clean markdown**, all **LOCAL**. Document
  default (D43: beats MinerU/PaddleOCR on M4). Wired by `connect_docling` (**sole-importer**
  adapter `# pragma: no cover`, invariant 20) ; wired into `real_runtime` for the `text/`,
  `application/pdf` and office MIME types, + the dispatcher **default**.
- **API (best-guess, checked against the `[OPERATOR]` smoke test).** `DocumentConverter().convert(DocumentStream(
  name=ref, stream=BytesIO(bytes)))` -> `result.document.export_to_markdown()`. To confirm at
  start-up: exact import paths + the name of the export method.
- **Licence / install `[OPERATOR]`.** MIT ; `uv sync --extra bricks` (`docling` package). Layout
  model weights are downloaded by Docling on the first run (plan for the local cache).
- **To freeze (2).** `docling` version + SHA ; layout model cache.

### PaddleOCR-VL / MinerU - OCR fallbacks (`SourceReader`, (3)-4b)
- **Role.** **Fallbacks** behind the SAME port for image/scan sources (`image/`), if Docling
  disappoints. `connect_paddleocr` (`PaddleOCRVL().predict(...)`) and `connect_mineru` (v2 `mineru` /
  v1 `magic_pdf`) - **sole-importer** adapters `# pragma: no cover`.
- **Honesty (F3).** Pipeline/file APIs less settled than Docling's: `connect_paddleocr` = best-guess
  glue (temp-file -> `predict` -> markdown) ; **`connect_mineru` = an honest seam that raises
  `NotImplementedError`** naming the call to wire at start-up (no invented API ; the D85 skip-net
  preserves the source). To confirm at the `[OPERATOR]` smoke test.
- **Licence / install `[OPERATOR]`.** PaddleOCR-VL Apache-2.0 (`pip install "paddleocr[doc-parser]"` +
  `paddlepaddle`) ; MinerU "MinerU OSL" Apache-2.0 base in **v2.x** (`pip install mineru`) - **WARNING:
  ex-AGPL-3.0 in v1** (`magic_pdf`): **pin v2.x** to avoid the AGPL debt (`inspi.` otherwise).
- **To freeze (2).** Version + SHA of the retained fallback ; **MinerU licence re-verified** at the pinned version.

### WhisperKit - voice -> ingestion (`SourceReader`, (3)-4b)
- **Role.** **Voice = one more source** (AV1): audio (`audio/`) -> text, behind the SAME port.
  WhisperKit is **NOT a Python import**: it is a **LOCAL Swift server with an OpenAI-compatible
  audio API** (D114 / D115, a binary back-end behind a port). The `connect_whisperkit` adapter
  is therefore an **HTTP client** (stdlib `urllib` - no HTTP dependency added) to the local endpoint.
- **API (best-guess, checked against the `[OPERATOR]` smoke test).** `POST {base_url}/v1/audio/transcriptions`,
  `multipart/form-data` (`file` + `model`) -> JSON `{"text": ...}`. To confirm at start-up: host/port
  bound by WhisperKit, the endpoint path, the `model` id, the response field.
- **Licence / install `[OPERATOR]`.** MIT ; **install + launch the local WhisperKit server** (Swift
  binary, outside `uv` ; see the REGISTRY's local-server setup scripts) + download the Whisper model.
  Nothing to `uv sync` (the client is stdlib).
- **To freeze (2).** Server version + SHA ; setup/launch script ; definitive host/port/endpoint.

### yt-dlp - YouTube -> transcription (`TranscriptFetcher`, subject 3)
- **Role.** **Video = one more source** (AV1): a YouTube URL -> its text transcription, behind the
  `TranscriptFetcher` port. The economical route = the video's **subtitles** (manual = human verbatim ;
  otherwise **auto-captions** = YouTube's ASR, marked **non-verbatim**). Sole-importer adapter `connect_ytdlp`
  (**lazy** `yt_dlp` import, D103 / inv. 20). **Fallback** when there is no subtitle track: **local** ASR via WhisperKit
  (download the audio -> `connect_whisperkit`), not wired yet.
- **OUTBOUND - not local (the nuance of subject 3).** Unlike the VLM (subject 2) and WhisperKit (both local),
  yt-dlp **reaches YouTube**: nothing `sensible` leaves (inv. 1 holds - we **import** a public datum),
  but it is an **external access** -> wired behind the **Guard's external channel** (deny-by-default, inv. 5) ; the
  retrieved text is **untrusted** (D100-3), classified at ingestion (D101), never executed as an instruction.
- **API (best-guess, checked against the `[OPERATOR]` pilot).** `yt_dlp.YoutubeDL({"skip_download": True, "quiet":
  True}).extract_info(url, download=False)` -> an `info` dict exposing `title`, `uploader`/`channel`,
  `webpage_url`, and the `subtitles` / `automatic_captions` maps as `{lang: [{"ext": "json3", "url": ...}]}`.
  The `json3` payload is downloaded with `urllib` (stdlib - no HTTP dependency added). To confirm at the pilot:
  these keys, the presence of a `json3` track, the URL being directly retrievable, and whether the `json3`
  auto-captions require de-overlapping (rolling-window) beyond consecutive dedup (home = `ingest/youtube.py`).
- **Licence / install `[OPERATOR]`.** Unlicense (public domain) ; `uv add --optional bricks yt-dlp`, then
  `make youtube-pilot URL="..."` on 1-3 videos to **judge** fidelity before any deployment.
- **To freeze (2).** yt-dlp version + SHA ; definitive preferred languages ; retained subtitle format.
