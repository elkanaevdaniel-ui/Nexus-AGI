#!/usr/bin/env python3
"""Fix Agent Zero infinite loop - patch extract_tools.py json parsing."""
import os, re, shutil, json, sys, subprocess, time

BASE = "/home/ubuntu/Nexus-AGI/agent-zero"
ET = os.path.join(BASE, "python/helpers/extract_tools.py")

print("=" * 60)
print("STEP 1: Patch extract_tools.py - add direct json.loads")
print("=" * 60)

with open(ET) as f:
    content = f.read()
    lines = content.split("\n")

shutil.copy2(ET, ET + ".bak_loop_fix")

func_start = None
for i, line in enumerate(lines):
    if "def json_parse_dirty" in line:
        func_start = i
        break

if func_start is None:
    print("ERROR: json_parse_dirty not found!")
    sys.exit(1)

print(f"Found json_parse_dirty at line {func_start + 1}")

if "# PATCH: direct json.loads" in content:
    print("Fix already applied! Skipping patch.")
else:
    insert_before = None
    for i in range(func_start + 1, min(func_start + 20, len(lines))):
        if "extract_json_object_string" in lines[i]:
            insert_before = i
            break

    if insert_before is None:
        print("ERROR: Could not find extract_json_object_string")
        sys.exit(1)

    print(f"Inserting fix before line {insert_before + 1}")
    indent = "    "
    fix_lines = [
        f"{indent}# PATCH: direct json.loads for adapter plain JSON",
        f"{indent}try:",
        f"{indent}    import json as _json",
        f"{indent}    _direct = _json.loads(json.strip())",
        f"{indent}    if isinstance(_direct, dict):",
        f"{indent}        return _direct",
        f"{indent}except Exception:",
        f"{indent}    pass",
        f"",
    ]
    for j, fl in enumerate(fix_lines):
        lines.insert(insert_before + j, fl)
    with open(ET, "w") as f:
        f.write("\n".join(lines))
    print("PATCHED extract_tools.py")

print()
print("=" * 60)
print("STEP 2: Diagnose agent.py monologue loop")
print("=" * 60)

for r, d, fs in os.walk(BASE):
    for fn in fs:
        if fn == "agent.py":
            p = os.path.join(r, fn)
            with open(p) as f:
                ac = f.read()
            for pat in ["monologue", "break_loop", "json_parse"]:
                for i, line in enumerate(ac.split("\n")):
                    if pat in line and not line.strip().startswith("#"):
                        print(f"  {p}:{i+1}: {line.rstrip()[:100]}")

print()
print("=" * 60)
print("STEP 3: Check response.py")
print("=" * 60)

for r, d, fs in os.walk(os.path.join(BASE, "python/tools")):
    for fn in fs:
        if fn == "response.py":
            p = os.path.join(r, fn)
            with open(p) as f:
                print(f.read())

print()
print("=" * 60)
print("STEP 4: Restart services")
print("=" * 60)

subprocess.run(["pkill", "-f", "run_ui.py"], capture_output=True)
subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
time.sleep(2)

adapter_loop = "/tmp/adapter_loop.sh"
if os.path.exists(adapter_loop):
    subprocess.Popen(["bash", adapter_loop],
        stdout=open("/tmp/claude-adapter.log", "a"),
        stderr=subprocess.STDOUT)
    print("Started adapter via loop script")
else:
    subprocess.Popen(
        ["python3", "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", "8090",
         "--workers", "1", "--log-level", "info"],
        cwd="/home/ubuntu/Nexus-AGI/services/claude-adapter",
        stdout=open("/tmp/claude-adapter.log", "a"),
        stderr=subprocess.STDOUT)
    print("Started adapter directly")

subprocess.Popen(
    ["python3", "run_ui.py", "--dockerized"],
    cwd=BASE,
    stdout=open("/tmp/agent-zero.log", "a"),
    stderr=subprocess.STDOUT)
print("Started Agent Zero UI")
time.sleep(5)

import urllib.request
try:
    r = urllib.request.urlopen("http://127.0.0.1:8090/health", timeout=5)
    print(f"Adapter: {r.status}")
except Exception as e:
    print(f"Adapter: {e}")
try:
    r = urllib.request.urlopen("http://127.0.0.1:50001/", timeout=5)
    print(f"AZ UI: {r.status}")
except Exception as e:
    print(f"AZ UI: {e}")

print("\nDONE! Test by sending a message in Agent Zero UI.")
