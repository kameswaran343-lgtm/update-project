# KuralGuard

KuralGuard checks Tamil quotations against installed local literary corpora.
Exact corpus matches can be confirmed; near matches show the corresponding
source text for review; a missing match is **not** a claim that a quote is fake.
`/literature/verify` is deterministic and uses no LLM or network lookup.
The web interface can also extract Tamil text from PNG, JPEG, or WebP
screenshots and check it through the same verifier. OCR runs in the browser;
the screenshot is not uploaded. Extracted text is only a draft: review and
correct it before submitting it to the verifier. The OCR engine and Tamil
language data are downloaded when image checking is first used.

The quotation input also offers opt-in Tamil voice transcription using the
browser's Web Speech API with the `ta-IN` language tag. Browser support and
Tamil availability vary; this currently depends on a compatible Chromium-based
browser and its configured speech service. It requires microphone permission,
a secure context (HTTPS or localhost), and typically an internet connection.
The app does not record or store audio, but the browser or its speech-service
provider may process it under their own privacy policy. Recording starts only
when you press **Speak** and continues until you press **Stop**. The transcript
is copied into the editable quote field only after you stop; it is not checked
until you separately submit it. English speech and meaning-based search are
not supported.

## Education and simple explanations

The Education tab browses the local corpus by Paal, Athigaram, and Kural
number. It shows the original Tamil couplet and the available source English
meaning without replacing either with generated text. Meanings flagged for
human review are identified as unverified, omitted from the verified-meaning
display, and not sent to the explanation model as verified context.

Simple explanations are generated only when the user selects a Kural and
clicks **Explain in Simple Terms**. The backend uses Gemini's `generateContent`
API and caches successful results in memory (up to 256 Kural/language
combinations per server process). Configure the model in the server's local
`.env` or deployment environment. For a hosted deployment, add
`GEMINI_API_KEY` as a server-side secret:

```dotenv
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_API_TIMEOUT_SECONDS=45
```

For Replit, add the key in the deployment's Secrets (or environment variables)
so the API service can read it at runtime. Keep the key server-side; never put
it in frontend code or commit it. Without a key, browsing remains available
and the explanation endpoint returns a clear configuration error. The selected
verse and any eligible source meaning are sent to Gemini when an explanation is
explicitly requested. Generated explanations are educational aids, not
verified translations or replacements for the source text.

The home-page ticker uses all 1,330 couplets from the local corpus. Its
Thiruvalluvar statue photograph is by PKharote, shared under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) via
[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Indian_Temple_at_dusk_Thiruvalluvar_Statue.jpg).

## Run it

The single-stack command builds/checks the corpus, creates the deterministic
evaluation report, then starts the FastAPI server and React/Vite interface:

```bash
python3.11 -m pip install -r requirements.txt
pnpm install
chmod +x run.sh
./run.sh
```

In VS Code on Windows, run `pnpm dev` from the project root instead. This starts
the FastAPI memory/API backend, waits until its memory quiz routes are ready,
and then starts the web interface. Set `PYTHON` to the Python executable for
your virtual environment if it is not already active in the terminal. Stop
both services with Ctrl+C.

The development services are available at:

- Web interface: `http://127.0.0.1:5173/`
- API health: `http://127.0.0.1:8000/api/health` (the API also accepts `/health`)
- FastAPI docs: `http://127.0.0.1:8000/docs`

In Replit, the managed preview runs the web artifact at `/` and routes the API
artifact at `/api`.

Individual steps:

```bash
python3.11 scripts/build_corpus.py
python3.11 eval/run_eval.py
python3.11 -m pytest -q
pnpm run typecheck
```

The React + Vite source is in the registered app at
`artifacts/meikural/`. The root `config.py` reads `.env` when present. Copy
`.env.example` to `.env` only when you need to override public source URLs,
thresholds, paths, or CORS settings. There are no API keys in the project.

## Corpus sources and handling

The Thirukkural corpus builder inspects and fetches source A's actual JSON layout:

