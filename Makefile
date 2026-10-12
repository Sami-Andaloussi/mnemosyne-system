# Mnemosyne — dev workshop (D116). Tools FOR building, not the bricks OF.
# Canonical toolchain = uv (packages + venv + lockfile in one). Bootstrap on a
# fresh clone:  make setup && make hooks
# CI is LOCAL only (D71 + sensible-local): the repo is never pushed to a cloud CI.

.DEFAULT_GOAL := help

# Boolean flags — the rule, and its asymmetry (do not "standardize" it blindly).
# `$(if $(filter 1,$(X)),…)` for any flag whose ACTIVATION is the risky direction: APPLY,
# PERSO (includes personal families), FORCE (overwrites), CONFIRM (declassifies). Without it, `X=0`
# would TURN THE THING ON — a footgun found by the D151 audit on CONFIRM, then generalized here.
# BUT the SAFETY flags (DRY, DRYRUN) stay deliberately permissive: a `filter 1` there would make a
# typo (`DRYRUN=true`) silently DISABLE the safeguard — the opposite of the goal.
# Short rule: harden what ARMS, never what PROTECTS.
#
# C9 — WHICH MODEL. There is no default model anywhere anymore (the operator: "you're basically
# already getting rid of it, so just delete it"), so any target that DECODES locally must be given
# one by name. One single channel, here, rather than a flag copy-pasted across the six targets
# concerned: `MODELE=` for text, `MODELE_VISION=` for vision — TWO distinct names, so a text model
# can never silently become the captioner. Unset ⇒ empty string ⇒ a named REFUSAL that prints the
# basket (`make modeles`), never a silent fallback. This is deliberately the opposite of the
# `filter 1` used by the arming flags: here, typing nothing chooses nothing.
export MNEMO_MODELE := $(MODELE)
export MNEMO_MODELE_VISION := $(MODELE_VISION)
.PHONY: portes garde-emit lot-emit plan-gate-emit item-retirer arsenal documents modeles help setup lock test lint fmt check hooks smoke calibrate agent search qdrant qdrant-up local-run remember rappel rappel-fenetre lecons rendement memoire depense memory-queue memory-validate declassify caption-pilot youtube-pilot youtube-ingest describe parenthese-ouvrir parentheses parenthese-fermer proposals proposal-reviewed endorse endorse-queue policy-queue policy-demander policy-examiner policy-approuver policy-refuser policy-appliquer murs daemon daemon-status distill distill-sommaire distill-emit distill-emit-split distill-batch distill-apply judge verbatim-check finish finish-emit regle-promouvoir skill-new skill-emit skill-audit skill-eprouver skill-juger skill-verdict skill-epreuves moisson rangement rangement-emit project-new plans plan-archiver plan-corbeille plan-convertir plan-nouveau gel-inscrire plan-emit ui-json domain-new veille completude raptor-build raptor-report ingest figures-enrich manifest-realign orphans-report orphans-purge cours cours-emit cours-verifier harnais-de-sabotage sites-de-sortie passes batterie clotures fermeture-glyphe disjoncteur attribution passation precedence plafond-rotation diffusion avancement accord-chiffre besoins besoin besoin-trancher commit-garde public-mirror public-mirror-verify public-mirror-mark-synced public-mirror-emit

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Create the venv and sync the dev toolchain (uv)
	uv sync

lock: ## (Re)generate uv.lock — pinned, supply-chain-safe (D113-d)
	uv lock

test: ## Run the local CI test ladder (pytest = D109)
	uv run pytest

lint: ## Lint with ruff
	uv run ruff check .

fmt: ## Format with ruff
	uv run ruff format .

portes: ## THE REPO'S GATES THAT REFUSE, in one shot (2.7 s measured). Five GREEN gates today, hence wireable: sites-de-sortie (an undeclared egress import), passes (a pre-commit pass that stopped being wired or reachable), clotures (a closure with no author), precedence (a mandate missing the clause, or a dead address), accord-chiffre (a copied figure that has drifted from its computation). FOUR GATES FROM LOT 2 ARE NOT HERE, AND THAT IS MEASURED, NOT FORGOTTEN: fermeture-glyphe, disjoncteur, attribution and plafond-rotation REFUSE TODAY on REAL defects in the repo (5 historical closures with no glyph, 3 items looping, one arc collision, 4 journals over the ceiling). Wiring them here would block EVERY commit -- a gate that is born red is not wired, it is pulled by hand until its population turns green. batterie either: it re-runs pytest, which `make check` already runs. Usage: make portes
	@$(MAKE) --no-print-directory sites-de-sortie
	@$(MAKE) --no-print-directory passes
	@$(MAKE) --no-print-directory clotures
	@$(MAKE) --no-print-directory precedence
	@$(MAKE) --no-print-directory accord-chiffre

check: lint test portes ## Lint + test + the gates that refuse (the full local gate)

smoke: ## Run the 1-click smoke over the REAL bricks (③) — needs `uv sync --extra bricks` + a running Qdrant
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.smoke

calibrate: ## Measure the two golden bars over the REAL bricks (D69) — reads the F1 the operator flips the trust flags on
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.calibration

agent: ## Run the live governed agent over the REAL bricks (③-5b) — needs `uv sync --extra bricks` + a running Qdrant + MLX weights
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.agent_run

search: ## Query the RAG and PRINT the retrieved passages (frontier-usable READ surface, item 4 / D65) — retrieval only, NO MLX brain (bge-m3 + Qdrant + BM25 + reranker). Needs `uv sync --extra bricks` + a running Qdrant (no generative weights). Usage: make search Q="your question" [WITHIN=sensible] [TOPK=8]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.search_run "$(Q)" $(if $(WITHIN),--within $(WITHIN),) $(if $(TOPK),--top-k $(TOPK),)

qdrant: ## SEE the vector index `make search` depends on — does it answer, and WHAT does it hold (point counts per collection, so an EMPTY index can never pass for the library). Says too why it dies at each reboot. Brick-free, instant. Usage: make qdrant
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.qdrant_run etat

qdrant-up: ## RESTART the stopped index container (`mnemo-qdrant`) — the gesture the 2026-07-27 measurement found missing: search died after 11.6 s on `Connection refused` and nothing said this. Never CREATES a container (a fresh one is empty and looks identical). Usage: make qdrant-up
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.qdrant_run demarrer

local-run: ## Dispatch ONE bounded task to the LOCAL model and PRINT its completion (frontier->local delegation, item 1) — loads the MLX brain (a decode, unlike search). Needs `uv sync --extra bricks` + a running Qdrant + MLX weights. Usage: make local-run PROMPT="a precise, bounded task" [WITHIN=sensible] [SCHEMA=path/to/schema.json] [BUBBLE=work]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.local_run "$(PROMPT)" $(if $(WITHIN),--within $(WITHIN),) $(if $(SCHEMA),--schema "$(SCHEMA)",) $(if $(BUBBLE),--bubble "$(BUBBLE)",)

remember: ## Deposit ONE concise LEARNING into living memory, INERT, awaiting your validation (learn-while-using, item 2) — no brain, persists via a durable proposals ledger (replayed at cold start; review with `make memory-queue`). Needs `uv sync --extra bricks` + a running Qdrant. Usage: make remember LEARNING="a durable, reusable learning" [WITHIN=perso] [BUBBLE=perso]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.remember_run "$(LEARNING)" $(if $(WITHIN),--within $(WITHIN),) $(if $(BUBBLE),--bubble "$(BUBBLE)",)

depense: ## REPORT what Mnemosyne's OWN code spent today against the two ceilings policy.toml declares (D155/D86) — input/output/cache-read/cache-write split, honest "estimated" status, and it says so when a model has no known price. Does NOT see your Claude Code session (subscription, another process). Read-only, brick-free. Usage: make depense [JOUR=2026-07-19]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.spend_run $(if $(JOUR),--jour $(JOUR),)

rappel: ## SEARCH your own past conversations (D155) — full-text over this repo's session transcripts. NO model, NO network, NO cost; the index refreshes itself incrementally on each call. Empty Q lists the latest conversations. Brick-free (sqlite3 is stdlib). Usage: make rappel Q="what did we decide about the library" [TOPK=8]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.sessions_run "$(Q)" $(if $(TOPK),--top-k $(TOPK),)

rappel-fenetre: ## READ the messages surrounding one `make rappel` hit — a snippet put back in the order it was said (D155). Read-only, brick-free. Usage: make rappel-fenetre SESSION=<id> SEQ=<n>
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.sessions_run --session "$(SESSION)" --seq "$(SEQ)"

memory-queue: ## List the living-memory validation queue — learnings captured INERT via `make remember`, awaiting your gesture (item 2). Brain-free, read-only, rebuilt from the durable ledger. Needs `uv sync --extra bricks` + a running Qdrant. Usage: make memory-queue
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.memory_queue_run

memory-validate: ## Validate (or DISMISS=1 to reject) ONE queued learning by id — your explicit gesture, journaled durably (item 2 / D59-5 / D82). Brain-free. Needs `uv sync --extra bricks` + a running Qdrant. Usage: make memory-validate ID=<fiche id> [DISMISS=1]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.memory_validate_run "$(ID)" $(if $(DISMISS),--dismiss,)

