// system/lib/mnemosyne/production/mecanique-en-lot.js
//
// THIS FILE IS NOT PYTHON -- deliberately. It runs through the platform's `Workflow` tool
// (scriptPath), never imported by `production/__init__.py`. Its place HERE, next to the Python
// production modules, follows the same gesture as the rest of the folder -- but do NOT CONFUSE it
// with `workflow.py` in the same folder: that one is a DIFFERENT concept (the draft -> audit ->
// promotion cycle for a deliverable, D79/D121-D1). This one is a script for the Workflow tool,
// unrelated to that cycle.
//
// Language: French, deliberately -- the same exception to D117 already taken by a_lire.py /
// derives.py / orchestration.py / offre_aux_projets.py in this same folder: this domain is read
// by the operator. The names imposed by the TOOL'S OWN CONTRACT (meta / agent / opts / pipeline /
// parallel / phase / log / args / schema / model) stay in English: this is not domain
// vocabulary, it is the tool's API.
//
// WHAT THIS SCRIPT NEVER JUDGES: whether the task it is given is really mechanical (the
// 3-question qualification test lives in this repository's own orchestration documentation,
// never copied here, D163). That is a human decision made BEFORE calling this tool -- this file
// EXECUTES, it does not qualify. Misuse breaks nothing visible: at worst, a mediocre translation
// that gets re-run -- which is why this mechanism does not carry the skill governance (SKILL.md,
// the DRAFT->AUDITED->ACTIVE cycle, audit D39-6): its worst case is cheap.
//
// CAUTION WRITTEN DOWN, NOT ASSUMED (this repository's own model-choice policy, S3): using Haiku
// for the dispatch follows the SHAPE of "the rule that trickles down" (D145), but D145 covers
// ONLY distillation until a second REAL precedent confirms it -- "extending it... is a gesture to
// measure, not to assume by analogy." This script is therefore a CANDIDATE for that second
// precedent, not yet a second precedent: it only becomes one after real use confirms that Haiku
// holds the contract for this class of task too.

export const meta = {
  name: "mecanique-en-lot",
  description:
    "Delegates a batch of units (files/sections) to one Haiku agent each, in waves bounded by maxParallel, then has the full set of results re-read by an agent on the session's inherited model to publish coherence gaps between units -- never to fix them.",
  phases: [
    {
      title: "Validation",
      detail: "Every unit has a path and a resolved instruction before any agent leaves.",
    },
    {
      title: "Mechanical dispatch",
      detail: "One Haiku agent per unit, in successive waves of at most maxParallel units.",
    },
    {
      title: "Cross-consistency check",
      detail: "A single agent, on the session's inherited model, compares all the results and publishes the gaps -- without fixing them.",
    },
  ],
};

// A REAL DEFECT FOUND BY RUNNING THIS SCRIPT FOR REAL (2026-08-19), NOT BY READING IT:
// `meta` IS NOT A LIVE BINDING DURING EXECUTION -- the tool extracts it separately (for the
// confirmation dialog) and the rest of the script runs WITHOUT `meta` available. "meta.phases[0]"
// here used to throw `meta is not defined`. The titles are therefore DUPLICATED BY HAND between
// `meta.phases` above and these three constants -- the drift the earlier comment meant to avoid
// is now a REAL risk, accepted for lack of a better option: if a title changes in `meta`, change
// it HERE too -- the two copies no longer check each other.
const TITRE_VALIDATION = "Validation";
const TITRE_DISPATCH = "Mechanical dispatch";
const TITRE_COHERENCE = "Cross-consistency check";

// Number of units processed AT THE SAME TIME when args.maxParallel is absent. Not the platform's
// implicit ceiling (16): a caller who states no preference should still get a STAGGERED dispatch
// (visible waves), not a single burst. 5 bounds the damage if the instruction turns out bad: 5
// damaged units before the first visible stopping point, not 16.
const MAX_PARALLEL_PAR_DEFAUT = 5;

// Every result passed to the coherence pass is truncated to this many characters --
// deterministic, computed by the code, never left to an agent's judgment (the same guarantee as
// the splitting itself, per this repository's own model-choice policy). Without a ceiling, a
// batch of large files would blow up the final pass's prompt.
const EXTRAIT_MAX_COHERENCE = 4000;

// The tool's hard ceiling (parallel()/pipeline() accept at most 4096 items per call) -- a safety
// rail, not a realistic expectation.
const MAX_PARALLEL_PLAFOND_OUTIL = 4096;

