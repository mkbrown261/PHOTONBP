# PhotonBP test — uses HTTP API on port 30010
# Run: python test_photon.py

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'mcp_server'))

import urllib.request, urllib.error

BASE = "http://127.0.0.1:30010"

def http(path, body=None, method="PUT"):
    url  = BASE + path
    if body is not None:
        data = json.dumps(body).encode()
        req  = urllib.request.Request(url, data=data,
               headers={"Content-Type": "application/json"}, method=method)
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

def run_py(script):
    """Run Python in UE and return the response dict."""
    return http("/remote/object/call", {
        "objectPath": "/Engine/PythonScriptPlugin.Default__PythonScriptPlugin",
        "functionName": "ExecutePythonScript",
        "parameters": {"PythonScript": script},
        "generateTransaction": False
    })

# ── 1. Ping ───────────────────────────────────────────────────────────────────
print("=== 1. HTTP ping ===")
r = http("/remote/info", method="GET")
if "error" in r:
    print("  FAILED:", r)
    sys.exit(1)
print("  OK - HTTP API is alive\n")

# ── 2. Test basic Python execution ────────────────────────────────────────────
print("=== 2. Basic Python execution ===")
r = run_py("import unreal; unreal.log('PHOTON_PING_OK')")
print("  response:", json.dumps(r, indent=2))
print()

# ── 3. Check PhotonBPLibrary is loaded ────────────────────────────────────────
print("=== 3. Check PhotonBPLibrary ===")
r = run_py("""
import unreal
found = hasattr(unreal, 'PhotonBPLibrary')
unreal.log('PhotonBPLibrary found: ' + str(found))
if found:
    methods = [m for m in dir(unreal.PhotonBPLibrary) if not m.startswith('_')]
    unreal.log('Methods: ' + str(methods))
""")
print("  response:", json.dumps(r, indent=2))
print()

# ── 4. Create Blueprint ───────────────────────────────────────────────────────
print("=== 4. Create BP_PhotonTest ===")
r = run_py("""
import unreal
unreal.EditorAssetLibrary.make_directory('/Game/PhotonTest')
if unreal.EditorAssetLibrary.does_asset_exist('/Game/PhotonTest/BP_PhotonTest'):
    unreal.log('BP already exists')
else:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('ParentClass', unreal.load_class(None, '/Script/Engine.Actor'))
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset('BP_PhotonTest', '/Game/PhotonTest', None, factory)
    unreal.log('Created: ' + (bp.get_name() if bp else 'FAILED'))
""")
print("  response:", json.dumps(r, indent=2))
print()

# ── 5. Add variable ───────────────────────────────────────────────────────────
print("=== 5. add_member_variable (float Health) ===")
r = run_py("""
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
ok = unreal.PhotonBPLibrary.add_member_variable(bp, 'Health', 'real', 'float', '')
unreal.log('add_member_variable Health => ' + str(ok))
""")
print("  response:", json.dumps(r, indent=2))
print()

# ── 6. Add BeginPlay + PrintString nodes ─────────────────────────────────────
print("=== 6. Add nodes ===")
r = run_py("""
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
g1 = unreal.PhotonBPLibrary.add_event_node(bp, 'EventGraph', 'ReceiveBeginPlay', -200, 0)
g2 = unreal.PhotonBPLibrary.add_function_call_node(bp, 'EventGraph', 'KismetSystemLibrary', 'PrintString', 200, 0)
unreal.log('BeginPlay guid: ' + str(g1))
unreal.log('PrintString guid: ' + str(g2))
""")
print("  response:", json.dumps(r, indent=2))
print()

# ── 7. Inspect graph nodes ────────────────────────────────────────────────────
print("=== 7. get_graph_nodes ===")
r = run_py("""
import unreal, json
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
raw = unreal.PhotonBPLibrary.get_graph_nodes(bp, 'EventGraph')
unreal.log('GRAPH_NODES:' + raw)
""")
print("  response:", json.dumps(r, indent=2))
print()

# ── 8. Wire + compile ─────────────────────────────────────────────────────────
print("=== 8. connect_pins + compile ===")
r = run_py("""
import unreal, json
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
raw = unreal.PhotonBPLibrary.get_graph_nodes(bp, 'EventGraph')
nodes = json.loads(raw)
begin_guid = None
print_guid = None
for n in nodes:
    if 'Event' in n['type'] and 'BeginPlay' in n['name']:
        begin_guid = n['guid']
    if 'CallFunction' in n['type'] and 'Print' in n['name']:
        print_guid = n['guid']
unreal.log('BeginPlay: ' + str(begin_guid))
unreal.log('PrintString: ' + str(print_guid))
if begin_guid and print_guid:
    ok = unreal.PhotonBPLibrary.connect_pins(bp, 'EventGraph', begin_guid, 'then', print_guid, 'execute')
    unreal.log('connect => ' + str(ok))
    ok2 = unreal.PhotonBPLibrary.set_pin_default_value(bp, 'EventGraph', print_guid, 'InString', 'PhotonBP works!')
    unreal.log('set_pin_value => ' + str(ok2))
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.EditorAssetLibrary.save_asset('/Game/PhotonTest/BP_PhotonTest')
unreal.log('DONE')
""")
print("  response:", json.dumps(r, indent=2))
print()

print("=" * 60)
print("Check UE Output Log for unreal.log() messages")
print("Open /Game/PhotonTest/BP_PhotonTest in UE to verify nodes")
print("=" * 60)