declassify: ## Declassify a SENSIBLE deliverable into a PUBLIC copy under YOUR explicit gesture (D107 / D147 — the wired egress door). DRY-RUN by default; CONFIRM=1 performs the gesture. Requires a DISTINCT audit (PRODUCER != VERIFIER, D100-6). Original intact (non-destructive). No brain/brick/Qdrant. Usage: make declassify FILE="knowledge/distilled/<dom>/<doc>.md" PRODUCER=frontier VERIFIER=opus [BUBBLE=perso] [OUT=path] [CONFIRM=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.declassify_run "$(FILE)" --producer "$(PRODUCER)" --verifier "$(VERIFIER)" $(if $(BUBBLE),--bubble "$(BUBBLE)",) $(if $(OUT),--out "$(OUT)",) $(if $(filter 1,$(CONFIRM)),--confirm,)

caption-pilot: ## Caption ONE book's figures with the local VLM (subject 2 pilot) — first `uv add --optional bricks mlx-vlm`, then run. Usage: make caption-pilot BOOK="knowledge/raw/<...>/book.pdf" [MAX=6 to cap the first N figures for a fast pilot]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.caption_pilot "$(BOOK)" $(MAX)

youtube-pilot: ## Fetch ONE YouTube video's transcript to <id>.youtube.md (subject 3 pilot) — first `uv add --optional bricks yt-dlp`, then run. Usage: make youtube-pilot URL="https://youtu.be/<id>"
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.youtube_pilot "$(URL)"

youtube-ingest: ## Capture ONE YouTube transcript INTO MEMORY (subject 3 / C3, Guard-mediated) — needs `uv add --optional bricks yt-dlp` AND www.youtube.com allow-listed in policy.toml [egress]. Usage: make youtube-ingest URL="https://youtu.be/<id>" [BUBBLE=perso]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.youtube_ingest "$(URL)" $(if $(BUBBLE),--bubble "$(BUBBLE)",)

figures-enrich: ## Fill EXISTING .md figure holes IN PLACE from each PDF (subject F), backing up the original once; re-index only changed docs via `make ingest`. Needs `uv add --optional bricks pymupdf` (+ mlx-vlm for VISION=1, anthropic for FRONTIER=1). IMAGES=1 (arc D) keeps each figure's OWN pixels as a .png the .md links -- no model, deterministic, and it OUTRANKS every description. LOCAL first: vector always on, VLM opt-in; FRONTIER=1 = level 3 (asks to confirm the cloud egress, Guard-gated). Usage: make figures-enrich [IMAGES=1] [ONLY="substring of the book path"] [LIMIT=N] [MAXHOLES=M] [VISION=1] [FRONTIER=1] [DRYRUN=1]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.figures_enrich_run $(if $(IMAGES),--images,) $(if $(ONLY),--only "$(ONLY)",) $(if $(LIMIT),--limit $(LIMIT),) $(if $(MAXHOLES),--max-holes $(MAXHOLES),) $(if $(VISION),--vision,) $(if $(FRONTIER),--frontier,) $(if $(DRYRUN),--dry-run,)

ingest: ## Re-index the reference-library shelf into the real stores (truth + Qdrant + BM25, via docling + bge-m3) — THE RAG re-index gesture (referenced by figures-enrich / manifest-realign). Needs `uv sync --extra bricks` + a running Qdrant. Non-destructive + resumable (content-id manifest, D142). Usage: make ingest [LIMIT=N to cap new books] [RETRY_OCR=1 to re-attempt scanned books]
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.library_run $(if $(LIMIT),--limit $(LIMIT),) $(if $(RETRY_OCR),--retry-ocr,)

manifest-realign: ## G5: move the library manifest's display paths onto the CURRENT shelf paths (post-reorg), matched by content id, so a later re-index purges stale vectors (no Qdrant duplicates). Run BEFORE `make figures-enrich`. Non-destructive (backs up once). Usage: make manifest-realign [DRYRUN=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.library_run --realign-only $(if $(DRYRUN),--dry-run,)

orphans-report: ## G6: report library vectors whose source book left the shelf (post-reorg orphans) — read-only, no change. Needs Qdrant up ([OPERATOR] bricks). Usage: make orphans-report
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.library_run --report-orphans

orphans-purge: ## G6: report AND purge confirmed orphan vectors + their manifest rows (governed, non-destructive: derivative-only, backs up the manifest once). Needs Qdrant up. Usage: make orphans-purge
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.library_run --purge-orphans

raptor-build: ## Ch.5: build/refresh the RAPTOR summary tree (book + domain synopses, RAG level 2) over the library shelf, embed + index new nodes, sweep stale ones. Needs `uv sync --extra bricks` + a running Qdrant + MLX weights (many guarded model calls, SERIAL — D95). Usage: make raptor-build
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.raptor_run

raptor-report: ## Ch.5: dry view of `raptor-build` — counts reused / would-summarize / would-sweep WITHOUT calling the summarizer or writing anything (read-only). Usage: make raptor-report
	PYTHONPATH=system/lib uv run --extra bricks python -m mnemosyne.runtime.raptor_run --report

describe: ## Render Mnemosyne's self-model (identity + surfaces + tools + active skills) — a fresh agent reads this to discover & use the system. Brick-free, read-only (⑥ / D25 / D114-TO2)
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.describe

modeles: ## THE BASKET of LOCAL models (C9) — the single, written answer to "which models do I have?", declared in `system/config/models.toml` and VERIFIED against disk in BOTH DIRECTIONS on every call (0.9 ms measured): declared-but-absent, present-but-undeclared, and drifted weights are three NAMED refusals. There is NO default model, and that is deliberate: calling the local engine without naming a model REFUSES and prints this basket (`MODELE=<id>` on the command line, `MODELE_VISION=<id>` for vision). Also names cached models OUTSIDE the basket (bge-m3, docling) — an excluded population is unjudged, not risk-free. A STATUS surface (always exits 0): the gate that blocks lives where a model is chosen. Writes NOTHING — the zone is protected (SE4); `EMETTRE=1` renders the exact lines to paste. Brick-free, no weights loaded. `JSON=1` renders the SAME basket in JSON for an interface (arc C3/G8) — emitted from the same catalogue and the same reconciliation, never re-derived from a text that could drift. Usage: make modeles [EMETTRE=1] [JSON=1]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.models_run $(if $(filter 1,$(EMETTRE)),--emettre,) $(if $(filter 1,$(JSON)),--json,)

endorse-queue: ## SHOW which library documents are CITABLE sources and which are still matière-de-travail (D137). Read-only, brick-free. Usage: make endorse-queue
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.endorse_run --queue

endorse: ## ENDORSE a LOT of library documents as citable sources — YOUR gesture (D137). DRY-RUN by default; CONFIRM=1 performs it. RETRACT=1 tightens back (always free). Append-only journal, nothing erased. Usage: make endorse SCOPE="Finance/Assets/commodities" [DOMAIN=commodities] [RETRACT=1] [CONFIRM=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.endorse_run $(if $(SCOPE),--scope "$(SCOPE)",) $(if $(DOMAIN),--domain "$(DOMAIN)",) $(if $(filter 1,$(RETRACT)),--retract,) $(if $(filter 1,$(CONFIRM)),--confirm,)

policy-queue: ## SHOW every policy-widening request and its stage (depose/examine/approuve/refuse/applique, D159). Read-only, brick-free. Usage: make policy-queue
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.policy_run queue

policy-demander: ## FILE a structured request to widen policy.toml (egress/domains/contract), or create a blank template if FICHIER is omitted (D159). Brick-free. Usage: make policy-demander [FICHIER=path/to/request.toml]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.policy_run demander $(if $(FICHIER),--fichier "$(FICHIER)",)

policy-examiner: ## PRINT the closable adversarial examination mandate for a request (dispatch it to an ISOLATED agent, D75), or RECORD its verdict with VERDICT=. Never decides — narrows/recommends only. Usage: make policy-examiner ID=<id> [VERDICT=path/to/verdict.json]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.policy_run examiner --id "$(ID)" $(if $(VERDICT),--verdict "$(VERDICT)",)

policy-approuver: ## The operator's gesture — the ONLY way a request becomes approved (D159). MUST be run in a REAL terminal: shows the full content then asks for a LIVE 'OUI' on /dev/tty (an agent cannot satisfy this, by design — post-incident hardening). Usage: make policy-approuver ID=<id>
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.policy_run approuver --id "$(ID)"

policy-refuser: ## The same gesture, the other way — records a refusal with your reason (D159). Same LIVE 'OUI' gate as policy-approuver. Never deletes the refused request (inv. 2). Usage: make policy-refuser ID=<id> RAISON="why"
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.policy_run refuser --id "$(ID)" --raison "$(RAISON)"

policy-appliquer: ## WRITE the approved items to system/config/policy.toml — DRY-RUN by default, CONFIRM=1 performs it. Fail-closed: refuses anything not exactly approved (D159). Usage: make policy-appliquer ID=<id> [CONFIRM=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.policy_run appliquer --id "$(ID)" $(if $(filter 1,$(CONFIRM)),--confirm,)

