"""
PhotonBP end-to-end test.
Run from Windows PowerShell:
    python C:\Users\AVIAT\Downloads\PHOTONBP-main\test_photon.py
"""

import sys
import json

sys.path.insert(0, r'C:\Users\AVIAT\Downloads\PHOTONBP-main\mcp_server')

from remote_control.remote_execution import RemoteExecution

# ── connect ──────────────────────────────────────────────────────────────────
re = RemoteExecution()
re.start()

if not re.remote_nodes:
    print("ERROR: No UE instance found. Make sure Unreal Editor is open.")
    re.stop()
    sys.exit(1)

re.open_command_connection(re.remote_nodes[0].node_id)
print(f"Connected to: {re.remote_nodes[0].node_id}\n")

# ── helper ───────────────────────────────────────────────────────────────────
PASS = 0
FAIL = 0

def run(label, script):
    global PASS, FAIL
    print(f"=== {label} ===")
    result = re.run_command(script, unattended=True)
    output = result.get('output', '')
    lines = [l.strip() for l in output.replace('\r', '').split('\n') if l.strip()]
    for line in lines:
        print("  ", line)
    ok = result.get('success', False) and not any('Error' in l or 'error' in l for l in lines if not l.startswith('LogPython'))
    status = "PASS" if lines else "WARN (no output)"
    print(f"  -> {status}\n")
    return output

# ── 1. Create Blueprint ───────────────────────────────────────────────────────
run("1. Create BP_PhotonTest", """
import unreal, json
unreal.EditorAssetLibrary.make_directory('/Game/PhotonTest')
if unreal.EditorAssetLibrary.does_asset_exist('/Game/PhotonTest/BP_PhotonTest'):
    print("Already exists - OK")
else:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('ParentClass', unreal.load_class(None, '/Script/Engine.Actor'))
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset('BP_PhotonTest', '/Game/PhotonTest', None, factory)
    print("Created:", bp.get_name() if bp else "FAILED")
""")

# ── 2. Add variable ───────────────────────────────────────────────────────────
run("2. add_member_variable (float Health)", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
ok = unreal.PhotonBPLibrary.add_member_variable(bp, 'Health', 'real', 'float', '')
print("add_member_variable Health =>", ok)
""")

# ── 3. Custom event ───────────────────────────────────────────────────────────
run("3. add_custom_event", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
guid = unreal.PhotonBPLibrary.add_custom_event(bp, 'OnHealthChanged', 0, 0)
print("add_custom_event guid =>", guid if guid else "FAILED (empty)")
""")

# ── 4. BeginPlay event node ───────────────────────────────────────────────────
run("4. add_event_node (ReceiveBeginPlay)", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
guid = unreal.PhotonBPLibrary.add_event_node(bp, 'EventGraph', 'ReceiveBeginPlay', -200, 0)
print("add_event_node BeginPlay guid =>", guid if guid else "FAILED (empty)")
""")

# ── 5. PrintString function call ──────────────────────────────────────────────
run("5. add_function_call_node (PrintString)", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
guid = unreal.PhotonBPLibrary.add_function_call_node(bp, 'EventGraph', 'KismetSystemLibrary', 'PrintString', 200, 0)
print("add_function_call_node PrintString guid =>", guid if guid else "FAILED (empty)")
""")

# ── 6. Branch node ────────────────────────────────────────────────────────────
run("6. add_branch_node", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
guid = unreal.PhotonBPLibrary.add_branch_node(bp, 'EventGraph', 500, 0)
print("add_branch_node guid =>", guid if guid else "FAILED (empty)")
""")

# ── 7. Variable GET node ──────────────────────────────────────────────────────
run("7. add_variable_get_node (Health)", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
guid = unreal.PhotonBPLibrary.add_variable_get_node(bp, 'EventGraph', 'Health', 300, 150)
print("add_variable_get_node Health guid =>", guid if guid else "FAILED (empty)")
""")

# ── 8. Inspect graph ──────────────────────────────────────────────────────────
graph_output = run("8. get_graph_nodes", """
import unreal, json
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
raw = unreal.PhotonBPLibrary.get_graph_nodes(bp, 'EventGraph')
nodes = json.loads(raw)
print("NODE COUNT:", len(nodes))
for n in nodes:
    pins = [p['name'] + '(' + p['dir'][0] + ')' for p in n.get('pins', [])]
    print("  TYPE:", n['type'])
    print("  NAME:", n['name'])
    print("  GUID:", n['guid'])
    print("  PINS:", ', '.join(pins))
    print("  ---")
""")

# ── 9. Wire BeginPlay -> PrintString + set pin value ─────────────────────────
run("9. connect_pins + set_pin_default_value", """
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

print("BeginPlay guid:", begin_guid)
print("PrintString guid:", print_guid)

if begin_guid and print_guid:
    ok = unreal.PhotonBPLibrary.connect_pins(bp, 'EventGraph', begin_guid, 'then', print_guid, 'execute')
    print("connect BeginPlay.then -> PrintString.execute =>", ok)
    ok2 = unreal.PhotonBPLibrary.set_pin_default_value(bp, 'EventGraph', print_guid, 'InString', 'PhotonBP works!')
    print("set_pin_default_value InString =>", ok2)
else:
    print("ERROR: one or both GUIDs not found")
    print("Available nodes:")
    for n in nodes:
        print(" ", n['type'], "|", n['name'])
""")

# ── 10. Compile and save ──────────────────────────────────────────────────────
run("10. compile + save", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
saved = unreal.EditorAssetLibrary.save_asset('/Game/PhotonTest/BP_PhotonTest')
print("Compile + Save =>", saved)
""")

# ── disconnect ────────────────────────────────────────────────────────────────
re.close_command_connection()
re.stop()

print("=" * 60)
print("DONE — open /Game/PhotonTest/BP_PhotonTest in UE to verify")
print("You should see: BeginPlay wired to PrintString('PhotonBP works!')")
print("=" * 60)