// Output contract of the coherence pass -- ONE list of gaps, each naming the units involved and
// describing the gap. Nothing more: no severity, no proposed fix.
const SCHEMA_COHERENCE = {
  type: "object",
  additionalProperties: false,
  required: ["ecarts"],
  properties: {
    ecarts: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["unites_concernees", "description"],
        properties: {
          unites_concernees: { type: "array", items: { type: "string" }, minItems: 1 },
          description: { type: "string", minLength: 1 },
        },
      },
    },
  },
};

/**
 * Checks and normalises `args` -- REFUSES (throws) instead of letting an agent guess what the
 * calling chat got wrong. Three named refusals: a missing path, a unit with NO instruction at
 * all (neither its own nor a shared one), a DUPLICATE path (two agents writing the same file in
 * parallel would run over each other). PURE: no hooks, only `args` as input.
 */
function valider(args) {
  const unites = Array.isArray(args?.unites) ? args.unites : null;
  if (unites === null) {
    throw new Error(`REFUSED: args.unites must be an array -- received ${JSON.stringify(args?.unites)}`);
  }
  if (unites.length === 0) {
    return { unites: [], consigneCommune: null, maxParallel: MAX_PARALLEL_PAR_DEFAUT, vide: true };
  }

  const sansChemin = unites
    .map((u, i) => (typeof u?.chemin === "string" && u.chemin.length > 0 ? null : i))
    .filter((i) => i !== null);
  if (sansChemin.length > 0) {
    throw new Error(`REFUSED: ${sansChemin.length} unit(s) without a valid "chemin", index [${sansChemin.join(", ")}]`);
  }

  const chemins = unites.map((u) => u.chemin);
  const dupliques = [...new Set(chemins.filter((c, i) => chemins.indexOf(c) !== i))];
  if (dupliques.length > 0) {
    throw new Error(
      `REFUSED: ${dupliques.length} path(s) cited more than once -- two agents writing the ` +
        `same file in parallel would run over each other: ${dupliques.join(", ")}`
    );
  }

  const consigneCommune =
    typeof args.consigne_commune === "string" && args.consigne_commune.length > 0
      ? args.consigne_commune
      : null;
  const sansConsigne = unites
    .filter((u) => !(typeof u.consigne === "string" && u.consigne.length > 0) && consigneCommune === null)
    .map((u) => u.chemin);
  if (sansConsigne.length > 0) {
    throw new Error(
      `REFUSED: ${sansConsigne.length} unit(s) without an instruction (neither their own, nor consigne_commune): ` +
        sansConsigne.join(", ")
    );
  }

  let maxParallel = MAX_PARALLEL_PAR_DEFAUT;
  if (args.maxParallel !== undefined) {
    if (!Number.isInteger(args.maxParallel) || args.maxParallel < 1) {
      throw new Error(`REFUSED: maxParallel must be an integer >= 1 -- received ${JSON.stringify(args.maxParallel)}`);
    }
    if (args.maxParallel > MAX_PARALLEL_PLAFOND_OUTIL) {
      throw new Error(
        `REFUSED: maxParallel (${args.maxParallel}) exceeds the tool's ceiling ` +
          `(${MAX_PARALLEL_PLAFOND_OUTIL} items per parallel())`
      );
    }
    maxParallel = args.maxParallel;
  }

  return { unites, consigneCommune, maxParallel, vide: false };
}

// SIMPLE split into fixed-size batches. PURE.
function enLots(unites, taille) {
  const lots = [];
  for (let i = 0; i < unites.length; i += taille) {
    lots.push(unites.slice(i, i + taille));
  }
  return lots;
}

// PURE.
function promptUnite(unite, consigne) {
  return [
    "MECHANICAL task, no judgment on the substance -- follow the instruction LITERALLY, do not improvise,",
    "do not do anything it does not ask for.",
    "",
    `File: ${unite.chemin}`,
    `Instruction: ${consigne}`,
    "",
    "1. Read the file at this path.",
    "2. Apply the instruction, and only it.",
    "3. Write the result to this same path (replace the existing content).",
    "4. Return, as your final answer, ONLY the complete text you wrote -- no summary,",
    "   no comment on what you did, no pleasantries.",
  ].join("\n");
}