murs: ## SHOW every refusal the Guard has raised, grouped by effect (D159) — "hitting a wall stops being silent". Read-only, brick-free. Usage: make murs
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.murs_run

orphelins: ## PUBLISH, for every system/lib/{production,runtime} file: declared owner (all FOUR mon_lot: — the three chats AND the orchestrator's own, which a throwaway census missed) vs measured producer (Co-Authored-By models seen in git history). Level 1 (publishes, never refuses) — the gap is the result, not either column alone. Read-only, brick-free. Usage: make orphelins
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.orphelins_run

fermeture-isolee: ## PUBLISH plan items closed (done/closed) whose known git history never names a SECOND Co-Authored-By identity (H5, line 5) — a floor below which independent audit is structurally impossible, never proof one happened (same-model chats are indistinguishable). Level 1 (publishes, never refuses) — a refusing gate here would false-block legitimate same-model cross-chat audits. Read-only, brick-free. Usage: make fermeture-isolee
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.fermeture_isolee_run

memoire: ## EMIT the memory overflow index (MEMORY-2.md — the built-in loads only MEMORY.md) and publish the ratchet: bijection by SET diff over both indexes, the frozen size of MEMORY.md, and whether the overflow was REALLY emitted (D173). Exits non-zero on a dead link, an orphan, or a grown index. Read-only, brick-free, no model. Wired into the SessionStart hook — where its rc is discarded (fail-open), so there it only PRINTS. Usage: make memoire
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.memoire_run

lecons: ## ASK the lessons instead of receiving all of them (workstream 0 · A1) — full-text over the memory fiches themselves. NO model, NO network, NO cost; the index refreshes itself incrementally on each call and lives under system/state (gitignored, so nothing lands in the memory repo). Measured 2026-08-09, the reason this exists: MEMORY.md sits at 24,324 bytes against a ~24,400 built-in wall, and its overflow MEMORY-2.md — born 3 days earlier — already weighed 16,735 bytes. 41,059 bytes of index PUSHED into every session. This is the PULLED path. ALWAYS prints how many fiches were searched, so an empty index can never pass for a library. Deletes nothing, merges nothing, rewrites nothing — it only READS (inv. 2 / D74). Usage: make lecons Q="what you are about to do" [TOPK=6]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.lecons_run "$(Q)" $(if $(TOPK),--top-k $(TOPK),)

rendement: ## I6 — how many lessons DETECTED by the hook actually led to a DEPOSIT, and the same count for task-ends where NOTHING was detected. The control group is not optional: without it, "87% of signals are followed by a deposit" means nothing, since deposits are frequent and almost any instant is "followed by a deposit"; `mesurer()` renders both or neither, by its signature. It is PULLED and is NOT in the hook, by design: it measures the machine's whole history, not one task — printing it at every task end would repeat the same table, exactly how a block becomes furniture. It ALWAYS SAYS what it searched, and REFUSES (exit 1) on an empty population rather than printing a table of zeros: a null population means "the marker moved", never "the loop no longer detects anything", and the two read the same on zeros. Local, read-only, no model, no network, no cost (inv. 1 / inv. 2 / D126). Usage: make rendement [PROJET=<transcripts folder>]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.rendement_run $(if $(PROJET),--projet "$(PROJET)",)

parenthese-ouvrir: export MNEMO_P_TITRE := $(TITRE)
parenthese-ouvrir: export MNEMO_P_PLAN := $(PLAN)
parenthese-ouvrir: export MNEMO_P_ITEM := $(ITEM)
parenthese-ouvrir: export MNEMO_P_POURQUOI := $(POURQUOI)
parenthese-ouvrir: export MNEMO_P_RETOUR_ATTENDU := $(RETOUR_ATTENDU)
parenthese-ouvrir: ## OPEN a parenthesis — a workstream OFF TO THE SIDE of a plan, which will have to come BACK to it (C8-c). REFUSES if RETOUR_ATTENDU is empty: "what must come back" is declared at opening time, the only moment nobody benefits from leaving it vague (measured: one of the sibling project's parentheses closed leaving a decision never executed). Renders the ONE line to paste into the plan — one line, never the content. Brick-free. Usage: make parenthese-ouvrir TITRE="..." PLAN="projects/<bubble>/<project>/PLAN.md" ITEM="C8" POURQUOI="..." RETOUR_ATTENDU="what the plan will need to receive back"
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.parentheses --ouvrir

parentheses: ## SEE the open parentheses and, for each, WHAT IT STILL OWES BACK to its plan (the tick counts them for you). Flags the ones the plan does not point to — a parenthesis invisible from the plan is exactly the waste this is meant to prevent. Read-only, brick-free. Usage: make parentheses
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.parentheses

parenthese-fermer: export MNEMO_P_FICHIER := $(FICHIER)
parenthese-fermer: export MNEMO_P_RETOUR := $(RETOUR)
parenthese-fermer: export MNEMO_P_DANS := $(DANS)
parenthese-fermer: ## CLOSE a parenthesis — REFUSES until the return is both NAMED (RETOUR) and PLACED in a file that exists (DANS). Naming without placing is closing on a promise: that is exactly what left a debt behind one of the sibling project's parentheses. The file is never deleted, its status moves to `fermee` (inv. 2). Usage: make parenthese-fermer FICHIER=docs/parentheses/xxx.md RETOUR="what came back" DANS="projects/<bubble>/<project>/PLAN.md"
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.parentheses --fermer

proposals: ## READ the inert proposals the veille and the agents deposited for your review (the tick counts them). Lists paths, never a digest — they cite YOUR sources, so you read them yourself. Read-only. Usage: make proposals
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.proposals

proposal-reviewed: export MNEMO_FICHIER := $(FICHIER)
proposal-reviewed: ## MARK one proposal as seen-and-decided (`status: revu`) — NOT promoted: turning a draft into a real skill stays a separate act (D92). Never deletes it (inv. 2). Usage: make proposal-reviewed FICHIER=knowledge/proposals/veille/xxx.md
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.proposals --revu

daemon: ## EMIT the launchd plist + launchctl gesture to run `tick` 24/7 on THIS machine (the between-sessions upgrade of the SessionStart hook). Installing a standing agent is the operator's gesture — this only renders it. Brick-free. Usage: make daemon
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.daemon install

daemon-status: ## Show the tick daemon's proof-of-life (last wake + proposals surfaced) — honest when it never woke, AND honest when it has stopped waking (past 24h silence, "THE DAEMON HAS STOPPED BEATING" replaces "Last wake" -- measured 2026-08-17, D163 pattern adopted from `make plancher`/`make carte`). Read-only. Usage: make daemon-status
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.daemon status

carte: ## B3: THE MAP — the SINGLE surface for "where things stand", of CONSTANT size. Where things stand, what remains, what blocks what, what is parallelizable, and WHAT IS NOT MOVING (nobody is waiting on it, it is waiting on nobody). Its property is not to be small, it is to never GROW: a plan of 10,000 steps renders the SAME number of lines as a plan of 168, and every section SAYS how much it is hiding -- an excerpt is the worst of both worlds, too small to understand and big enough to believe you have seen it all. It carries B2's order, there is no second command. PULLABLE BY HAND by design: the SessionStart hook that pushes it is fail-open, if it breaks it stays silent. Refuses (rc 1) to draw on an UNREADABLE plan -- a correct view of a stale source is an exact lie; rc 2 if there is no gate. Read-only, no brick, no model. Usage: make carte [POUR=projects/<bubble>/<project>]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.carte_run

orchestration-borne: ## E2: the number of chats to launch, DERIVED -- min(width of the wave IN ARCS, the orchestrator's arbitration capacity), never a hand-written value. The first term is measured live on the real plan (reuses ArcEtat.demarrable from make carte, no second computation); the second is frozen and cited with its source (a usage measurement over a closed time window, not re-measurable). Refuses (rc 1) on an UNREADABLE plan, rc 2 if there is no gate. Read-only, no brick, no model. Usage: make orchestration-borne [POUR=projects/<bubble>/<project>]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.orchestration_run

plans: ## Which plans are readable, and which are not (arc C2 · D166) — over a DECLARED list of roots: every `projects/<bubble>/<project>/`, plus `docs/` (Mnemosyne's own plan, the only one that cannot live under `projects/`, and which was invisible here). A plan is a FOLDER: a `PLAN.md` gate + arcs under `plan/`, at any depth; a single-file plan remains legal. Names every one; reports, never blocks. `VERIFIER=1` renders the SAME view then REFUSES (exit 1) if a plan is UNREADABLE or if a frozen gate (D163, `derives.PORTES_QUI_DECLARENT`) has lost its `**Format**` declaration -- this is the only surface that judges a PROJECT's plan, `projects/` being gitignored (this repo's pre-commit never sees it). Brick-free. Usage: make plans [VERIFIER=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plans_run

