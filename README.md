# Batch Script Generator

An interactive command-line tool that generates long-form YouTube scripts in
bulk using the **Anthropic Messages Batches API** (50% cost savings) and
**prompt caching** (further savings across reused SOP content).

You enter one or more titles with target word counts, pick a profile, and the
tool writes finished `.txt` scripts to a folder on your computer.

---

## 1. First-time setup on a brand-new computer

If this is a fresh machine with nothing installed, follow these steps in order.
If you already have Python and Git, skip to [section 2](#2-install).

### 1.1 Install Python 3.10 or newer

**Windows**
1. Go to <https://www.python.org/downloads/windows/> and download the latest
   **Windows installer (64-bit)**.
2. Run the installer. On the very first screen, **tick the box "Add python.exe
   to PATH"** (bottom of the window). This is the single most important step —
   without it, `python` will not work from the terminal.
3. Click **Install Now** and wait for it to finish.
4. Open a **new** PowerShell or Command Prompt window (existing windows won't
   see the new PATH) and run:
   ```powershell
   python --version
   ```
   You should see something like `Python 3.12.5`.

**macOS**
1. Install Homebrew if you don't have it: paste the command from <https://brew.sh/>
   into Terminal.
2. `brew install python`
3. Verify: `python3 --version`

**Linux (Debian / Ubuntu)**
```bash
sudo apt update
sudo apt install python3 python3-pip git
```

### 1.2 Install Git

- **Windows**: download from <https://git-scm.com/downloads> and run the
  installer. Accept the defaults on every screen.
- **macOS**: `brew install git` (or it prompts you the first time you run `git`).
- **Linux**: included in the `apt install` above.

Verify in a new terminal:
```bash
git --version
```

### 1.3 Get an Anthropic API key

1. Sign up or log in at <https://console.anthropic.com/>.
2. Add a payment method (Batches API usage is pay-as-you-go).
3. Go to **Settings → API Keys → Create Key**, copy the `sk-ant-...` value,
   and keep it somewhere safe. You'll paste it into `config.json` in step 2.3.

### 1.4 Pick a folder for the project

Choose where the tool should live on disk, e.g. `C:\Users\<you>\Documents\script-cli`
or `~/projects/script-cli`. Open a terminal **in that parent folder** before
continuing to section 2.

---

## 2. Install

> **Windows shortcut:** if you just want the fastest path, skip the rest of
> section 2 and jump to [section 2.4 (run.bat)](#24-windows-one-click-runbat) —
> it automates the virtual-env, dependency install, and `config.json` creation
> for you.

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

### 2.4 Windows one-click: `run.bat`

The repo ships with `run.bat`, a launcher that bundles steps 2.2, 2.3 and
section 3 into a single double-click. On a fresh Windows machine, once Python
and Git are installed and the repo is cloned (steps 1.1, 1.2, 2.1), you can
skip the manual `pip` and `copy` commands and just use the batch file.

**What it does, in order:**

1. `cd`s into its own folder, so you can double-click it from Explorer.
2. Checks that `python` is on PATH. If not, it prints the install link and the
   "Add Python to PATH" reminder and stops.
3. **First run only** — creates a local virtual environment in `.venv\`,
   upgrades `pip`, and runs `pip install -r requirements.txt` inside it. This
   keeps the tool's dependencies isolated from the rest of your system.
4. **Every subsequent run** — activates the existing `.venv\` instead of
   reinstalling anything.
5. If `config.json` doesn't exist yet, it copies `config.example.json` into
   place, opens the new file in Notepad so you can paste your Anthropic API
   key, then exits. Save the file and re-run `run.bat`.
6. Once the config is in place, it runs `python generate.py` — the same entry
   point described in section 3 — and pauses the window at the end so any
   error output stays readable.

**How to use it:**

- Double-click `run.bat` in File Explorer, **or**
- From a terminal inside the repo folder: `run.bat`

Use `run.bat` every time you want to generate scripts — it's the intended
day-to-day entry point on Windows. The plain `python generate.py` flow still
works for users on macOS/Linux or anyone who prefers to manage their own
virtual environment.

---

## 3. Use

From inside the repo folder run:

```bash
python generate.py
```

You will be asked two things:

1. **Working folder** — the folder that holds your `titles.txt` file. Finished
   scripts are saved into sub-folders here (one per video ID). Press ENTER
   to accept the default from `config.json`.
2. **Profile** — a numbered list of all folders under `profiles/` is shown. Each
   profile bundles the prompts, token limits and SOP for one writing style
   (e.g. `sleep-history`). Type the number and press ENTER.

### The titles.txt file

Create a file called `titles.txt` inside your working folder, with one video
per line in the form:

```
<VIDEO_ID> <TITLE> - <WORD_COUNT>
```

Example:

```
MD0001 Life of pirates - 18000
MD0002 Viking Women Warriors Who Led Raids Across Europe - 16000
MD0003 The Forgotten Women Who Disguised Themselves as Sailors - 20000
```

- `VIDEO_ID` — first token on the line. Letters, digits, `_` and `-` only.
  This ID becomes the folder name **and** the output filename
  (`MD0001/MD0001.txt`).
- `TITLE` — everything between the ID and the last ` - `.
- `WORD_COUNT` — integer after the last ` - `.
- Blank lines and lines starting with `#` are ignored.

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
├── titles.txt
├── MD0001/
│   ├── outline.json
│   └── MD0001.txt          <-- final narration text
└── MD0002/
    ├── outline.json
    └── MD0002.txt
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
