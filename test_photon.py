# PhotonBP test — uses Epic's OWN remote_execution.py from UE install
# Run: python test_photon.py

import sys, os, json

# Use Epic's remote_execution.py directly from the UE install
UE_REMOTE_EXEC = r"C:\Program Files\Epic Games\UE_5.4\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python\remote_execution.py"

if not os.path.exists(UE_REMOTE_EXEC):
    # Try alternate location
    UE_REMOTE_EXEC = r"C:\Program Files\Epic Games\UE_5.4\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python\remote_execution.py"
    print("Looking for Epic's remote_execution.py at:")
    print(" ", UE_REMOTE_EXEC)
    if not os.path.exists(UE_REMOTE_EXEC):
        print("NOT FOUND. Searching...")
        import glob
        results = glob.glob(r"C:\Program Files\Epic Games\**\remote_execution.py", recursive=True)
        if results:
            UE_REMOTE_EXEC = results[0]
            print("Found:", UE_REMOTE_EXEC)
        else:
            print("ERROR: Could not find Epic's remote_execution.py")
            print("Paste the path manually below.")
            sys.exit(1)

print("Using:", UE_REMOTE_EXEC)
sys.path.insert(0, os.path.dirname(UE_REMOTE_EXEC))

import remote_execution as ue_remote

# ── Connect ───────────────────────────────────────────────────────────────────
re = ue_remote.RemoteExecution()
re.start()

import time
time.sleep(2)  # give discovery time

nodes = re.remote_nodes
print(f"Found {len(nodes)} UE node(s): {[n.node_id for n in nodes]}")

if not nodes:
    print("ERROR: No UE instance found via multicast.")
    re.stop()
    sys.exit(1)

re.open_command_connection(nodes[0].node_id)
print("Connected!\n")

def run(label, script):
    print(f"=== {label} ===")
    result = re.run_command(script, unattended=True)
    output = result.get('output', [])
    for entry in (output if isinstance(output, list) else []):
        msg = entry.get('output', '') if isinstance(entry, dict) else str(entry)
        if msg.strip():
            print("  ", msg.strip())
    success = result.get('success', False)
    print(f"  success={success}\n")
    return result

# ── Tests ─────────────────────────────────────────────────────────────────────
run("1. PhotonBPLibrary check", """
import unreal
found = hasattr(unreal, 'PhotonBPLibrary')
print('PhotonBPLibrary found:', found)
if found:
    methods = [m for m in dir(unreal.PhotonBPLibrary) if not m.startswith('_')]
    print('Methods:', methods)
""")

run("2. Create BP_PhotonTest", """
import unreal
unreal.EditorAssetLibrary.make_directory('/Game/PhotonTest')
if unreal.EditorAssetLibrary.does_asset_exist('/Game/PhotonTest/BP_PhotonTest'):
    print('Already exists')
else:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('ParentClass', unreal.load_class(None, '/Script/Engine.Actor'))
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset('BP_PhotonTest', '/Game/PhotonTest', None, factory)
    print('Created:', bp.get_name() if bp else 'FAILED')
""")

run("3. add_member_variable (float Health)", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
ok = unreal.PhotonBPLibrary.add_member_variable(bp, 'Health', 'real', 'float', '')
print('add_member_variable Health =>', ok)
""")

run("4. Add BeginPlay + PrintString nodes", """
import unreal
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
g1 = unreal.PhotonBPLibrary.add_event_node(bp, 'EventGraph', 'ReceiveBeginPlay', -200, 0)
g2 = unreal.PhotonBPLibrary.add_function_call_node(bp, 'EventGraph', 'KismetSystemLibrary', 'PrintString', 200, 0)
print('BeginPlay guid:', g1)
print('PrintString guid:', g2)
""")

run("5. get_graph_nodes", """
import unreal, json
bp = unreal.EditorAssetLibrary.load_asset('/Game/PhotonTest/BP_PhotonTest')
raw = unreal.PhotonBPLibrary.get_graph_nodes(bp, 'EventGraph')
nodes = json.loads(raw)
print('NODE COUNT:', len(nodes))
for n in nodes:
    pins = [p['name'] + '(' + p['dir'][0] + ')' for p in n.get('pins', [])]
    print('  TYPE:', n['type'], '| NAME:', n['name'])
    print('  GUID:', n['guid'])
    print('  PINS:', ', '.join(pins))
""")

run("6. connect_pins + set value + compile", """
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
print('BeginPlay:', begin_guid)
print('PrintString:', print_guid)
if begin_guid and print_guid:
    ok = unreal.PhotonBPLibrary.connect_pins(bp, 'EventGraph', begin_guid, 'then', print_guid, 'execute')
    print('connect =>', ok)
    ok2 = unreal.PhotonBPLibrary.set_pin_default_value(bp, 'EventGraph', print_guid, 'InString', 'PhotonBP works!')
    print('set_pin_value =>', ok2)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
unreal.EditorAssetLibrary.save_asset('/Game/PhotonTest/BP_PhotonTest')
print('DONE')
""")

re.close_command_connection()
re.stop()
print("=" * 60)
print("DONE - open BP_PhotonTest in UE to verify nodes")
print("=" * 60)
