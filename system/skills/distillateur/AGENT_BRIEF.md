# BRIEF - distilling a SLICE of a book (AGENT lane, D145)

> **This file is the brief handed AS IS to each Haiku agent** of the distillateur's agent lane.
> `make distill-emit-split` prints its path in its plan. It lives HERE (versioned), never in a
> scratchpad: a recipe you want to replay must not die with the session.
>
> **The agent's prompt fits in 5 lines** - it points at this brief and gives the 3 variables:
> ```
> First read your full brief and apply it to the letter: system/skills/distillateur/AGENT_BRIEF.md
> Book: "<title>" (<author>) - <N> sections in total. <nature hint: technical manual / end of the book...>
> EMISSION: <folder of the sec_*.md>
> OUTPUT  : <folder where the section_*.json go>
> YOUR SECTIONS: 1, 2, 3, 4, 5
> ```
> **Model: HAIKU, always, never Sonnet** (the operator's immutable rule).

---

You distill a SLICE of a PUBLIC book. You do NOTHING but fill in JSON forms: the splitting, the
verification and the assembly are done by CODE, not by you.

Your prompt gives you three variables: the EMISSION folder, the OUTPUT folder, and YOUR SECTIONS.

For EACH section `i` on your list, in order:

1. **Read** `<EMISSION>/sec_<i on 3 digits>.md` (e.g. `sec_007.md`). These files are 150-950 lines:
   ONE single Read is enough, read it in full.
   It contains the JSON SCHEMA at the top, then the `PROMPT SECTION i/N` with the source text between
   `--- SOURCE START ---` and `--- SOURCE END ---`.
2. **Answer the prompt**: produce ONE JSON object conforming to the schema
   (`title`, `summary`, `tags`, `description`, `concepts`, `passages`).
3. **Write** that JSON - and NOTHING else: no markdown, no ```json, just the object - into
   `<OUTPUT>/section_<i on 3 digits>.json` (e.g. `section_007.json`).

## HARD RULE on `passages` - this is what matters most

- A passage = an extract **COPIED AND PASTED WORD FOR WORD** from the source text you have just read
  (between SOURCE START and SOURCE END).
- Copy from the displayed text. NEVER retype from memory. Correct NEITHER the spelling, NOR the punctuation,
  NOR the capitals, NOR the apostrophes (’ versus '), NOR the dashes, NOR the markdown formatting (**bold**).
  The slightest changed character = passage THROWN AWAY. An OCRed book contains damaged characters (`e¤ect`,
  `di‰cult`): **keep them as they are**, "correcting" them gets the quotation thrown away.
- **ESCAPE the quotation marks**: a `"` inside a JSON string MUST be written `\"`. Quotations from a
  book often contain them - this is the #1 cause of a broken file. The text stays literal, only the
  JSON escaping is added. **But do NOT escape the quotation mark that CLOSES the string** (over-escaping breaks it
  just as much as under-escaping).
- Each passage = ONE **CONTIGUOUS** span (one to three sentences that really follow one another in the text).
  NEVER two pieces glued back together, NEVER a "..." in the middle, NEVER an internal cut.
- Choose ~10 load-bearing passages (definitions, central claims, key figures), spread over the WHOLE
  section, 500 characters maximum each.
- If your section is an appendix, a bibliography, an index or a data table: honestly distill what
  is in it (tables have titles and quotable figures) - do not invent prose that is absent.
- CODE re-tests each quotation against the source and THROWS AWAY every non-literal quotation. Bluffing does not
  help: it just impoverishes the record. **Better 6 exact quotations than 10 approximate ones.**

## The other fields

`title` / `summary` / `tags` / `description` / `concepts` are on the contrary to be **WRITTEN in your own words**:
a neutral and objective synthesis, attributed to the authors ("the authors argue that...", "the book presents...").
Keep the language of the prompt (English). Respect the schema's limits: summary 600 characters,
description 1800, 8 tags maximum, 12 concepts maximum.

## FRAME

- Write ONLY in YOUR OUTPUT folder. Touch NO other file in the repository. Do not explore the repository, do
  not run any command, do not read anything other than YOUR `sec_*.md` files.
- Do NOT skip ANY section: all your JSON files must exist at the end.
- NO quality report and no self-evaluation (code verifies, not you). Just answer with the list of
  files written and, for each one, the number of passages.
