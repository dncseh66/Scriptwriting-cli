#!/usr/bin/env python3
"""Batch script generator.

Reads titles from a titles.txt file in the working folder, then generates
all scripts in parallel using the Anthropic Messages Batches API
(50% cost savings). Uses prompt caching on the SOP.

titles.txt format — one line per video:
    MD0001 Life of pirates - 18000
    MD0002 Viking women warriors - 16000

Where:
    - First whitespace-separated token is the Video ID (used as folder
      name AND output filename, e.g. MD0001/MD0001.txt).
    - Everything up to the last " - " is the title.
    - The number after " - " is the target word count.
"""
import json
import re
import sys
from pathlib import Path

from batch_client import BatchClient
from utils import (
    count_words, tail_words,
    read_text, write_text, append_text, section_type,
)

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.json"
PROFILES_DIR = ROOT / "profiles"
TITLES_FILENAME = "titles.txt"


def load_config():
    if not CONFIG_PATH.exists():
        print("ERROR: config.json not found. Copy config.example.json to config.json and fill in your API key.")
        sys.exit(1)
    cfg = json.loads(read_text(CONFIG_PATH))
    if not cfg.get("api_key") or "REPLACE" in cfg["api_key"] or "PASTE" in cfg["api_key"]:
        print("ERROR: set your API key in config.json")
        sys.exit(1)
    return cfg


def list_profiles():
    if not PROFILES_DIR.exists():
        print("ERROR: profiles/ folder not found")
        sys.exit(1)
    return sorted([p.name for p in PROFILES_DIR.iterdir() if p.is_dir() and (p / "profile.json").exists()])