plan-archiver: ## Move the memory of what is DONE out of a living plan, into `archive/plan-<date>-<arc>.md` alongside it (C8). The UNIT follows the shape of the plan (D166): a GATE archives its ARCS (the whole `plan/` file leaves, the gate keeps the pointer in place of its index entry); a plan that is a SINGLE FILE archives its `##` sections, as before — the file shape remains the floor. Moves bytes, rewrites NONE of them: the reconstruction (archive + remaining plan = the original file, character for character) is verified BEFORE any write, otherwise the command refuses. Also REFUSES to archive an arc that lies (title over items ), an arc the gate contradicts (`titre_ambigu` — the index can VETO, never authorize), an index that does not designate the arc exactly once (`index_incertain`), and overwriting an existing archive (inv. 2). DRY by default; APPLY=1 to write. Brick-free. Usage: make plan-archiver [PLAN="projects/<bubble>/<project>/PLAN.md"] [APPLY=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plan_archiver_run $(if $(PLAN),"$(PLAN)",) $(if $(filter 1,$(APPLY)),--apply,)

plan-corbeille: ## Move ONE item already removed by H1 (arc `07-la-revision.md`) into the permanent trash alongside it (H3): memory of what was REMOVED, never of what is DONE — distinct from `plan-archiver`. Same pattern as its neighbor: moves bytes, rewrites NONE of them — the reconstruction (trash + remaining arc = the original file, character for character) is verified BEFORE any write, otherwise the command refuses. Writes the trash FIRST, the arc LAST (inv. 2: a failure between the two duplicates the item, never loses it). DRY by default; APPLY=1 to write. Brick-free. Usage: make plan-corbeille PLAN="docs/plan/07-la-revision.md" ITEM=H3 REMPLACE="nothing for now" [APPLY=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plan_corbeille_run "$(PLAN)" --item "$(ITEM)" --remplace "$(REMPLACE)" $(if $(filter 1,$(APPLY)),--apply,)

plan-convertir: ## A plan that is a FILE becomes a plan that is a FOLDER (D166 · C20-4): the gate keeps the heading and the INDEX, each `##` section moves into `plan/<arc>.md`. Moves bytes, rewrites NONE of them — not even the indentation: the reconstruction (gate + arcs = the original file, character for character) AND the re-reading of the converted plan by the reader itself are verified BEFORE any write, otherwise the command refuses and writes nothing. The original file is never erased: it BECOMES the gate. Leaves a handover note alongside it. REFUSES rather than guessing: `deja_converti`, `plan_illisible`, `borne_incertaine`, `titre_sans_identite`, `collision_de_nom`, `garder_introuvable`, `note_existe` — and a single reason blocks the WHOLE conversion (a hinge does not happen halfway). DRY by default; APPLY=1 to write. `GARDER=` designates by the section's NAME (what precedes its status glyph), and only ONE passes through this target — to keep several, call the module directly with several `--garder`. Brick-free. Usage: make plan-convertir [PLAN="projects/<bubble>/<project>/PLAN.md"] [GARDER="ON RESUME"] [APPLY=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plan_converter_run $(if $(PLAN),"$(PLAN)",) $(if $(GARDER),--garder "$(GARDER)",) $(if $(filter 1,$(APPLY)),--apply,)

gel-inscrire: ## D176: RECORD an adopting gate into the freeze (`derives.PORTES_QUI_DECLARENT`), by a GESTURE instead of hand-editing code. What the freeze buys: without it, a gate can ERASE its `**Format**:` line — twenty characters — and the guard that judges that declaration silently turns GREEN again, because a gate never adopted and a gate that JUST LOST its adoption render the same empty state. `make plans` publishes the gap (level 1, refuses nothing) and now names THIS command. REFUSES to record a gate that declares NOTHING on disk (the freeze certifies "it declared": putting it in without measuring would fabricate the very attestation it makes falsifiable), a gate ALREADY frozen, and an insertion whose anchor is not found exactly once. The declaration is read by the PRODUCTION accessor, never by a grep — a freeze recorded by a different reader than its judge proves nothing. Auto-discovers NOTHING, deliberately: populating from a scan would make the freeze inert. Re-reads the file AFTER writing (D161). Reachable from a project folder via `make -C ~/mnemosyne` (J4). DRY by default; APPLY=1 to write — then COMMIT `derives.py`, an uncommitted freeze is worthless. Brick-free. Usage: make gel-inscrire PORTE="projects/<bubble>/<project>/PLAN.md" [APPLY=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.gel_inscrire_run $(if $(PORTE),"$(PORTE)",) $(if $(filter 1,$(APPLY)),--apply,)

plan-nouveau: ## GIVE BIRTH to a plan that is already a CONFORMING FOLDER (D166 · C20-13) — the capacity to CREATE, where `plan-convertir` only knew how to REPAIR: it writes the `PLAN.md` gate (heading + index), the `plan/` folder and a first arc, at PATH. RECURSIVE: if the target folder lives under the `plan/` of an existing plan, it is a SUB-plan, and the parent gate receives its index entry in the SAME gesture — without it, it would be born orphaned (`arc_hors_index`) and the barrier would refuse the commit. The shape is written nowhere here: the index entry comes from `plan_convert.index_entry`, and the READER itself (`plan_format`) judges the bytes BEFORE any write — so a plan born here passes the pre-commit barrier on the first try, with no conversion (CAUTION: this guarantee covers D166 READABILITY, not D176 -- if FORMAT= is supplied or inherited from the parent, the skeleton fills in none of the promised fields and the installed D176 barrier will refuse it as-is, see the command's output). REFUSES rather than overwriting (inv. 2), and every refusal is NAMED, blames what triggered it and is pulled by hand ALONE — the list lives in the code, `make plan-emit` renders it (`chemin_manquant`, `racine_du_depot`, `dossier_des_arcs`, `plan_existe`, `texte_declare_un_chemin`, … and `squelette_illisible`, which alone means "the code has drifted"). A single reason blocks the WHOLE birth. Targets the PROJECT's folder, not its `plan/`: a SUB-plan is born INSIDE `<project>/plan/<name>`, and several SIBLING sub-plans are the normal shape. FORMAT= (D176, optional) declares mandatory fields from birth (e.g. "produit, fini_quand") -- omitted, the plan is born with no obligation and the gate explains the choice, never imposes it. DRY by default; APPLY=1 to write. `ARC=` passes only ONE through this target — for several, call the module with several `--arc`. Brick-free. Usage: make plan-nouveau CHEMIN="projects/<bubble>/<project>" [NOM="Sibling Research"] [CAP="close arc 6"] [ARC="Foundation"] [FORMAT="produit, fini_quand"] [APPLY=1]
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plan_new_run $(if $(CHEMIN),"$(CHEMIN)",) $(if $(NOM),--nom "$(NOM)",) $(if $(CAP),--cap "$(CAP)",) $(if $(ARC),--arc "$(ARC)",) $(if $(FORMAT),--format "$(FORMAT)",) $(if $(filter 1,$(APPLY)),--apply,)

plan-emit: ## EMIT (from the single code source) the LITERAL structure of a conforming plan, for an agent to apply without interpreting it — the gate, an arc, the index entry, the statuses, the accepted AND refused separators, the named refusals. This is NOT a description: it is the exact content to write, replayed from `plan_scaffold` / `plan_convert` / `plan_format`, never copied by hand (a copy drifts — measured: 12/12 against the tool, 2/10 against the hand, D170). Skill `planificateur`. No model/brick. Usage: make plan-emit [NOM="my project"]
	@PYTHONPATH=system/lib uv run python system/skills/planificateur/plan_emit.py $(if $(NOM),"$(NOM)",)

ui-json: ## THE data contract an interface reads (arc C3) — the 6 queues (refused fiches included) + every project's plan, as JSON on stdout. One command, no server, no network: it works with the Wi-Fi off. Writes no file (redirect if you want one). Brick-free. Usage: make ui-json
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.ui_run

project-new: ## Propose a governed project DRAFT (Ch.7 / D52) — renders the deny-by-default profile; PROPOSES, never activates (activation is a human gesture, D54-3b). Brick-free. Usage: make project-new NAME=example GOAL="macro research" BUBBLE=example
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.project_new --name "$(NAME)" --goal "$(GOAL)" --bubble "$(BUBBLE)"

domain-new: ## Create a new library domain (D46): make the shelf tree + write the taxonomy line, then EMIT the one policy line for the operator to add (POLICY_WRITE = their gesture, never mine). Brick-free. Usage: make domain-new DOMAIN=macro FAMILY=Economics GROUP=Macro
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.domain_new --domain "$(DOMAIN)" --family "$(FAMILY)" --group "$(GROUP)"

veille: ## EMIT (from the single code source) the veille contract for a batch of un-surveyed distilled fiches, for a FRONTIER host (Claude Code) to apply: extract principles/skills/hypotheses as inert drafts (propose, never impose). No model/brick. Usage: make veille [BATCH=N]
	PYTHONPATH=system/lib uv run python system/skills/veilleur/emit_veille.py $(BATCH)

