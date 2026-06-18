"""
test_photon.py
==============
End-to-end test for PhotonBPLibrary via HTTP bridge.
NO multicast. NO UDP. NO admin rights required.

Prerequisites:
  1. UE 5.4 is running with your project open.
  2. Remote Control Plugin enabled (Edit > Project Settings > Plugins > Remote Control API = ON).
  3. ue_http_bridge.py has been loaded in UE — run INSTALL_BRIDGE.ps1 first, OR
     paste the one-liner below into UE's Python console (Output Log):

       exec(open(r'C:\\path\\to\\your\\project\\Content\\Python\\ue_http_bridge.py').read())

     OR if you already copied it to Content/Python, just:
       import ue_http_bridge

Run:
  python test_photon.py
"""

import sys
import os
import json
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────

HTTP_PORT = 30010
BASE_URL  = f"http://127.0.0.1:{HTTP_PORT}"

BRIDGE_OBJECT   = "/Engine/PhotonExecBridge.Default__PhotonExecBridge_C"
BRIDGE_FUNCTION = "RunScript"

FALLBACK_OBJECT   = "/Engine/PythonScriptPlugin.Default__PythonScriptPlugin"
FALLBACK_FUNCTION = "ExecutePythonScript"

# ── Low-level HTTP ────────────────────────────────────────────────────────────

def _put(path: str, body: dict, timeout: int = 30) -> dict:
    url  = BASE_URL + path
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


# ── Bridge call ───────────────────────────────────────────────────────────────

def run_in_ue(script: str, timeout: int = 30) -> dict:
    """
    Execute Python inside UE via PhotonExecBridge.
    Returns {"ok": bool, "output": str, "error": str|None}.
    """
    raw = _put("/remote/object/call", {
        "objectPath": BRIDGE_OBJECT,
        "functionName": BRIDGE_FUNCTION,
        "parameters": {"Script": script},
        "generateTransaction": False
    }, timeout=timeout)

    # HTTP API wraps return value: {"ReturnValue": "<json_string>"}
    return_value = raw.get("ReturnValue") or raw.get("returnValue") or ""
    if isinstance(return_value, str) and return_value.startswith("{"):
        try:
            return json.loads(return_value)
        except json.JSONDecodeError:
            pass
    return {"ok": True, "output": str(raw), "error": None}


def show(label: str, result: dict):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    output = result.get("output", "").strip()
    error  = result.get("error")
    ok     = result.get("ok", False)
    if output:
        for line in output.splitlines():
            print(f"  {line}")
    if error:
        print(f"  !! ERROR: {error}")
    print(f"  >> ok={ok}")


# ── Step 0: Connectivity check ────────────────────────────────────────────────

print("=" * 60)
print("  PhotonBP End-to-End Test (HTTP Bridge)")
print("=" * 60)

# 0a. Can we reach UE at all?
print("\n[0a] Pinging UE Remote Control HTTP API...")
try:
    urllib.request.urlopen(BASE_URL + "/remote/info", timeout=3)
    print("  OK — UE is reachable on port 30010")
except Exception as e:
    print(f"  FAIL — {e}")
    print()
    print("  UE is not reachable. Make sure:")
    print("    1. UE is running")
    print("    2. Remote Control Plugin is enabled:")
    print("       Edit > Project Settings > Plugins > Remote Control API = ON")
    print("    3. UE has been restarted after enabling the plugin")
    sys.exit(1)

# 0b. Is our bridge loaded?
print("\n[0b] Checking PhotonExecBridge...")
bridge_ok = False
try:
    r = run_in_ue("print('bridge_ok')")
    if r.get("ok") and "bridge_ok" in r.get("output", ""):
        bridge_ok = True
        print("  OK — PhotonExecBridge is active and returning output")
    else:
        print(f"  WARN — Bridge responded but output unexpected: {r}")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print("  FAIL — PhotonExecBridge not found (404)")
    else:
        print(f"  FAIL — HTTP {e.code}: {e}")
except Exception as e:
    print(f"  FAIL — {e}")

if not bridge_ok:
    print()
    print("  The PhotonExecBridge is NOT loaded in UE.")
    print()
    print("  TO FIX (easiest): Paste this into UE's Python console (Output Log tab):")
    print()
    print("    import sys; sys.path.insert(0, r'C:\\path\\to\\ueos\\ue_scripts'); import ue_http_bridge")
    print()
    print("  OR run INSTALL_BRIDGE.ps1 from PowerShell.")
    print()
    print("  Then re-run: python test_photon.py")
    sys.exit(1)