def prompt_working_folder(default):
    raw = input(f"Working folder (must contain {TITLES_FILENAME}) [{default}]: ").strip()
    folder = Path(raw or default).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def prompt_profile():
    profiles = list_profiles()
    if not profiles:
        print("ERROR: no profiles found in profiles/")
        sys.exit(1)
    print("\nAvailable profiles:")
    for i, name in enumerate(profiles, 1):
        print(f"  {i}. {name}")
    while True:
        choice = input(f"Choose profile [1-{len(profiles)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(profiles):
            return profiles[int(choice) - 1]
        print("Invalid choice.")


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_titles_line(line: str):
    """Parse one line of titles.txt. Returns (video_id, title, word_count) or None."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Split into video ID and the rest
    parts = line.split(None, 1)
    if len(parts) != 2:
        raise ValueError(f"expected '<ID> <title> - <word_count>', got: {line!r}")
    video_id, rest = parts[0], parts[1]

    if not VIDEO_ID_RE.match(video_id):
        raise ValueError(f"video ID {video_id!r} must be letters/digits/_/- only")

    # Split off the word count from the end on the last ' - '
    if " - " not in rest:
        raise ValueError(f"missing ' - <word_count>' in: {line!r}")
    title_str, _, wc_str = rest.rpartition(" - ")
    title_str = title_str.strip()
    try:
        wc = int(wc_str.strip())
    except ValueError:
        raise ValueError(f"word count must be a number, got {wc_str!r}")
    if not title_str:
        raise ValueError(f"empty title in: {line!r}")

    return (video_id, title_str, wc)


def load_titles_file(working_folder: Path):
    path = working_folder / TITLES_FILENAME
    if not path.exists():
        print(f"ERROR: {path} not found.")
        print(f"Create {TITLES_FILENAME} in the working folder with lines like:")
        print(f"    MD0001 Life of pirates - 18000")
        sys.exit(1)

    titles = []
    seen_ids = set()
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            parsed = parse_titles_line(raw)
        except ValueError as e:
            print(f"ERROR on line {i} of {TITLES_FILENAME}: {e}")
            sys.exit(1)
        if parsed is None:
            continue
        vid, _, _ = parsed
        if vid in seen_ids:
            print(f"ERROR on line {i}: duplicate video ID {vid!r}")
            sys.exit(1)
        seen_ids.add(vid)
        titles.append(parsed)

    if not titles:
        print(f"ERROR: {path} has no valid title lines.")
        sys.exit(1)
    return titles


def build_system_blocks(profile, sop_text, kind):
    if kind == "outline":
        return profile["outline_system_prompt"]

    sys_text = profile["section_system_prompt"]
    blocks = [{"type": "text", "text": sys_text}]
    if sop_text:
        blocks.append({
            "type": "text",
            "text": f"=== SOP ===\n{sop_text}",
            "cache_control": {"type": "ephemeral"},
        })
    return blocks


def generate_outlines(bc: BatchClient, profile, titles, output_dirs):
    requests = []
    for idx, ((vid, title, wc), out_dir) in enumerate(zip(titles, output_dirs)):
        user_prompt = profile["outline_user_prompt_template"].format(
            title=title, target_words=wc,
        )
        requests.append(bc.build_request(
            custom_id=f"outline-{idx}",
            system=build_system_blocks(profile, "", "outline"),
            user_prompt=user_prompt,
            max_tokens=profile.get("outline_max_tokens", 32000),
        ))

    results = bc.submit_and_wait(requests, label="outlines")

    outlines = {}
    for idx, ((vid, title, wc), out_dir) in enumerate(zip(titles, output_dirs)):
        cid = f"outline-{idx}"
        if cid not in results:
            print(f"  SKIP: outline failed for {vid} '{title}'")
            continue
        raw = results[cid].strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  ERROR: outline JSON parse failed for {vid} '{title}': {e}")
            (out_dir / "outline_raw.txt").write_text(raw, encoding="utf-8")
            continue
        write_text(out_dir / "outline.json", json.dumps(data, indent=2, ensure_ascii=False))
        outlines[vid] = data
        print(f"  [{vid}] outline: {len(data.get('sections', []))} sections")
    return outlines


def generate_sections(bc: BatchClient, profile, sop_text, titles, output_dirs, outlines):
    section_rules = profile.get("section_type_rules", {"default": "body"})
    max_tokens_map = profile.get("section_max_tokens", {"body": 6000})
    context_window = profile.get("context_window_words", 1500)

    active = []
    for idx, ((vid, title, wc), out_dir) in enumerate(zip(titles, output_dirs)):
        if vid not in outlines:
            continue
        sections = outlines[vid].get("sections", [])
        script_path = out_dir / f"{vid}.txt"
        script_path.write_text("", encoding="utf-8")
        active.append({
            "idx": idx, "vid": vid,
            "title": title, "wc": wc, "dir": out_dir,
            "sections": sections, "script_path": script_path,
        })

    if not active:
        return

    max_len = max(len(a["sections"]) for a in active)

    for slot in range(max_len):
        requests = []
        slot_jobs = []
        for a in active:
            if slot >= len(a["sections"]):
                continue
            sec = a["sections"][slot]
            is_last = (slot == len(a["sections"]) - 1)
            stype = section_type(sec["id"], is_last, section_rules)
            max_tokens = max_tokens_map.get(stype, max_tokens_map.get("body", 6000))

            prev_tail = tail_words(a["script_path"].read_text(encoding="utf-8"), context_window)

            user_prompt = profile["section_user_prompt_template"].format(
                sop_text=sop_text,
                outline_json=json.dumps(outlines[a["vid"]], ensure_ascii=False),
                previous_script_tail=prev_tail,
                context_window_words=context_window,
                section_id=sec["id"],
                section_title=sec.get("title", ""),
                section_word_target=sec.get("word_target", ""),
            )

            cid = f"sec-{a['idx']}-{slot}"
            requests.append(bc.build_request(
                custom_id=cid,
                system=build_system_blocks(profile, sop_text, "section"),
                user_prompt=user_prompt,
                max_tokens=max_tokens,
            ))
            slot_jobs.append((cid, a, sec))

        if not requests:
            continue
        print(f"\n=== Slot {slot+1}/{max_len} — {len(requests)} section(s) ===")
        results = bc.submit_and_wait(requests, label=f"slot {slot+1}")

        for cid, a, sec in slot_jobs:
            if cid not in results:
                print(f"  SKIP: {a['vid']} section {sec['id']} failed")
                continue
            text = results[cid].rstrip() + "\n\n"
            append_text(a["script_path"], text)
            total = count_words(a["script_path"].read_text(encoding="utf-8"))
            added = count_words(text)
            print(f"  [{a['vid']}] section {sec['id']}: +{added} words (total {total}/{a['wc']})")


def main():
    print("=== Batch Script Generator ===\n")
    cfg = load_config()
    working_folder = prompt_working_folder(cfg.get("default_working_folder", "./outputs"))
    titles = load_titles_file(working_folder)
    profile_name = prompt_profile()

    profile_dir = PROFILES_DIR / profile_name
    profile = json.loads(read_text(profile_dir / "profile.json"))
    sop_path = profile_dir / "sop.txt"
    sop_text = read_text(sop_path) if sop_path.exists() else ""

    model = profile.get("model", cfg.get("model", "claude-opus-4-7"))
    poll_interval = cfg.get("poll_interval_seconds", 30)

    print("\n=== Summary ===")
    print(f"Profile:        {profile_name}")
    print(f"Model:          {model}")
    print(f"Working folder: {working_folder}")
    print(f"Titles file:    {working_folder / TITLES_FILENAME}")
    print(f"Titles:         {len(titles)}")
    for vid, t, wc in titles:
        print(f"   - [{vid}] {t} ({wc} words)")
    confirm = input("\nStart generation? [Y/n]: ").strip().lower()
    if confirm and confirm != "y":
        print("Cancelled.")
        return

    output_dirs = []
    for vid, _title, _wc in titles:
        folder = working_folder / vid
        folder.mkdir(parents=True, exist_ok=True)
        output_dirs.append(folder)

    bc = BatchClient(api_key=cfg["api_key"], model=model, poll_interval=poll_interval)

    print("\n=== Phase 1: Outlines ===")
    outlines = generate_outlines(bc, profile, titles, output_dirs)
    if not outlines:
        print("No outlines succeeded. Aborting.")
        return

    print("\n=== Phase 2: Sections (batched across titles, slot by slot) ===")
    generate_sections(bc, profile, sop_text, titles, output_dirs, outlines)

    print("\n=== Done ===")
    for (vid, title, wc), out_dir in zip(titles, output_dirs):
        script_path = out_dir / f"{vid}.txt"
        if script_path.exists():
            words = count_words(script_path.read_text(encoding="utf-8"))
            print(f"  [{vid}] {title}: {words} words -> {script_path}")
        else:
            print(f"  [{vid}] {title}: FAILED (no script written)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