completude: ## F3 — THE COMPLETENESS CLAUSE: confronts the plan against a reference that does NOT DERIVE from it. It PUBLISHES the units no item carries (that work remains is a fact, never a fault) and it REFUSES three things, in a single direction (floors, never ceilings): a reference YOUNGER than the plan's gate ("derived" — MEASURED by git, never declared: a document that claims to predate the gate without actually doing so reassures instead of judging), a reference SHRUNK below its floor (removing a tier to erase a gap is a gesture aimed at the JUDGE), and a reference from which NO unit is read (zero gaps would read as perfect coverage). Exits 1 on refusal. No model/brick. PLANCHER is MANDATORY (a default of 1 made the SHRUNK refusal inert) and PORTE must be a REAL plan gate — otherwise the judge would be designated by the judge. Usage: make completude REFERENCE=<path to a reference doc> PLANCHER=<N> SECTION="<section title>" [PORTE=<path to a plan gate>]
	@PYTHONPATH=system/lib uv run python system/skills/enqueteur/emit_completude.py --reference "$(REFERENCE)" $(if $(PLANCHER),--plancher $(PLANCHER),) $(if $(PORTE),--porte "$(PORTE)",) $(if $(SECTION),--section "$(SECTION)",)

enqueter: ## F1 — THE INVESTIGATOR: takes a project question and EMITS its mandate (it CALLS `make search` / `rappel` / `lecons` / `endorse-queue`, it reinvents no engine; outside = the Guard and its allow-list, inv. 21). With FICHE=, it is a BARRIER (obligation level 2, it REFUSES and exits 1): every claim carries a RESOLVED source — a path that exists in the repo, or a URL whose host is allow-listed — and a fiche that asserts nothing is refused too. DEPOSER=1 writes NOTHING when it is red; the deposit is inert (D92), promotion stays the operator's gesture. No model/brick. F2 — SOUS="a precise point" [ALIRE="a,b"] emits the mandate for ONE sub-question (one question, one reading list, an output with TWO branches, of which "I found nothing" is the second, valid and free). Usage: make enqueter Q="my question" | make enqueter SOUS="a precise point" [ALIRE="path1,path2"] | make enqueter FICHE=knowledge/enquetes/x.md [DEPOSER=1]
	PYTHONPATH=system/lib uv run python system/skills/enqueteur/emit_enquete.py $(if $(SOUS),--sous "$(SOUS)" $(if $(ALIRE),--a-lire "$(ALIRE)",),$(if $(FICHE),--fiche "$(FICHE)",$(if $(Q),"$(Q)",))) $(if $(filter 1,$(DEPOSER)),--deposer,)

distill: ## Distil ONE book .md into its mirrored fiche via the distillateur skill — needs `--extra bricks` + MLX. Usage: make distill BOOK="knowledge/raw/<dom>/<book>.md" [CHUNKS=N] [FORCE=1]
	PYTHONPATH=system/lib uv run --extra bricks python system/skills/distillateur/distill_book.py "$(BOOK)" $(CHUNKS) $(if $(filter 1,$(FORCE)),--force,)

distill-sommaire: ## PRINT the book's MAP only — index | title | characters per section, and the total. The cheap way to find WHERE a chapter lives: the same chunking as the emission, without the emission (measured: finding one chapter used to cost 1,008,988 bytes of stdout). No model/brick. Usage: make distill-sommaire BOOK="knowledge/raw/<dom>/<book>.md" [CHUNKS=N] [HAIKU=1]
	PYTHONPATH=system/lib uv run python system/skills/distillateur/emit_prompts.py "$(BOOK)" $(CHUNKS) --sommaire $(if $(HAIKU),--haiku,)

distill-emit: ## EMIT (from the single code source) the exact per-section prompts + schema + source-gate verdict for ONE book, for a FRONTIER host/agent to apply. HAIKU=1 sizes sections to Haiku; RANGE=a:b emits only that SLICE (one agent per slice — a big book does not fit one agent); CHAPTER="title" aims by NAME instead of rank (OCR-tolerant match, refuses on 0 or several rather than picking one silently — `make distill-sommaire` lists them). No model/brick. Usage: make distill-emit BOOK="knowledge/raw/<dom>/<book>.md" [CHUNKS=N] [FORCE=1] [HAIKU=1] [RANGE=1:6] [CHAPTER="acknowledgments"]
	PYTHONPATH=system/lib uv run python system/skills/distillateur/emit_prompts.py "$(BOOK)" $(CHUNKS) $(if $(filter 1,$(FORCE)),--force,) $(if $(HAIKU),--haiku,) $(if $(RANGE),--range $(RANGE),) $(if $(CHAPTER),--chapter "$(CHAPTER)",)

distill-emit-split: ## EMIT one prompt file PER SECTION for ONE book + print the HAIKU agent dispatch plan (the replayable agent lane, D145 — see system/skills/distillateur/AGENT_BRIEF.md). Then: dispatch ~5 sections per Haiku agent, and `make distill-apply`. No model/brick. Usage: make distill-emit-split BOOK="knowledge/raw/<dom>/<book>.md" OUT="<dir>" [FORCE=1]
	PYTHONPATH=system/lib uv run python system/skills/distillateur/emit_prompts.py "$(BOOK)" --split-dir "$(OUT)" $(if $(filter 1,$(FORCE)),--force,)

distill-batch: ## Distil MANY public books via Claude Haiku IN PARALLEL (frontier campaign) — needs `--extra bricks` + ANTHROPIC_API_KEY + api.anthropic.com allow-listed. Public-by-provenance, Guard-gated, personal families EXCLUDED by default, idempotent, repeatable. Usage: make distill-batch [DOMAIN=macro] [WORKERS=6] [LIMIT=N] [CHUNKS=N] [DRY=1] [FORCE=1] [PERSO=1]
	PYTHONPATH=system/lib uv run --extra bricks python system/skills/distillateur/distill_campaign.py $(if $(DOMAIN),--domain "$(DOMAIN)",) $(if $(WORKERS),--workers $(WORKERS),) $(if $(LIMIT),--limit $(LIMIT),) $(if $(CHUNKS),--chunks $(CHUNKS),) $(if $(DRY),--dry-run,) $(if $(filter 1,$(FORCE)),--force,) $(if $(filter 1,$(PERSO)),--include-personal,)

distill-apply: ## ASSEMBLE a fiche from an AGENT's per-section JSON answers (the apply counterpart of distill-emit): code applies the verbatim floor (D143) + DEMANDS completeness. No model/brick. Usage: make distill-apply BOOK="knowledge/raw/<dom>/<book>.md" SECTIONS="answers.json" [HAIKU=1]
	PYTHONPATH=system/lib uv run python system/skills/distillateur/distill_apply.py "$(BOOK)" "$(SECTIONS)" $(if $(HAIKU),--haiku,)

judge: ## Verify ALL of distilled/ against raw/ via the juge skill (no model, no bricks) — flags hollow/paraphrased fiches. Writes system/logs/judge_report.md. To check ONE fiche you just wrote, use `make verbatim-check` instead (targeted, print-only).
	PYTHONPATH=system/lib uv run python system/skills/juge/judge_library.py

verbatim-check: ## Replay the verbatim floor on ONE fiche — the TARGETED, PRINT-ONLY door to what `make judge` checks in bulk (measured: 249 books, 9.79 s, names 1 fiche out of 249, writes a report). Same hearth as the judge; additionally NAMES the passages the floor DROPS — the repair list judge_fiche computes and throws away. Exit 0 = PASSE, anything else = this fiche must not enter the base (make reports every refusal as exit 2 — read `VERDICT:` on stdout to tell a rejection from a usage refusal). Usage: make verbatim-check FICHE="knowledge/distilled/<dom>/<book>.md" [BOOK="knowledge/raw/<dom>/<book>.md"]
	PYTHONPATH=system/lib uv run python system/skills/juge/verbatim_check.py "$(FICHE)" $(if $(BOOK),--raw "$(BOOK)",)

finish: ## Polish readability of distilled/ via the finisseur skill (deterministic floor, no model) — rebuilds bad chapter titles, NEVER touches P3. Re-run `make judge` after.
	PYTHONPATH=system/lib uv run python system/skills/finisseur/finish_book.py

finish-emit: ## EMIT (from the single code source) the exact polish contract + fail-closed safety verdict + chapter state for ONE fiche, for a FRONTIER host (Codex) to apply. No model/brick. Usage: make finish-emit FICHE="knowledge/distilled/<dom>/<book>.md"
	PYTHONPATH=system/lib uv run python system/skills/finisseur/finish_emit.py "$(FICHE)"

regle-promouvoir: ## Level 1 -- REAL gate, OPTIONAL caller, for `exiger_panne_declaree` (I3) -- reads a candidate rule fiche, REFUSES (rc=1) if its defect is not declared, and on success NAMES (never runs) the exact chain to the differential trial (skill-new -> skill-eprouver -> ... -> skill-verdict). Nothing forces going through this gate -- an agent may jump straight to skill-new. No model/brick. Usage: make regle-promouvoir FICHE="knowledge/proposals/<fiche>.md"
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.regle_promouvoir_run "$(FICHE)"