print()
print("  Bridge confirmed. Starting PhotonBP tests...")

# ── Test 1: PhotonBPLibrary loaded? ──────────────────────────────────────────

show("1. PhotonBPLibrary check", run_in_ue("""
import unreal
found = hasattr(unreal, 'PhotonBPLibrary')
print('PhotonBPLibrary found:', found)
if found:
    methods = [m for m in dir(unreal.PhotonBPLibrary) if not m.startswith('_')]
    print('Methods:', methods)
"""))

# ── Test 2: Create BP_PhotonTest ─────────────────────────────────────────────

show("2. Create BP_PhotonTest", run_in_ue("""
import unreal
unreal.EditorAssetLibrary.make_directory('/Game/PhotonTest')
if unreal.EditorAssetLibrary.does_asset_exist('/Game/PhotonTest/BP_PhotonTest'):
    print('Already exists — skipping creation')
else:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('ParentClass', unreal.load_class(None, '/Script/Engine.Actor'))
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        'BP_PhotonTest', '/Game/PhotonTest', None, factory)
    print('Created:', bp.get_name() if bp else 'FAILED')
"""))

# ── Test 3: Add member variable ───────────────────────────────────────────────

show("3. add_member_variable (float Health)", run_in_ue("""
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
if not bp:
    print('ERROR: Could not load BP_PhotonTest')
else:
    ok = unreal.PhotonBPLibrary.add_member_variable(bp, 'Health', 'real', 'float', '')
    print('add_member_variable Health =>', ok)
"""))

# ── Test 4: Add BeginPlay + PrintString nodes ─────────────────────────────────

show("4. Add BeginPlay + PrintString nodes", run_in_ue("""
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
if not bp:
    print('ERROR: Could not load BP_PhotonTest')
else:
    g1 = unreal.PhotonBPLibrary.add_event_node(
        bp, 'EventGraph', 'ReceiveBeginPlay', -200, 0)
    g2 = unreal.PhotonBPLibrary.add_function_call_node(
        bp, 'EventGraph', 'KismetSystemLibrary', 'PrintString', 200, 0)
    print('BeginPlay guid:', g1)
    print('PrintString guid:', g2)
    print('Both created:', bool(g1 and g2))
"""))

# ── Test 5: get_graph_nodes ───────────────────────────────────────────────────

show("5. get_graph_nodes", run_in_ue("""
import unreal, json
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
if not bp:
    print('ERROR: Could not load BP_PhotonTest')
else:
    raw = unreal.PhotonBPLibrary.get_graph_nodes(bp, 'EventGraph')
    nodes = json.loads(raw)
    print('NODE COUNT:', len(nodes))
    for n in nodes:
        pins = [p['name'] + '(' + p['dir'][0] + ')' for p in n.get('pins', [])]
        print('  TYPE:', n['type'], '| NAME:', n['name'])
        print('  GUID:', n['guid'])
        print('  PINS:', ', '.join(pins[:6]), ('...' if len(pins) > 6 else ''))
"""))

# ── Test 6: connect_pins + set value + compile ────────────────────────────────

show("6. connect_pins + set_pin_default_value + compile", run_in_ue("""
import unreal, json
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
if not bp:
    print('ERROR: Could not load BP_PhotonTest')
else:
    raw = unreal.PhotonBPLibrary.get_graph_nodes(bp, 'EventGraph')
    nodes = json.loads(raw)
    begin_guid = None
    print_guid  = None
    for n in nodes:
        t = n['type']
        nm = n['name']
        if 'Event' in t and 'BeginPlay' in nm:
            begin_guid = n['guid']
        if 'CallFunction' in t and 'Print' in nm:
            print_guid = n['guid']
    print('BeginPlay GUID:', begin_guid)
    print('PrintString GUID:', print_guid)
    if begin_guid and print_guid:
        ok = unreal.PhotonBPLibrary.connect_pins(
            bp, 'EventGraph', begin_guid, 'then', print_guid, 'execute')
        print('connect_pins =>', ok)
        ok2 = unreal.PhotonBPLibrary.set_pin_default_value(
            bp, 'EventGraph', print_guid, 'InString', 'PhotonBP works!')
        print('set_pin_default_value =>', ok2)
    else:
        print('WARN: Could not find both nodes — run test 4 first')
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset('/Game/PhotonTest/BP_PhotonTest')
    print('COMPILED AND SAVED')
"""))

# ── Done ──────────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print("  ALL TESTS COMPLETE")
print("  Open BP_PhotonTest in UE to verify nodes are wired up.")
print("=" * 60)
