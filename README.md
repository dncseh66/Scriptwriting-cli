# Batch Script Generator

An interactive command-line tool that generates long-form YouTube scripts in
bulk using the **Anthropic Messages Batches API** (50% cost savings) and
**prompt caching** (further savings across reused SOP content).

You enter one or more titles with target word counts, pick a profile, and the
tool writes finished `.txt` scripts to a folder on your computer.

---

## 1. Requirements

- **Python 3.10 or newer** — check with `python --version` (or `python3 --version`).
  - Windows: install from <https://www.python.org/downloads/> and tick "Add Python to PATH".
  - macOS: `brew install python` or install from python.org.
  - Linux: usually preinstalled, otherwise `sudo apt install python3 python3-pip`.
- **Git** (only needed to clone the repo): <https://git-scm.com/downloads>
- An **Anthropic API key** from <https://console.anthropic.com/>.

---

## 2. Install

### 2.1 Clone the repo

```bash
git clone https://github.com/dncseh66/Scriptwriting-cli.git
cd Scriptwriting-cli
```

If you don't have Git, you can instead click **Code → Download ZIP** on the
GitHub page, unzip it, and open a terminal inside the unzipped folder.

### 2.2 Install the Python dependency

```bash
pip install -r requirements.txt
```

On some systems you may need `pip3` instead of `pip`.

### 2.3 Create your config file

Copy the example:

```bash
# Windows
copy config.example.json config.json

# macOS / Linux
cp config.example.json config.json
```

Then open `config.json` in any text editor and replace `sk-ant-REPLACE-WITH-YOUR-KEY`
with your real Anthropic API key.

```json
{
  "api_key": "sk-ant-...your key here...",
  "model": "claude-opus-4-7",
  "default_working_folder": "./outputs",
  "poll_interval_seconds": 30
}
```

- `model` — `claude-opus-4-7` (highest quality, default) or `claude-sonnet-4-6` (cheaper/faster).
- `default_working_folder` — the folder suggested as default at runtime.
- `poll_interval_seconds` — how often the tool checks on a running batch.

Your `config.json` is in `.gitignore` and will never be pushed to GitHub.

---

## 3. Use

From inside the repo folder run:

```bash
python generate.py
```

You will be asked three things:

1. **Working folder** — where the finished scripts will be saved. One sub-folder
   per title is created automatically. Press ENTER to accept the default from
   `config.json`.
2. **Profile** — a numbered list of all folders under `profiles/` is shown. Each
   profile bundles the prompts, token limits and SOP for one writing style
   (e.g. `sleep-history`). Type the number and press ENTER.
3. **Titles** — enter one per line in the form:
   ```
   TITLE | WORD_COUNT
   ```
   Example:
   ```
   The Forgotten Women Who Disguised Themselves as Sailors | 18000
   Viking Women Warriors Who Led Raids Across Europe | 16000
   ```
   Press ENTER on an **empty line** when you are done.

The tool shows a summary and asks for confirmation. Type `y` (or just ENTER)
to start.

### What happens next

- **Phase 1 — outlines.** All outlines are submitted as a single batch. The
  tool prints a status line roughly every 30 seconds until the batch ends.
- **Phase 2 — sections.** For each section slot (1, 2, 3, …) the tool submits
  one batch containing the same section for every title. Each section is
  appended to the right `script.txt` as soon as it arrives.

Batches usually finish within a few minutes, but Anthropic guarantees up to
24 hours. You can close your terminal only after the tool prints **=== Done ===**.

### Output layout

```
<working folder>/
├── The Forgotten Women Who Disguised Themselves as Sailors/
│   ├── outline.json
│   └── script.txt          <-- final narration text
└── Viking Women Warriors Who Led Raids Across Europe/
    ├── outline.json
    └── script.txt
```

---

## 4. Adding your own writing style (profiles)

Create a new folder under `profiles/`, for example `profiles/my-style/`, and
put two files inside it:

- **`profile.json`** — prompts, temperatures, token limits, and section type
  rules. Copy `profiles/sleep-history/profile.json` as a starting point.
- **`sop.txt`** — free-form style guide / SOP. The tool reads it as text and
  passes it to Claude verbatim.

No code changes required — the new profile shows up in the picker on next run.

---

## 5. Costs

- **Anthropic Batches API**: 50% off standard pricing.
- **Prompt caching** on the SOP: up to 90% off the cached prefix on subsequent
  reads (one-time 1.25× premium on the first write).

As a rough guide, a 20K-word Opus 4.7 script is in the few-dollar range with
batch + caching. Check the Anthropic console for the exact bill.

---

## 6. Troubleshooting

- **`ERROR: config.json not found`** — you skipped step 2.3.
- **`ERROR: set your API key in config.json`** — the placeholder is still in
  the file; paste your real key.
- **`outline JSON parse failed`** — the model returned malformed JSON. The raw
  text is written to `outline_raw.txt` inside that title's folder so you can
  inspect it. Re-run the title.
- **Batch gets stuck in `in_progress` for a long time** — that is normal under
  load; Anthropic guarantees delivery within 24h and usually finishes much
  faster. Leave it running.
- **Rate limit errors** — the Batches API has high limits, but if you hit one,
  run fewer titles per batch.

---

## 7. Updating

```bash
git pull
pip install -r requirements.txt   # only if requirements changed
```

Your `config.json` and `outputs/` folder are untouched by updates.