skill-new: ## Scaffold a DRAFT skill (code-home stub + thin adapter + Makefile target + lock-test stub) via the skill-creator skill. No model/brick. Usage: make skill-new NEED="what the skill must do" [NAME=kebab-name]
	PYTHONPATH=system/lib uv run python system/skills/skill-creator/new_skill.py "$(NEED)" $(NAME)

skill-emit: ## EMIT (from the single code source) the skill-anatomy contract + the 6-lesson checklist every skill must encode. No model/brick. Usage: make skill-emit
	PYTHONPATH=system/lib uv run python system/skills/skill-creator/skill_emit.py

skill-audit: ## Verify-in-code that a candidate skill respects the anatomy (emit seam, anti-drift lint, frontmatter, scaffold_only axis) via the skill-creator skill. No model/brick. Usage: make skill-audit DIR="system/skills/<name>"
	PYTHONPATH=system/lib uv run python system/skills/skill-creator/audit_skill.py "$(DIR)"

skill-eprouver: ## Step 1 of the differential trial — emit BOTH arm mandates and a SECRET SALT into a trial directory. The blind arm's mandate is built by a function that never receives the skill name; the salt is what makes the judge's blinding unrecoverable. Prints what the trial CANNOT establish. Usage: make skill-eprouver SKILL=distillateur TACHE="..." OUT=/tmp/epreuve [REFERENCE="prior state"]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.skill_trial_run eprouver --skill "$(SKILL)" --tache "$(TACHE)" --out "$(OUT)" $(if $(REFERENCE),--reference "$(REFERENCE)",)

skill-juger: ## Step 2 — emit the judge's mandate from the two real outputs, labelled A/B under the trial's secret salt. REFUSES when an output names its own arm (measured on the first real trial: the equipped arm cites its artifact); add OUVERT=1 to judge in the open instead, and the verdict must then carry AVEUGLEMENT=rompu. Usage: make skill-juger EPREUVE=/tmp/epreuve AVEC=/tmp/sortie-avec.md SANS=/tmp/sortie-sans.md [OUVERT=1]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.skill_trial_run juger --epreuve "$(EPREUVE)" --avec "$(AVEC)" --sans "$(SANS)" $(if $(OUVERT),--ouvert,)

skill-verdict: ## Step 3 — RECORD what the trial showed. Re-reads the outputs AND the emitted mandates, and digests them itself: a verdict about a trial that was never emitted has no directory to cite. Outcomes: differencie / ne_differencie_pas / nuit. PAR and AVEUGLEMENT (aveugle|rompu) have NO default — a verdict that stays silent about its blinding reads exactly like a clean one. Usage: make skill-verdict EPREUVE=... SKILL=... TACHE="..." AVEC=... SANS=... VERDICT=nuit PREUVE="..." AVEUGLEMENT=aveugle PAR="..."
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.skill_trial_run verdict --epreuve "$(EPREUVE)" --skill "$(SKILL)" --tache "$(TACHE)" --avec "$(AVEC)" --sans "$(SANS)" --verdict "$(VERDICT)" --preuve "$(PREUVE)" --aveuglement "$(AVEUGLEMENT)" --par "$(PAR)"

obligation: ## A2: PUBLISHES the obligation scale (1 nudge / 2 barrier / 3 incapacity) and NAMES the targets that declare none. The level is the CALLER's, never the code's: a target that exits 1 with nobody consuming its rc is a level 1. The registry lives in docs/governance/OBLIGATION.md (the .md is authoritative, D44); a level 2/3 must NAME its mechanism AND its caller there. PUBLISHES, does not refuse (rc 0 even when almost none of the targets declare any); rc 1 if the registry LIES TO ITSELF (nonexistent target, level off the scale, level 2/3 with no mechanism, duplicate, an unreadable line that would be silently lost); rc 2 if the measurement is impossible. CAUTION: the module lived since 2026-08-14 19:00 with NO target at all to call it, even though OBLIGATION.md quoted this very help line verbatim -- the registry that publishes what this repo OBLIGES had no command. Read-only, no brick, no model. Usage: make obligation
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.obligation_run

sites-de-sortie: ## THE EGRESS-SITE FREEZE (inv. 1 / inv. 5, D156) -- surveys by AST every `file::module` of `system/lib/` that carries an EGRESS capability (network, process) and compares the SET against its freeze. REFUSES at rc=1 as soon as a site appears with NO declaration, or a declaration no longer covers any site (the freeze would rot silently); rc=2 if ZERO sites are compared -- an empty survey is an instrument failure, never a pass. SCOPE: it scans `system/lib/`, exactly the zone `CLAUDE.md` already says has "no back door" -- it VERIFIES that promise, it does NOT close the "outside" (project engine, personal script) that the same sentence declares open. v1 claimed the opposite; an isolated audit measured it. A model of CAPABILITY, never of intent: a `subprocess` that only launches a `git log` counts, and that is deliberate. Reads STATIC imports: a dynamically-built `__import__` escapes it -- it protects against ACCIDENT and drift, never an adversary. `tick` PUBLISHES it (level 1, rc discarded); HERE the rc bites -- but CAUTION, measured: `make` flattens rc=1 AND rc=2 into 2, so the refusal/not-measured distinction reads in the TEXT, never in the exit code. Read-only, no brick, no model. Usage: make sites-de-sortie
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.sites_run

passes: ## G3+G5: THE PRE-COMMIT PASS SURVEY, frozen and surveyed by AST on TWO axes -- WIRING (the header is written under a call, in a scope that can exit with an error) and REACHABILITY (that scope is reachable from the module). REFUSES (rc=1) when a FROZEN pass is no longer seen; a NEW pass is PUBLISHED, never refused (a floor, not an equality: otherwise adding a guarantee would cost a red). rc=2 if zero passes are surveyed -- an empty table is an instrument failure. The denominator is THE FREEZE, never len(seen): a shrinking survey would declare itself complete. Measured on 2026-09-08: 5 refusal passes, and no file carried such a table. Surfaced by the sibling project's harvest (G3, G5). Cost measured: 10.9 ms. Read-only, no brick, no model. Usage: make passes
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.passes_run

batterie: ## G4: THE BATTERY THAT CANNOT MELT -- refuses on failure, on SKIP, and on a MUTE TEST (a witness with no assertion is a bought green). Two bidirectional ratchets: they refuse degradation just as much as an UNDECLARED improvement, because a figure that moves without anyone knowing stops being a measurement. Measured on 2026-09-08: 42 skip sites, 14 mute witnesses out of 4232. --gel reprints both freezes ready to paste, without ever writing. rc=1 refusal, rc=2 not measured. CAUTION, cost measured: 2558 ms over the whole of tests/ -- too slow for the commit path as-is; if wanted there, judge only the STAGED test files. Surfaced by the sibling project's harvest (G4). Read-only, no brick, no model. Usage: make batterie
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.batterie_run

clotures: ## P1: A CLOSURE WITH NO AUTHOR IS REFUSED -- a closure nobody can verify is not a closure. Measured on 2026-09-08: 22 closures in docs/signalements/, ZERO authors, 7 without even a date. The inheritance ratchet carries these 22 entries, derived from a command and never copied by hand, and refuses in BOTH directions (an entry disappearing from the ratchet is just as abnormal as a new one). A status outside the vocabulary is NAMED, never swallowed. DECLARED REFUSAL inside the item: the 'accepted at no cost' clause is written and tested but bites on 0/34 -- the vocabulary does not have that status, and creating it is the operator's decision. Surfaced by the sibling project's harvest (P1). Cost measured: 20 ms. Read-only, no brick, no model. Usage: make clotures
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.cloture_run

fermeture-glyphe: ## P9: DECLARED CLOSURE <-> FLIPPED GLYPH IN THE SAME COMMIT. This was the sibling project's recommendation number 6, the ONLY one that asked for a barrier, nonexistent for 19 days -- and Mnemosyne had made the SAME diagnosis FIVE DAYS EARLIER without ever building the gate. Measured by the judge's own accessor over 2196 commits: 111 status movements, 100 closures, 5 REFUSED (5%), ZERO false positive. rc=1 refusal, rc=2 not measured. Its real home is the commit-msg hook, which DOES NOT EXIST in .githooks/: pre-commit cannot hold it, the message is not written yet at that point. Until that hook exists, this target is LEVEL 1 and must be pulled by hand -- it judges HEAD by default (REV=<ref> for another commit, MESSAGE_FILE=<path> for a message not yet committed). Without --rev it ALWAYS returned 'not measured': measured by an isolated audit, the documented usage did not work. Read-only, no brick, no model. Usage: make fermeture-glyphe
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.fermeture_declaree_run $(if $(REV),--rev "$(REV)",--rev HEAD) $(if $(MESSAGE_FILE),--message-file "$(MESSAGE_FILE)",)

