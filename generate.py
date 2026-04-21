#!/usr/bin/env python3
"""Interactive batch script generator.

Collects multiple titles, then generates all scripts in parallel using the
Anthropic Messages Batches API (50% cost savings). Uses prompt caching on
the SOP for additional savings across many section calls.
"""
import json
import sys
from pathlib import Path

from batch_client import BatchClient
from utils import (
    count_words, sanitize_folder_name, tail_words,
    read_text, write_text, append_text, section_type,
)

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.json"
PROFILES_DIR = ROOT / "profiles"


def load_config():
    if not CONFIG_PATH.exists():
        print(f"ERROR: config.json not found. Copy config.example.json to config.json and fill in your API key.")
        sys.exit(1)
    cfg = json.loads(read_text(CONFIG_PATH))
    if not cfg.get("api_key") or "REPLACE" in cfg["api_key"]:
        print("ERROR: set your API key in config.json")
        sys.exit(1)
    return cfg


def list_profiles():
    if not PROFILES_DIR.exists():
        print("ERROR: profiles/ folder not found")
        sys.exit(1)
    return sorted([p.name for p in PROFILES_DIR.iterdir() if p.is_dir() and (p / "profile.json").exists()])


def prompt_working_folder(default):
    raw = input(f"Working folder where scripts will be saved [{default}]: ").strip()
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


def prompt_titles():
    print("\nEnter titles one per line as: TITLE | WORD_COUNT")
    print("Example: The Forgotten Women Who Disguised Themselves as Sailors | 18000")
    print("Press ENTER on an empty line when done.\n")
    titles = []
    while True:
        line = input(f"Title {len(titles)+1}: ").strip()
        if not line:
            if not titles:
                print("Enter at least one title.")
                continue
            return titles
        if "|" not in line:
            print("Format: TITLE | WORD_COUNT")
            continue
        title_str, _, wc_str = line.rpartition("|")
        title_str = title_str.strip()
        try:
            wc = int(wc_str.strip())
        except ValueError:
            print("Word count must be a number.")
            continue
        if not title_str:
            print("Title cannot be empty.")
            continue
        titles.append((title_str, wc))


def build_system_blocks(profile, sop_text, kind):
    """Build system blocks with prompt caching on the SOP prefix.

    For sections, the SOP is included in the system prompt and cached; the
    volatile parts (outline, previous_script_tail, section target) go in the
    user message. For outlines there is no SOP reuse benefit, so plain string.
    """
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
    for (title, wc), out_dir in zip(titles, output_dirs):
        user_prompt = profile["outline_user_prompt_template"].format(
            title=title, target_words=wc,
        )
        requests.append(bc.build_request(
            custom_id=f"outline__{out_dir.name}",
            system=build_system_blocks(profile, "", "outline"),
            user_prompt=user_prompt,
            max_tokens=profile.get("outline_max_tokens", 32000),
        ))

    results = bc.submit_and_wait(requests, label="outlines")

    outlines = {}
    for (title, wc), out_dir in zip(titles, output_dirs):
        cid = f"outline__{out_dir.name}"
        if cid not in results:
            print(f"  SKIP: outline failed for '{title}'")
            continue
        raw = results[cid].strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  ERROR: outline JSON parse failed for '{title}': {e}")
            (out_dir / "outline_raw.txt").write_text(raw, encoding="utf-8")
            continue
        write_text(out_dir / "outline.json", json.dumps(data, indent=2, ensure_ascii=False))
        outlines[out_dir.name] = data
        print(f"  [{out_dir.name}] outline: {len(data.get('sections', []))} sections")
    return outlines


def generate_sections(bc: BatchClient, profile, sop_text, titles, output_dirs, outlines):
    section_rules = profile.get("section_type_rules", {"default": "body"})
    max_tokens_map = profile.get("section_max_tokens", {"body": 6000})
    context_window = profile.get("context_window_words", 1500)

    active = []
    for (title, wc), out_dir in zip(titles, output_dirs):
        if out_dir.name not in outlines:
            continue
        sections = outlines[out_dir.name].get("sections", [])
        script_path = out_dir / "script.txt"
        script_path.write_text("", encoding="utf-8")
        active.append({
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
                outline_json=json.dumps(outlines[a["dir"].name], ensure_ascii=False),
                previous_script_tail=prev_tail,
                context_window_words=context_window,
                section_id=sec["id"],
                section_title=sec.get("title", ""),
                section_word_target=sec.get("word_target", ""),
            )

            cid = f"sec__{a['dir'].name}__{slot}"
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
                print(f"  SKIP: {a['dir'].name} section {sec['id']} failed")
                continue
            text = results[cid].rstrip() + "\n\n"
            append_text(a["script_path"], text)
            total = count_words(a["script_path"].read_text(encoding="utf-8"))
            added = count_words(text)
            print(f"  [{a['dir'].name}] section {sec['id']}: +{added} words (total {total}/{a['wc']})")


def main():
    print("=== Batch Script Generator ===\n")
    cfg = load_config()
    working_folder = prompt_working_folder(cfg.get("default_working_folder", "./outputs"))
    profile_name = prompt_profile()

    profile_dir = PROFILES_DIR / profile_name
    profile = json.loads(read_text(profile_dir / "profile.json"))
    sop_path = profile_dir / "sop.txt"
    sop_text = read_text(sop_path) if sop_path.exists() else ""

    model = profile.get("model", cfg.get("model", "claude-opus-4-7"))
    poll_interval = cfg.get("poll_interval_seconds", 30)

    titles = prompt_titles()

    print("\n=== Summary ===")
    print(f"Profile:        {profile_name}")
    print(f"Model:          {model}")
    print(f"Working folder: {working_folder}")
    print(f"Titles:         {len(titles)}")
    for t, wc in titles:
        print(f"   - {t} ({wc} words)")
    confirm = input("\nStart generation? [Y/n]: ").strip().lower()
    if confirm and confirm != "y":
        print("Cancelled.")
        return

    output_dirs = []
    for title, _ in titles:
        folder = working_folder / sanitize_folder_name(title)
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
    for (title, wc), out_dir in zip(titles, output_dirs):
        script_path = out_dir / "script.txt"
        if script_path.exists():
            words = count_words(script_path.read_text(encoding="utf-8"))
            print(f"  {title}: {words} words -> {script_path}")
        else:
            print(f"  {title}: FAILED (no script written)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