// PURE.
function construirePromptCoherence(resultats) {
  const extraits = resultats
    .filter((r) => r.ok)
    .map((r) => {
      const tronque = r.resultat.length > EXTRAIT_MAX_COHERENCE;
      const texte = tronque ? r.resultat.slice(0, EXTRAIT_MAX_COHERENCE) + "\n[...truncated...]" : r.resultat;
      return `--- UNIT: ${r.chemin} ---\nInstruction received: ${r.consigne}\n${texte}`;
    })
    .join("\n\n");
  return [
    "You are re-reading a BATCH of units that were already transformed INDEPENDENTLY -- each unit",
    "was handled by an agent who saw NONE of the others. Your only job: find the CONSISTENCY GAPS",
    "between them (a term translated differently from one unit to another, a structural convention",
    "applied inconsistently, etc.).",
    "",
    "Fix NOTHING -- you publish a finding, you do not repair. Do not judge the individual quality",
    "of one unit taken alone: only the gaps BETWEEN units matter here.",
    "If you find no gap, return an empty list -- an empty list is a valid answer,",
    "not a failure.",
    "",
    extraits,
  ].join("\n");
}

// `agent`/`log` are ambient globals from the tool's own contract -- no parameter for them.
async function dispatcherUnite(unite, consigne) {
  const resultat = await agent(promptUnite(unite, consigne), {
    label: unite.chemin,
    phase: TITRE_DISPATCH,
    model: "haiku",
  });
  const ok = typeof resultat === "string" && resultat.trim().length > 0;
  if (!ok) {
    log(`FAILED (empty or non-conforming response): ${unite.chemin}`);
  }
  return { chemin: unite.chemin, consigne, resultat: ok ? resultat : null, ok };
}

// ---- the script's body, at ROOT level -- no exported function wrapping it: the Workflow tool's
// real contract exposes agent/parallel/phase/log/args as ambient globals INSIDE the script's
// body, with a final `return` at root level. ----

phase(TITRE_VALIDATION);
const { unites, consigneCommune, maxParallel, vide } = valider(args);
log(`${unites.length} unit(s) to process, in waves of at most ${maxParallel}.`);

let sortie;
if (vide) {
  log("No units -- nothing to do.");
  sortie = { unites_totales: 0, unites_traitees: 0, unites_en_echec: [], lots: 0, maxParallel, ecarts: [] };
} else {
  phase(TITRE_DISPATCH);
  const lots = enLots(unites, maxParallel);
  let resultats = [];
  for (let i = 0; i < lots.length; i++) {
    const lot = lots[i];
    log(`batch ${i + 1}/${lots.length} (${lot.length} unit(s)): ${lot.map((u) => u.chemin).join(", ")}`);
    const resultatsLot = await parallel(
      lot.map((unite) => () => dispatcherUnite(unite, unite.consigne ?? consigneCommune))
    );
    // A thunk that THROWS (an error from the agent tool, not just an empty response) resolves to
    // `null` inside parallel() -- never a rejection (the tool's own contract). Without this
    // handling, a `null` would end up in `resultats` and `r.ok` would crash on the first
    // `.filter()` downstream -- two different failure causes (empty response vs. agent error)
    // must not overwrite one another.
    resultatsLot.forEach((r, idx) => {
      if (r === null) {
        const unite = lot[idx];
        log(`FAILED (agent error): ${unite.chemin}`);
        resultats.push({ chemin: unite.chemin, consigne: unite.consigne ?? consigneCommune, resultat: null, ok: false });
      } else {
        resultats.push(r);
      }
    });
  }

  const echecs = resultats.filter((r) => !r.ok).map((r) => r.chemin);
  if (echecs.length > 0) {
    log(`${echecs.length} unit(s) FAILED (empty response, non-conforming, or agent error): ${echecs.join(", ")}`);
  }

  phase(TITRE_COHERENCE);
  let ecarts;
  if (resultats.some((r) => r.ok)) {
    const promptCoherence = construirePromptCoherence(resultats);
    // A single thunk, but still VIA parallel(): if THIS pass throws, we want a clean `null`
    // rather than a crash that would lose the whole dispatch already completed -- the tool's own
    // contract turns a throw into `null` ONLY through parallel(), never through a bare agent() call.
    const [coherence] = await parallel([
      () => agent(promptCoherence, { label: TITRE_COHERENCE, phase: TITRE_COHERENCE, schema: SCHEMA_COHERENCE }),
    ]);
    if (coherence === null) {
      log("Coherence pass FAILED -- gaps NOT MEASURED, distinct from an empty list.");
      ecarts = null;
    } else {
      ecarts = coherence.ecarts;
      log(`${ecarts.length} coherence gap(s) published -- not fixed.`);
    }
  } else {
    log("No usable result -- coherence pass skipped (nothing to compare).");
    ecarts = null;
  }

  sortie = {
    unites_totales: unites.length,
    unites_traitees: resultats.filter((r) => r.ok).length,
    unites_en_echec: echecs,
    lots: lots.length,
    maxParallel,
    ecarts, // null = not measured (failure or nothing to compare); [] = measured, zero gaps -- NEVER conflated
  };
}

return sortie;