disjoncteur: ## G2: ON THE 3rd NEGATIVE VERDICT, ANNOUNCE; ON THE 4th, SPLIT. An item repaired in a loop is not a hard item, it is a BADLY SPLIT item -- and nobody sees it from inside the loop. Run against the real plan on 2026-09-08: 21 open items, 3 triggers, rc=1 (one item had 9 repairs in a row over 10 turns). ADMISSION, written in the module: this repo has NO structured verdict registry. The substitute is the commit `fix(IDENT)` -- feat/test reset the count, docs/plan/orch are transparent. An item repaired three times WITHOUT A COMMIT is invisible to this gate. Surfaced by the sibling project's harvest (G2). Read-only, no brick, no model. Usage: make disjoncteur
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.disjoncteur_run

attribution: ## P2: WHO HOLDS WHICH ARC -- the registry that lives at the SENDER's end, and that REFUSES a collision. Measured on 2026-09-08: a REAL collision exists and nothing names it -- arc H is claimed by BOTH chat-2 AND chat-3, and make ui-json publishes both as fact, without a word. The READ side already existed (ui_contract): it is IMPORTED, never copied — what was missing was the REFUSAL. Collision and unknown arc REFUSE; a stale holding only PUBLISHES (4 of the 6 real holdings are stale: refusing would block two-thirds of the registry on day one). ADMISSION: the read happens with no lock -- two simultaneous emissions could grant the same arc. Call this BEFORE make lot-emit. Usage: make attribution (audit) or make attribution ARC=H POUR=chat-4 (the gate)
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.attribution_run $(if $(ARC),--arc "$(ARC)",) $(if $(POUR),--pour "$(POUR)",)

passation: ## G10: A THIRD PARTY DECLARES A PEER'S STATE BY MEASUREMENT, NEVER ON THEIR WORD. Measured on 2026-09-08: 21 commits where one chat declares a peer's state, and ZERO occurrences of 'handover' in ORCHESTRATION.md or in docs/postes/README.md -- all 21 are taken on word alone. Four refusals, including sur_parole, which is judged BEFORE any denial: the rule governs the WAY OF KNOWING, not the fact known. Reuses non_committe.lire (the Stop hook's judge) and carte_par_arc. TWO ADMISSIONS: durability is not attributable to a peer here (single tree, D175), and NOTHING forces a third party to call this gate before writing a sentence about a peer. Usage: make passation PAIR=chat-N ETAT=... SOURCE=...
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.passation_run $(if $(PAIR),--pair "$(PAIR)",) $(if $(ETAT),--etat "$(ETAT)",) $(if $(SOURCE),--source "$(SOURCE)",)

precedence: ## G9: REPO PROCEDURE OUTRANKS THE MANDATE'S OWN PROMPT. This is what lets an agent catch an error IN ITS OWN MANDATE instead of executing it. Measured on 2026-09-08: precedence was written NOWHERE (0 hits across docs/, CLAUDE.md, or this repo's other governance docs) even though 17 commits name a mandate error -- the repo carried only the MIRROR side in memory, never the recipient side. Single home, EMITTED by lot_emit.rendre(): without that the rule would live in a document the recipient never reads. REFUSES if the mandate does not carry the clause, or if one of its addresses no longer exists on disk. ADMISSION: it detects NO contradiction (a question of meaning, not of form) and forces nobody to obey. Usage: make precedence
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.precedence_run

plafond-rotation: ## P4: THE LINE CEILING AS A BARRIER, with NON-DESTRUCTIVE rotation. What breaks without it, measured: docs/postes/README.md PRESCRIBES that a compacted chat RE-READ its journal, and the journals reached 6038-7199 lines in four days -- the prescribed re-reading became impossible IN SILENCE. The tradeoff was left open in the end-of-session summary, raised three times, never settled; the files grew 14x. The number is DERIVED (a scan over 828 real versions), never copied from the sibling project. The half that matters: a ceiling alone would teach CUTTING the start of the file -- the coupe_sans_archive clause refuses any shrink whose removed lines are not in an archive from the SAME commit. IT EXITS rc=1 TODAY and names 4 archives to create: wiring it into the commit path RIGHT NOW would refuse EVERY commit. The order is: run the make target, then rotate the 4 journals, then --mis-en-scene. Usage: make plafond-rotation
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plafond_rotation_run

diffusion: ## G8: EVERY DIFFUSED RULE NAMES THE POPULATION IT WAS MEASURED ON. Measured on 2026-09-08: 0 of 6 *-emit targets carry a commit id or an emission date -- a contract installed at a project can neither be dated, nor verify it holds the history its rule was measured on. On the receiving side, VERIFIER=<file> REFUSES: no stamp, commit absent from history, tree modified at emission, and UNREADABLE history (the worst case must not pass for the best). The default mode only PUBLISHES and writes why it is not a gate: at 0/6, a gate would be born red and un-greenable without rewriting 6 modules -- a wall gets walked around, an accusation gets read. Usage: make diffusion (state) or make diffusion TAMPON=1 or make diffusion VERIFIER=<file>
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.diffusion_run $(if $(TAMPON),--tampon,) $(if $(VERIFIER),--verifier "$(VERIFIER)",)

avancement: ## P3: THE WEIGHTED LADLE, PUBLISHED SIDE BY SIDE WITH THE PLAIN COUNT. Measured on 2026-09-08: 86 items all declare a Size, and only 6 render a readable weight. Real output: 75.6% by count, 58.0% weighted -- and 'no readable weight: 80/86' is written ON THE SAME LINE as the percentage, because a reader copies a figure, never a report. Louche.degradee states in plain words when the weighting no longer has any arithmetic effect: a ladle whose weights are missing degrades into a plain count WITHOUT SAYING SO, and that is exactly the fault it exists to make impossible. NEVER a gate: rc=0 regardless of progress, rc=2 only on an instrument failure. Usage: make avancement DOSSIER=...
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.avancement_run

accord-chiffre: ## P6: A FIGURE COPIED INTO PROSE VISITS EVERY SITE, NEVER A TOTAL -- a total that agrees on one side and is wrong on the other is the REAL case, not a hypothesis. Measured on 2026-09-08: the invariant count is copied 41 times across 30 tracked files, and production/derives.py already admitted no barrier covered it. The reference is RECOMPUTED, never re-read: no 27 is hard-coded in the module. Section not found or empty -> RAISES, because a 0 would accuse the whole repo. The distinction between a LIVE copy and a DATED record is carried by the PATH, not by a word: classifying dated copies as live would have produced 4 false accusations the day the figure moves. Usage: make accord-chiffre
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.accord_chiffre_run

besoin: ## P8: FILE a need -- something a chat cannot decide alone, written, dated, tracked by git. The PIVOT field is REFUSED if empty: a need with no pivot is a stop in disguise, and the whole channel exists so its author CONTINUES. TYPE is either humain (a gesture only the operator can make) or inter-arc (a peer must decide). Non-destructive: nothing is ever deleted, it gets decided (inv. 2). Usage: make besoin TYPE=humain TITRE="..." QUESTION="..." PIVOT="what I did in the meantime" EMETTEUR=chat-N
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.besoins_run --deposer --type "$(TYPE)" --titre "$(TITRE)" --question "$(QUESTION)" --pivot "$(PIVOT)" --emetteur "$(EMETTEUR)" --destinataire "$(DESTINATAIRE)"

besoin-trancher: ## P8: DECIDE a need -- requires a written DECISION, recorded in the file. A need is never deleted (inv. 2): it gets decided, and the decision stays readable for whoever reads it later. Usage: make besoin-trancher CHEMIN=docs/besoins/....md DECISION="..."
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.besoins_run --trancher "$(CHEMIN)" --decision "$(DECISION)"

besoins: ## P8: THE CHANNEL WHERE A CHAT FILES WHAT IT CANNOT DECIDE ALONE, THEN MOVES ON WITHOUT WAITING. Measured on 2026-09-08: 48 tracked .md files carry a wait on a gesture from the operator, with no status, no date, no drain -- and the channel was REINVENTED BY HAND twice in the same folder. The PIVOT field is MANDATORY and REFUSES if empty: that is the clause that makes the whole channel work, a need with no pivot is a stop in disguise. Deciding requires a written DECISION; nothing is ever deleted (inv. 2). A status outside the vocabulary is NAMED. Unlike docs/signalements/ (gitignored by design), this channel is TRACKED BY GIT -- that is its whole point, it crosses between chats. Usage: make besoins (state) or make besoin TITRE=... or make besoin-trancher ID=... DECISION=...
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.besoins_run

commit-garde: ## P5: WAIT FOR A CALM WINDOW WITH A CEILING, THEN PROVE THE GESTURE BY HEAD -- in BOTH directions: HEAD not moving despite rc=0 (a pipe swallowing the failure) AND HEAD moving despite rc!=0 (replaying would duplicate). Measured on 2026-09-08: 1716 commits over 30 days, 26 intervals at 2 s or less, median 90 s. The three bounds are of DIFFERENT natures and the module writes this so a reader never confuses them: a wait ceiling (wall-clock, I give up on the queue), an anti-deadlock safeguard (wall-clock, NEVER a cost judgment) and the ONLY cost budget, in CPU. This last point is G12, RE-MEASURED HERE and not copied from the sibling project: over 10 interleaved pairs, the loaded/free ratio is x1.80 in WALL-CLOCK versus x1.28 in CPU, 10 times out of 10. Usage: make commit-garde MESSAGE="..."
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.guetteur_commit -- git commit -m "$(MESSAGE)"


