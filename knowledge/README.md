# knowledge/ - your library

Empty on purpose: this is a template, not a bundled library. Put your own documents here and the
pipeline in `system/lib/mnemosyne/ingest` and `system/skills/distillateur` will work on them exactly
as described in [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

- `raw/<domain>/` - your source documents (PDFs, EPUBs, transcripts, converted to `.md`). Declare a
  domain first with `make domain-new`.
- `distilled/<domain>/` - the distilled notes `make distill` produces from `raw/`, mirroring its
  structure.

Both subtrees are gitignored beyond their `.gitkeep` - your library is yours, not part of this
repo's history.
