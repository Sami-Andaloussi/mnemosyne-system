# system/golden/ - the quality-calibration golden set

**Reference samples validated by a human**, against which `make calibrate` measures the real
building blocks' output: fact extraction, reading fidelity (OCR), RAG recall. Moved here from
`knowledge/golden/` during a library reorganization.

## Contents
- A local spot-check file may hold representative proposed corrections for human re-review
  (producer != verifier): correct? complete?
- `extraction.json` - fact-from-text cases (an expected subject/relation/object triplet).
- `fidelity.json` - text-fidelity-from-source cases (excerpts + expected text).
- `retrieval.json` - query/relevant-passages cases for calibrating the recall floor.

## Convention
Contains **verbatim excerpts from copyrighted books** -> excluded from git tracking.

## See also
[`Makefile`](../../Makefile) (`make calibrate`) . [Root README](../../README.md)