plancher: ## D3: THE PRODUCTION FLOOR -- a REVERSED ratchet (the only one that refuses EXCESS rigor, not regression). Below X=30% share produced over N=1 day (derived from the real 21-22 July curve, denominator BOUNDED to the measured project, never eyeballed -- see docs/governance/PLANCHER.md), you can no longer OPEN a new HARDENING workstream; OPENING a PRODUCT workstream and CLOSING what is already open remain ALWAYS allowed -- non-punitive by construction, and it never prevents the very return to production the floor exists to provoke. The gesture is DECLARED (ouvrir_blindage/ouvrir_produit/fermer), never guessed (D2 applied to the gesture). Publishes the state (crossed or not, recent days) for the project whose PRODUIT.md is declared beside its plan gate; NAMES "FLOOR NOT MEASURED" rather than guessing when no declaration exists. Level 1 in publication (it refuses nothing itself) -- the refusal lives in mnemosyne.runtime.plancher_run.peut(), called by whoever actually makes an opening gesture. Read-only, no brick, no model. Usage: make plancher
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plancher_run

moisson: ## Emit the HARVEST contract for a finished project arc — what the project owes back to the system (ame §3, D24/D37). The orchestrator RECRUITS agents expert in the PROJECT'S OWN FIELD (a repo rule is judged by someone who knows repos; a measurement regime by someone who knows the field), then rules GENERIQUE / PARAMETRABLE / DOUBLON / SPECIFIQUE. Promotes nothing: candidates stay inert and must pass a differential trial. Usage: make moisson PROJET="projects/saas/Sibling Research" [EXPERTS=5] [MECANICIENS=3]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.harvest_run --projet "$(PROJET)" $(if $(EXPERTS),--experts $(EXPERTS),) $(if $(MECANICIENS),--mecaniciens $(MECANICIENS),)

skill-epreuves: ## READ the trial journal — `nuit` verdicts FIRST, and unreadable lines COUNTED. Exists because a recorded verdict nobody can read is a verdict that does not exist. Usage: make skill-epreuves
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.skill_trial_run epreuves

garde-emit: ## EMIT the shell guard to an OTHER host (D163: the address, never the copy). Renders the exact text to install -- a five-line hook that POINTS to Mnemosyne's single judge, plus the settings.json entry, plus TWO trial runs (it must both bite AND let a quoted heredoc through: a guard that refuses everything passes the first trial). Copying the judge to every host would produce as many versions as hosts, and they would drift. WRITES NOTHING anywhere: installing is the host's gesture, and the sibling project's repo is FROZEN. Usage: make garde-emit
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.garde_emit_run

lot-emit: ## E4: EMIT the mandate for an arc's chat -- its items, its aggregated *reading list* context (C4), its rendezvous point. Assembles and publishes from fields ALREADY published in the plan, never an orchestrator's own reasoning (a witness that goes red if it leaks). WRITES NOTHING: the mandate goes to stdout. Usage: make lot-emit ARC=<letter, or sub-plan path on a plan with folder sub-plans> [PLAN=docs]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.lot_emit_run "$(ARC)" $(if $(PLAN),--plan "$(PLAN)",)

plan-gate-emit: ## J1: EMIT the plan barrier (D166 clause 4) to an OTHER host. Renders the exact text to install -- a five-line pointer to the single judge (plan_format.index_problems), plus TWO trial runs (it must REFUSE an unindexed arc AND LET THROUGH an honest commit). Reads DISK, like `make plans` -- this is NOT .githooks/pre-commit (which judges the git STAGE index, 350 lines specific to Mnemosyne). WRITES NOTHING anywhere. Usage: make plan-gate-emit
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plan_gate_emit_run

item-retirer: ## H1: REMOVING an item from a plan becomes a gesture, never a text editor -- demander/examiner/approuver/refuser/appliquer, modeled on `make policy-*` (D159). A pass-through to chat 1's CLI (`plan_retrait_run`), which carries its own subcommands. Usage: make item-retirer ARGS="queue" | make item-retirer ARGS="demander ITEMS=... MOTIF=... COUT=..." (see `python -m mnemosyne.runtime.plan_retrait_run --help`)
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.plan_retrait_run $(ARGS)

arsenal: ## B2/B3: WHAT MNEMOSYNE OFFERS YOU, sorted by what it BUYS you — and you take what you want. The 30-second page, where `make help` is a wall (87 targets, 29,659 bytes, median 243 bytes per line, 77 of 87 targets above 100) and where `make describe` renders 7 abstract surfaces without naming a single command. States plainly, target by target, what your frontier host already carries () and what exists only here ( a gate that refuses, a state of the repo, a single home). The hard rules are NOT here: it is the tooling that becomes optional, never the safety. Bijection verified against the Makefile in BOTH directions — a new, unclassified target is NAMED (exit 1), the offer prints anyway. Read-only, no brick. `POUR=<plan gate>` (B4) renders only the weapons THIS project declared cold in its gate, and NAMES a declaration that designates no target -- declaring nothing remains a valid answer. Usage: make arsenal [DETAIL=1] [POUR=projects/<bubble>/<project>/PLAN.md]
	@PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.arsenal_run

documents: ## A3: REPORT of documents that nothing cites anymore (`a document that nothing points to does not exist`). Read-only, no threshold: the criterion is CITATION, age is only a sort key. MOVES NOTHING -- archiving is a judgment call, and moving one of the operator's files is THEIR gesture (D74). Usage: make documents
	PYTHONPATH=system/lib uv run python -m mnemosyne.runtime.documents_run

rangement: ## Tidy the repo: quarantine CLEAR cruft (OS files, stale manifest backups, old logs, misplaced outputs) non-destructively + reversibly (item 7 / D74 / D92). No model/brick. DRY-RUN by default; APPLY=1 to move. NEVER deletes. Usage: make rangement [APPLY=1]
	PYTHONPATH=system/lib uv run python system/skills/rangement/rangement_run.py $(if $(filter 1,$(APPLY)),--apply,)

rangement-emit: ## EMIT (from the single code source) the rangement contract for a FRONTIER host (Claude Code) to apply — the plan + the judgment pass (propose ambiguous mess, never move it). No model/brick. Usage: make rangement-emit
	PYTHONPATH=system/lib uv run python system/skills/rangement/rangement_emit.py

hooks: ## Install the local pre-push CI hook (sets core.hooksPath)
	git config core.hooksPath .githooks
	@echo "pre-push hook active → 'make test' will gate any promotion."

cours: ## Emit the governed contract for a source-backed course about PROJECT. Usage: make cours PROJECT="path" COURSE="name"
	PYTHONPATH=system/lib uv run python system/skills/cours/cours_run.py emit --project "$(PROJECT)" --course "$(COURSE)"

cours-emit: ## Emit the exact course contract for a frontier executor; writes nothing. Usage: make cours-emit PROJECT="path" COURSE="name"
	PYTHONPATH=system/lib uv run python system/skills/cours/cours_run.py emit --project "$(PROJECT)" --course "$(COURSE)"

cours-verifier: ## Verify a course against PROJECT's source boundary; never edits it. Usage: make cours-verifier PROJECT="path" COURSE="name"
	PYTHONPATH=system/lib uv run python system/skills/cours/cours_run.py verify --project "$(PROJECT)" --course "$(COURSE)"

harnais-de-sabotage: ## Deliberately breaks a test suite's guarantee to prove a witness BITES, never that it is merely assumed green -- active since 2026-08-16, proven by differential trial. Usage: make harnais-de-sabotage
	PYTHONPATH=system/lib uv run python system/skills/harnais-de-sabotage/harnais-de-sabotage_run.py

public-mirror: ## Print the deterministic sync plan for projects/mnemosyne/mnemosyne-github (no model): paths changed since the last sync, split in/out of scope. Writes nothing. No model/brick. Usage: make public-mirror
	PYTHONPATH=system/lib uv run python system/skills/public-mirror/public-mirror_run.py plan

public-mirror-verify: ## Scan the export tree (projects/mnemosyne/mnemosyne-github) for a secret or this repo owner's personal-identity strings -- fail-closed gate to run before any local commit there. No model/brick. Usage: make public-mirror-verify
	PYTHONPATH=system/lib uv run python system/skills/public-mirror/public-mirror_run.py verify

public-mirror-mark-synced: ## Record the export as caught up to source HEAD (or COMMIT=<sha>) -- call ONLY after sanitizing + verifying + committing locally in the export repo. No model/brick. Usage: make public-mirror-mark-synced [COMMIT=<sha>]
	PYTHONPATH=system/lib uv run python system/skills/public-mirror/public-mirror_run.py mark-synced $(COMMIT)

public-mirror-emit: ## EMIT (from the single code source) the complete, self-sufficient public-mirror contract -- scope + per-file sanitization checklist + steps -- for ANY LLM host to follow with zero extra input. No model/brick. Usage: make public-mirror-emit
	PYTHONPATH=system/lib uv run python system/skills/public-mirror/public-mirror_emit.py