- [tk120404/thirukkural](https://github.com/tk120404/thirukkural) —
  `thirukkural.json` supplies couplet text and English translation;
  `detail.json` supplies paal and chapter metadata. The repository declares
  Apache-2.0.
- [api-thirukkural.vercel.app](https://api-thirukkural.vercel.app/) — the
  configured primary API source uses its documented `?num={id}` endpoint. It
  returned HTTP 402 during this build, so the script falls back to a second,
  independent API:
  [Senkanthal's Thirukkural API](https://github.com/senkanthal/thirukkural-api),
  `GET /kural`, documented at
  [thirukkural.senkanthal.org/openapi.json](https://thirukkural.senkanthal.org/openapi.json).
  Senkanthal's repository declares MIT and states its data is free to use.

The exact downloaded bytes are preserved under `data/raw/` and are never
rewritten by the builder. Raw snapshots are excluded from Git/deployment;
`data/clean/kural.json` is the normalized runtime corpus. The builder compares
each source's Tamil lines. With two sources, any disagreement is a tie: source
A is retained and `needs_human_review` is set. Every disagreement is written
to `data/clean/mismatches.csv`. The builder fails rather than emitting a partial
corpus if it cannot obtain two complete sources or if the 1,330/133-by-10
integrity checks fail.

The multi-literature verifier currently has local text for:

- Thirukkural — 1,330 couplets, built as described above.
- Aathichudi (ஆத்திசூடி) — 109 entries from
  [tamizhilakkiyam/aathichudi](https://github.com/tamizhilakkiyam/aathichudi),
  pinned to commit `77896642fae2d72d46ddee6c339f2b0ae25c48fe` and retained
  under its MIT license in `data/licenses/AATHICHUDI-LICENSE`. The normalized
  data is in `data/clean/aathichudi.json`; regenerate it with
  `python scripts/import_aathichudi.py`.
- Purananuru (புறநானூறு) — 385 transcribed poems from
  [Tamil Wikisource](https://ta.wikisource.org/wiki/புறநானூறு), distributed
  under CC BY-SA 4.0 with attribution and revision URLs preserved in each
  record. License and source notes are in
  `data/licenses/PURANANURU-LICENSE`; regenerate the data with
  `python scripts/import_purananuru.py`.

The current Wikisource transcription omits poems 151–160 (the page for that
range duplicates poems 161–170), 267–268, 320, and 362. Poem 244 has only an
editorial note stating that its text is damaged. These poems are excluded
rather than inferred or filled with OCR. The supplied
[CICT scan](https://library.cict.in/api/storage/ebooks/PURA-CICT__1_.pdf) is
retained as edition-reference metadata, but its image-only pages were not
transcribed because OCR did not reliably separate poem text from commentary.
Purananuru matches are therefore limited to the 385 bundled records; a
`not_found` result cannot establish that a quote is absent from the complete
work.

Tolkappiyam (தொல்காப்பியம்) remains an unavailable choice until a complete
corpus with suitable reuse permissions is identified. The app does not
fabricate or silently substitute its text. The backend catalog reports its
unavailable status, and an explicit request to verify against it returns an
error.

## Matching and threshold

Normalization applies Unicode NFC, removes U+200B/U+200C/U+200D, strips
punctuation and digits, retains Tamil letters and combining marks, and folds
whitespace. Exact comparison ignores spaces. The engine indexes full
couplets and each line separately.

For non-exact candidates, the score combines RapidFuzz character-level ratio
(70%) and Dice word-overlap (30%). `NEAR_THRESHOLD` defaults to 80, as requested.
The seed-42 synthetic evaluation at 80 reports 100% recall on its 100 real
examples, 100% near-match detection on its 20 one-word substitutions, 0%
fake-to-verified false accepts, and 98% abstention on its 50 generated fakes.
The threshold sweep showed 85 also kept full recall on this generated set while
abstaining on all 50 fakes; the default remains 80 rather than overfitting a
small synthetic set. These are not scholarly validation results.

`eval/eval_set.json` and `eval/results.json` are generated from the fetched
corpus with a deterministic random seed of 42. The set contains 50 exact or
formatting-variant real quotes, 30 one-character typos, 20 one-word
substitutions, 30 line splices (split between same- and cross-chapter), and 20
word shuffles. If `eval/manual_fakes.json` exists, its entries are added.

## API

The registered API service is mounted at `/api` in Replit. The FastAPI app also
accepts the same routes without that prefix for direct local use:

- `GET /health` and `GET /healthz`
- `GET /kural/{id}`
- `POST /verify` with `{ "text": "...", "claimed_id": 123 }`
- `GET /literature/catalog` — list corpus availability and entry counts
- `POST /literature/verify` with
  `{ "text": "...", "work_id": "all" }`; `work_id` may also select an
  available literary corpus such as `thirukkural` or `aathichudi`
- `POST /guard` with `{ "llm_answer": "..." }`
- `GET /eval/results`

Guard extracts text inside common quotation marks and standalone lines with at
least four Tamil words, associates nearby Kural citations, and sends every
candidate to the same local matcher. Not-found annotations use the required
scholar-consultation abstention statement. The current MVP accepts pasted
answers from any chatbot; optional LLM answer generation is not enabled.

## Limitations

- Editions, orthography, spacing, punctuation, and editorial variants can
  differ. Source conflicts are flagged, not silently adjudicated.
- Only installed corpora can be checked. The verifier has Thirukkural,
  Aathichudi, and a partial Purananuru transcription; Tolkappiyam is not yet
  searchable.
- Purananuru verification covers 385 transcribed poems. Poems 151–160, 244,
  267–268, 320, and 362 are absent from the usable source text and cannot be
  verified.
- English translations are displayed as reference metadata; the matcher
  deliberately checks Tamil letters only.
- Near-match thresholds and generated fakes are evaluation aids, not proof of
  authenticity. A Tamil scholar remains the authority for uncertain passages.
- `not_found` means only “not in this local corpus; cannot confirm.” It must
  never be presented as “fake.”
