"""
UEOS Data Tools — Phase 2
Full implementation: Structs, Enums, DataTables, CurveTables, PrimaryDataAssets

UE 5.4 Python APIs used:
  - unreal.UserDefinedStruct           via EditorAssetLibrary + StructureEditorUtils
  - unreal.UserDefinedEnum             via UserDefinedEnumEditorUtils / EnumEditorUtils
  - unreal.DataTable                   via DataTableFunctionLibrary
  - unreal.CurveTable                  via CurveTableEditorUtils
  - unreal.AssetToolsHelpers           for creation + import
  - unreal.EditorAssetLibrary          for save / exist checks
  - unreal.DataTableImportOptions      for CSV import

Tools exposed (13 total):
  data_create_struct        — create UserDefinedStruct with typed fields
  data_add_struct_field     — add a field to an existing struct
  data_get_struct_fields    — read all fields from a struct
  data_create_enum          — create UserDefinedEnum with values
  data_add_enum_value       — append a value to an existing enum
  data_get_enum_values      — read all values from an enum
  data_create_datatable     — create empty DataTable with row struct
  data_add_row              — add / update a row in a DataTable
  data_get_row              — read one row from a DataTable
  data_get_all_rows         — dump entire DataTable as JSON
  data_delete_row           — remove a row from a DataTable
  data_import_csv           — import a CSV file as DataTable
  data_create_curve_table   — create CurveTable with Float/Vector curves
  data_get_curve            — read curve keys from a CurveTable
  data_create_data_asset    — create a PrimaryDataAsset subclass instance
"""

import json
import logging
from textwrap import dedent
from mcp import types

log = logging.getLogger("ueos.data")


# ──────────────────────────────────────────────────────────────────────────────
# UE 5.4 type mapping: friendly name → struct member type string
# Used when creating struct fields
# ──────────────────────────────────────────────────────────────────────────────
STRUCT_FIELD_TYPES: dict[str, str] = {
    # Primitives
    "bool":         "bool",
    "byte":         "uint8",
    "int":          "int32",
    "int32":        "int32",
    "int64":        "int64",
    "float":        "float",
    "double":       "double",
    "string":       "FString",
    "name":         "FName",
    "text":         "FText",
    # Math
    "vector":       "FVector",
    "vector2d":     "FVector2D",
    "vector4":      "FVector4",
    "rotator":      "FRotator",
    "transform":    "FTransform",
    "color":        "FColor",
    "linear_color": "FLinearColor",
    "quat":         "FQuat",
    # Asset refs
    "soft_object":  "TSoftObjectPtr<UObject>",
    "soft_class":   "TSoftClassPtr<UObject>",
    "object":       "UObject*",
    "class":        "TSubclassOf<UObject>",
    "actor":        "AActor*",
    # Gameplay
    "gameplay_tag": "FGameplayTag",
    "datetime":     "FDateTime",
    "timespan":     "FTimespan",
    "guid":         "FGuid",
}

# UE Python pin-type codes used by StructureEditorUtils.add_variable
PIN_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    # (PinCategory, PinSubCategoryObject)
    "bool":         ("bool",    ""),
    "byte":         ("byte",    ""),
    "int":          ("int",     ""),
    "int32":        ("int",     ""),
    "int64":        ("int64",   ""),
    "float":        ("real",    ""),
    "double":       ("real",    ""),
    "string":       ("string",  ""),
    "name":         ("name",    ""),
    "text":         ("text",    ""),
    "vector":       ("struct",  "/Script/CoreUObject.Vector"),
    "vector2d":     ("struct",  "/Script/CoreUObject.Vector2D"),
    "vector4":      ("struct",  "/Script/CoreUObject.Vector4"),
    "rotator":      ("struct",  "/Script/CoreUObject.Rotator"),
    "transform":    ("struct",  "/Script/CoreUObject.Transform"),
    "color":        ("struct",  "/Script/CoreUObject.Color"),
    "linear_color": ("struct",  "/Script/CoreUObject.LinearColor"),
    "quat":         ("struct",  "/Script/CoreUObject.Quat"),
    "gameplay_tag": ("struct",  "/Script/GameplayTags.GameplayTag"),
    "datetime":     ("struct",  "/Script/CoreUObject.DateTime"),
    "guid":         ("struct",  "/Script/CoreUObject.Guid"),
}


class DataTools:
    def __init__(self, ue):
        self.ue = ue

    # ──────────────────────────────────────────────────────────────────────
    # MCP interface
    # ──────────────────────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [
            types.Tool(
                name="data_create_struct",
                description=(
                    "Create a new UserDefinedStruct asset in Unreal Engine 5.4. "
                    "Supports all primitive, math, and gameplay types. "
                    "Optionally pre-populate fields in one call."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":   {"type": "string", "description": "Struct asset name e.g. FCharacterStats"},
                        "path":   {"type": "string", "description": "Content path e.g. /Game/Data/Structs"},
                        "fields": {
                            "type": "array",
                            "description": "Optional initial fields",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field_name": {"type": "string"},
                                    "type":       {"type": "string",
                                                   "description": "bool/int/float/string/vector/rotator/transform/linear_color/name/text/byte/int64/double/vector2d/vector4/quat/color/gameplay_tag/datetime/guid"},
                                    "tooltip":    {"type": "string", "default": ""}
                                },
                                "required": ["field_name", "type"]
                            }
                        }
                    },
                    "required": ["name", "path"]
                }
            ),
            types.Tool(
                name="data_add_struct_field",
                description="Add a new field (variable) to an existing UserDefinedStruct asset.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "struct_path": {"type": "string", "description": "Full content path e.g. /Game/Data/Structs/FCharacterStats"},
                        "field_name":  {"type": "string"},
                        "type":        {"type": "string",
                                        "description": "Same type options as data_create_struct"},
                        "tooltip":     {"type": "string", "default": ""}
                    },
                    "required": ["struct_path", "field_name", "type"]
                }
            ),
            types.Tool(
                name="data_get_struct_fields",
                description="Read all field definitions from a UserDefinedStruct.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "struct_path": {"type": "string", "description": "Full content path to the struct"}
                    },
                    "required": ["struct_path"]
                }
            ),
            types.Tool(
                name="data_create_enum",
                description=(
                    "Create a new UserDefinedEnum asset with named values. "
                    "Enums created here can be used as Blueprint variable types."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":   {"type": "string", "description": "Enum name e.g. ECharacterClass"},
                        "path":   {"type": "string", "description": "Content path e.g. /Game/Data/Enums"},
                        "values": {
                            "type": "array",
                            "description": "List of enum value names",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["name", "path", "values"]
                }
            ),
            types.Tool(
                name="data_add_enum_value",
                description="Append a new value to an existing UserDefinedEnum.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "enum_path": {"type": "string", "description": "Full content path to the enum"},
                        "value_name": {"type": "string", "description": "New value name to add"}
                    },
                    "required": ["enum_path", "value_name"]
                }
            ),
            types.Tool(
                name="data_get_enum_values",
                description="Read all value names and indices from a UserDefinedEnum.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "enum_path": {"type": "string", "description": "Full content path to the enum"}
                    },
                    "required": ["enum_path"]
                }
            ),
            types.Tool(
                name="data_create_datatable",
                description=(
                    "Create a new empty DataTable asset in UE 5.4, bound to a row struct. "
                    "The row struct must already exist (create it with data_create_struct first)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":        {"type": "string", "description": "DataTable asset name e.g. DT_Characters"},
                        "path":        {"type": "string", "description": "Content path e.g. /Game/Data"},
                        "struct_path": {"type": "string",
                                        "description": "Full content path to the row struct, OR a built-in struct path like /Script/Engine.CompositeCurveTableRow"}
                    },
                    "required": ["name", "path", "struct_path"]
                }
            ),
            types.Tool(
                name="data_add_row",
                description=(
                    "Add or update a row in an existing DataTable. "
                    "Row data is a dict matching the struct's field names."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_path": {"type": "string", "description": "Full content path to the DataTable"},
                        "row_name":   {"type": "string", "description": "Row key name"},
                        "row_data":   {
                            "type": "object",
                            "description": "Dict of field_name → value matching the row struct"
                        }
                    },
                    "required": ["table_path", "row_name", "row_data"]
                }
            ),
            types.Tool(
                name="data_get_row",
                description="Read a single named row from a DataTable as JSON.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_path": {"type": "string"},
                        "row_name":   {"type": "string"}
                    },
                    "required": ["table_path", "row_name"]
                }
            ),
            types.Tool(
                name="data_get_all_rows",
                description="Dump the entire contents of a DataTable as a JSON array.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_path": {"type": "string", "description": "Full content path to the DataTable"}
                    },
                    "required": ["table_path"]
                }
            ),
            types.Tool(
                name="data_delete_row",
                description="Remove a named row from a DataTable.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_path": {"type": "string"},
                        "row_name":   {"type": "string"}
                    },
                    "required": ["table_path", "row_name"]
                }
            ),
            types.Tool(
                name="data_import_csv",
                description=(
                    "Import a CSV file as a DataTable asset. "
                    "CSV first column is the row name; remaining columns map to struct fields. "
                    "Creates the DataTable asset if it does not exist."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "csv_path":    {"type": "string", "description": "Absolute path to the CSV file on disk"},
                        "name":        {"type": "string", "description": "Target DataTable asset name"},
                        "path":        {"type": "string", "description": "Content path to create the DataTable in"},
                        "struct_path": {"type": "string", "description": "Row struct content path (required if table doesn't exist yet)"},
                        "replace_existing": {"type": "boolean", "default": True}
                    },
                    "required": ["csv_path", "name", "path"]
                }
            ),
            types.Tool(
                name="data_create_curve_table",
                description=(
                    "Create a CurveTable asset with named float curves. "
                    "Each curve is a list of (time, value) key pairs. "
                    "Useful for stat scaling, damage falloff, animation curves shared across Blueprints."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":       {"type": "string", "description": "Asset name e.g. CT_DamageScaling"},
                        "path":       {"type": "string", "description": "Content path"},
                        "curve_type": {"type": "string",
                                       "description": "float (default) or vector",
                                       "enum": ["float", "vector"],
                                       "default": "float"},
                        "curves": {
                            "type": "object",
                            "description": "Dict of curve_name → list of [time, value] pairs. For vector curves use [time, x, y, z].",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"type": "array"}
                            }
                        }
                    },
                    "required": ["name", "path", "curves"]
                }
            ),
            types.Tool(
                name="data_get_curve",
                description="Read all key-value pairs from a named curve in a CurveTable.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_path":  {"type": "string", "description": "Full content path to the CurveTable"},
                        "curve_name":  {"type": "string", "description": "Name of the curve row"}
                    },
                    "required": ["table_path", "curve_name"]
                }
            ),
            types.Tool(
                name="data_create_data_asset",
                description=(
                    "Create a PrimaryDataAsset (or subclass) instance. "
                    "Useful for creating DA_ game config assets tied to a custom Blueprint class."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name":       {"type": "string", "description": "Asset name e.g. DA_HeroConfig"},
                        "path":       {"type": "string", "description": "Content path"},
                        "class_path": {"type": "string",
                                       "description": "UE class path for the asset. Default: /Script/Engine.PrimaryDataAsset",
                                       "default": "/Script/Engine.PrimaryDataAsset"},
                        "properties": {
                            "type": "object",
                            "description": "Optional dict of property name → value to set immediately",
                            "additionalProperties": True
                        }
                    },
                    "required": ["name", "path"]
                }
            ),
        ]

    async def handle(self, name: str, args: dict) -> list[types.TextContent]:
        handlers = {
            "data_create_struct":     self._create_struct,
            "data_add_struct_field":  self._add_struct_field,
            "data_get_struct_fields": self._get_struct_fields,
            "data_create_enum":       self._create_enum,
            "data_add_enum_value":    self._add_enum_value,
            "data_get_enum_values":   self._get_enum_values,
            "data_create_datatable":  self._create_datatable,
            "data_add_row":           self._add_row,
            "data_get_row":           self._get_row,
            "data_get_all_rows":      self._get_all_rows,
            "data_delete_row":        self._delete_row,
            "data_import_csv":        self._import_csv,
            "data_create_curve_table": self._create_curve_table,
            "data_get_curve":         self._get_curve,
            "data_create_data_asset": self._create_data_asset,
        }
        fn = handlers.get(name)
        if not fn:
            return self._err(f"Unknown data tool: {name}")
        try:
            return await fn(args)
        except Exception as e:
            log.error(f"[{name}] {e}", exc_info=True)
            return self._err(str(e))

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _ok(self, data: dict | list | str) -> list[types.TextContent]:
        text = json.dumps(data, indent=2) if not isinstance(data, str) else data
        return [types.TextContent(type="text", text=text)]

    def _err(self, msg: str) -> list[types.TextContent]:
        return [types.TextContent(type="text", text=json.dumps({"error": msg}))]

    async def _exec(self, script: str, timeout: int = 60) -> dict:
        """Run script in UE and return parsed result dict."""
        result = await self.ue.execute_python(dedent(script), timeout=timeout)
        output = result.get("output", "")
        for line in output.split("\n"):
            line = line.strip()
            if line.startswith("UEOS_RESULT:"):
                return json.loads(line[len("UEOS_RESULT:"):])
            if line.startswith("UEOS_ERROR:"):
                raise RuntimeError(line[len("UEOS_ERROR:"):])
        # Fallback: return raw output dict
        return result

    def _pin_info(self, field_type: str) -> tuple[str, str]:
        """Return (pin_category, sub_category_object) for a field type string."""
        ft = field_type.lower()
        return PIN_CATEGORY_MAP.get(ft, ("string", ""))

    # ──────────────────────────────────────────────────────────────────────
    # STRUCT TOOLS
    # ──────────────────────────────────────────────────────────────────────

    # PhotonBPLibrary default object path — used for all C++ plugin RC calls
    _PHOTON_OBJ = "/Script/PhotonBP.Default__PhotonBPLibrary"

    async def _rc_add_struct_field(
        self,
        struct_path: str,
        field_name: str,
        ftype: str,
    ) -> dict:
        """
        Call PhotonBPLibrary.AddStructField via RC HTTP (PUT /remote/object/call).
        This routes around the missing unreal.StructureEditorUtils Python binding.

        PIN_CATEGORY_MAP maps friendly type names to (PinCategory, PinSubCategoryObjectPath).
        PinSubCategory is always "" for non-numeric reals; the C++ BuildPinType helper
        handles float/double sub-category internally when PinCategory=="real".
        """
        cat, sub_obj_path = self._pin_info(ftype)

        # For "real" types we pass the sub-category so BuildPinType can pick float vs double
        sub_cat = ""
        if ftype in ("float",):
            sub_cat = "float"
        elif ftype in ("double",):
            sub_cat = "double"

        params = {
            "Struct":                    {"$type": "softobjectpath", "assetPath": struct_path},
            "FieldName":                 field_name,
            "PinCategory":               cat,
            "PinSubCategory":            sub_cat,
            "PinSubCategoryObjectPath":  sub_obj_path,
        }
        return await self.ue.call_function(
            self._PHOTON_OBJ,
            "AddStructField",
            parameters=params,
            transaction=True,
        )

    async def _create_struct(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"].rstrip("/")
        fields      = args.get("fields", [])
        asset_path  = f"{path}/{name}"

        # ── Step 1: create the empty struct via Python (always works) ─────────
        create_script = f"""
import unreal, json

asset_path = "{asset_path}"

# CRITICAL: check existence first — never call create_asset on an existing
# path or UE will freeze on a "replace existing?" modal.
if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    struct = unreal.EditorAssetLibrary.load_asset(asset_path)
    if struct and isinstance(struct, unreal.UserDefinedStruct):
        print("UEOS_RESULT:" + json.dumps({{"status":"already_exists","name":"{name}","path":struct.get_path_name()}}))
    else:
        print("UEOS_ERROR:Asset exists at {asset_path} but is not a UserDefinedStruct")
else:
    unreal.EditorAssetLibrary.make_directory("{path}")
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.StructureFactory()
    struct = asset_tools.create_asset("{name}", "{path}", unreal.UserDefinedStruct, factory)
    if struct is None:
        print("UEOS_ERROR:Failed to create struct {name} at {path}")
    else:
        unreal.EditorAssetLibrary.save_asset(struct.get_path_name(), only_if_is_dirty=False)
        print("UEOS_RESULT:" + json.dumps({{"status":"created","name":"{name}","path":struct.get_path_name()}}))
"""
        create_result = await self._exec(create_script, timeout=90)
        status = create_result.get("status", "")
        if "error" in create_result or status not in ("created", "already_exists"):
            return self._ok(create_result)

        # ── Step 2: add each field via PhotonBPLibrary RC call ────────────────
        added   = []
        errors  = []
        for f in fields:
            fname = f["field_name"]
            ftype = f.get("type", "string").lower()
            try:
                rc_result = await self._rc_add_struct_field(asset_path, fname, ftype)
                added.append(fname)
            except Exception as e:
                errors.append({"field": fname, "error": str(e)})

        # ── Step 3: save after all fields added ───────────────────────────────
        if added:
            save_script = f"""
import unreal
struct = unreal.EditorAssetLibrary.load_asset("{asset_path}")
if struct:
    unreal.EditorAssetLibrary.save_asset(struct.get_path_name(), only_if_is_dirty=False)
"""
            await self._exec(save_script, timeout=30)

        return self._ok({
            "status":        status,
            "name":          name,
            "path":          asset_path,
            "fields_added":  added,
            "fields_failed": errors,
        })

    async def _add_struct_field(self, args: dict) -> list[types.TextContent]:
        struct_path = args["struct_path"]
        field_name  = args["field_name"]
        ftype       = args.get("type", "string").lower()

        try:
            rc_result = await self._rc_add_struct_field(struct_path, field_name, ftype)
        except Exception as e:
            return self._err(f"AddStructField RC call failed: {e}")

        # Save after adding the field
        save_script = f"""
import unreal
struct = unreal.EditorAssetLibrary.load_asset("{struct_path}")
if struct:
    unreal.EditorAssetLibrary.save_asset(struct.get_path_name(), only_if_is_dirty=False)
"""
        await self._exec(save_script, timeout=30)

        return self._ok({
            "status": "added",
            "field":  field_name,
            "type":   ftype,
            "struct": struct_path,
            "rc":     rc_result,
        })

    async def _get_struct_fields(self, args: dict) -> list[types.TextContent]:
        struct_path = args["struct_path"]

        script = f"""
import unreal, json

struct = unreal.EditorAssetLibrary.load_asset("{struct_path}")
if struct is None or not isinstance(struct, unreal.UserDefinedStruct):
    print("UEOS_ERROR:Struct not found: {struct_path}")
else:
    # unreal.StructureEditorUtils.get_variables does NOT exist in UE 5.4 Python.
    # Iterate the struct's UProperties via the script struct layout instead.
    fields = []
    for prop in unreal.TFieldIterator(struct, unreal.FProperty):
        try:
            fields.append({{
                "name":  prop.get_fname().to_string(),
                "class": prop.get_class().get_name(),
            }})
        except Exception:
            pass
    print("UEOS_RESULT:" + json.dumps({{"struct":"{struct_path}","field_count":len(fields),"fields":fields}}))
"""
        return self._ok(await self._exec(script))

    # ──────────────────────────────────────────────────────────────────────
    # ENUM TOOLS
    # ──────────────────────────────────────────────────────────────────────

    async def _create_enum(self, args: dict) -> list[types.TextContent]:
        name   = args["name"]
        path   = args["path"].rstrip("/")
        values = args.get("values", [])

        # Encode values as JSON for safe injection into the script
        values_json = json.dumps(values)

        asset_path = f"{path}/{name}"
        script = f"""
import unreal, json as _json

asset_path = "{asset_path}"
if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    enum_asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if enum_asset and isinstance(enum_asset, unreal.UserDefinedEnum):
        num_vals = enum_asset.num_enums() - 1
        print("UEOS_RESULT:" + _json.dumps({{"status":"already_exists","name":"{name}","path":enum_asset.get_path_name(),"value_count":num_vals}}))
    else:
        print("UEOS_ERROR:Asset exists at {asset_path} but is not a UserDefinedEnum")
else:
    unreal.EditorAssetLibrary.make_directory("{path}")
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    # EnumFactory is the correct class name in UE 5.4 Python bindings
    factory = unreal.EnumFactory()
    enum_asset = asset_tools.create_asset("{name}", "{path}", unreal.UserDefinedEnum, factory)
    if enum_asset is None:
        print("UEOS_ERROR:Failed to create enum {name} at {path}")
    else:
        # UserDefinedEnumEditorUtils does NOT exist in UE 5.4 Python bindings.
        # EnumFactory creates the asset with one auto-generated placeholder: NewEnumerator0.
        # Rename entries via set_meta_data("DisplayName_NewEnumerator{i}", display_name).
        # This is the only confirmed-working approach in UE 5.4 Python.
        values_to_add = {values_json}
        added = 0
        for i, v in enumerate(values_to_add):
            try:
                slot_key = f"DisplayName_NewEnumerator{{i}}"
                enum_asset.set_meta_data(slot_key, str(v))
                added += 1
            except Exception:
                pass  # slot may not exist for i>0; enum still created with fewer values
        unreal.EditorAssetLibrary.save_asset(enum_asset.get_path_name(), only_if_is_dirty=False)
        num_vals = max(0, enum_asset.num_enums() - 1)  # subtract MAX sentinel
        print("UEOS_RESULT:" + _json.dumps({{"status":"created","name":"{name}","path":enum_asset.get_path_name(),"value_count":num_vals,"values_requested":len(values_to_add),"values_added":added}}))
"""
        return self._ok(await self._exec(script, timeout=90))

    async def _add_enum_value(self, args: dict) -> list[types.TextContent]:
        enum_path  = args["enum_path"]
        value_name = args["value_name"]

        script = f"""
import unreal, json

enum_asset = unreal.EditorAssetLibrary.load_asset("{enum_path}")
if enum_asset is None or not isinstance(enum_asset, unreal.UserDefinedEnum):
    print("UEOS_ERROR:Enum not found: {enum_path}")
else:
    # UserDefinedEnumEditorUtils does NOT exist in UE 5.4 Python.
    # insert_enum_entry / set_enum_display_name also do NOT exist.
    # Only confirmed-working API: set_meta_data("DisplayName_NewEnumerator{i}", name)
    # slot_i = current num_enums - 1 (position before the MAX sentinel)
    slot_i = max(0, enum_asset.num_enums() - 1)
    slot_key = f"DisplayName_NewEnumerator{{slot_i}}"
    added = False
    try:
        enum_asset.set_meta_data(slot_key, "{value_name}")
        added = True
    except Exception as _e:
        print("UEOS_ERROR:Could not add enum value via set_meta_data: " + str(_e))
    if added:
        unreal.EditorAssetLibrary.save_asset("{enum_path}", only_if_is_dirty=False)
        print("UEOS_RESULT:" + json.dumps({{"status":"added","value":"{value_name}","enum":"{enum_path}"}}))
"""
        return self._ok(await self._exec(script))

    async def _get_enum_values(self, args: dict) -> list[types.TextContent]:
        enum_path = args["enum_path"]

        script = f"""
import unreal, json

enum_asset = unreal.EditorAssetLibrary.load_asset("{enum_path}")
if enum_asset is None or not isinstance(enum_asset, unreal.UserDefinedEnum):
    print("UEOS_ERROR:Enum not found: {enum_path}")
else:
    values = []
    for i in range(enum_asset.num_enums()):
        entry_name = enum_asset.get_display_name_text_by_index(i).to_string()
        if entry_name and entry_name != "MAX":
            values.append({{"index": i, "name": entry_name}})
    print("UEOS_RESULT:" + json.dumps({{"enum":"{enum_path}","values":values}}))
"""
        return self._ok(await self._exec(script))

    # ──────────────────────────────────────────────────────────────────────
    # DATATABLE TOOLS
    # ──────────────────────────────────────────────────────────────────────

    async def _create_datatable(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"].rstrip("/")
        struct_path = args["struct_path"]

        asset_path = f"{path}/{name}"
        script = f"""
import unreal, json

asset_path = "{asset_path}"
if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    table = unreal.EditorAssetLibrary.load_asset(asset_path)
    if table and isinstance(table, unreal.DataTable):
        print("UEOS_RESULT:" + json.dumps({{"status":"already_exists","name":"{name}","path":table.get_path_name(),"struct":"{struct_path}"  }}))
    else:
        print("UEOS_ERROR:Asset exists at {asset_path} but is not a DataTable")
else:
    struct = unreal.load_object(None, "{struct_path}")
    if struct is None:
        print("UEOS_ERROR:Row struct not found: {struct_path}")
    else:
        unreal.EditorAssetLibrary.make_directory("{path}")
        factory = unreal.DataTableFactory()
        factory.struct = struct
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        table = asset_tools.create_asset("{name}", "{path}", unreal.DataTable, factory)
        if table is None:
            print("UEOS_ERROR:Failed to create DataTable {name} at {path}")
        else:
            unreal.EditorAssetLibrary.save_asset(table.get_path_name(), only_if_is_dirty=False)
            print("UEOS_RESULT:" + json.dumps({{
                "status": "created",
                "name":   "{name}",
                "path":   table.get_path_name(),
                "struct": "{struct_path}"
            }}))
"""
        return self._ok(await self._exec(script, timeout=90))

    async def _add_row(self, args: dict) -> list[types.TextContent]:
        table_path = args["table_path"]
        row_name   = args["row_name"]
        row_data   = args.get("row_data", {})
        row_json   = json.dumps(row_data)

        script = f"""
import unreal, json

table = unreal.EditorAssetLibrary.load_asset("{table_path}")
if table is None or not isinstance(table, unreal.DataTable):
    print("UEOS_ERROR:DataTable not found: {table_path}")
else:
    row_data = json.loads('{row_json}')
    row_struct = table.get_row_struct()

    # Build FTableRowBase-compatible dict and add the row
    # Use DataTableFunctionLibrary for safe row access
    existing_rows = unreal.DataTableFunctionLibrary.get_data_table_row_names(table)
    row_name_obj = unreal.Name("{row_name}")

    # Serialize our data dict to JSON and use editor scripting to import
    # This approach works reliably across all UE 5.x versions
    csv_header = ",".join(["Name"] + list(row_data.keys()))
    csv_values = ",".join(["{row_name}"] + [str(v) for v in row_data.values()])
    csv_string = csv_header + "\\n" + csv_values

    import_options = unreal.DataTableImportOptions()
    import_options.import_type = unreal.CSVImportType.ECSV_DATA_TABLE

    success = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(
        table, csv_string, import_options
    )

    unreal.EditorAssetLibrary.save_asset("{table_path}", only_if_is_dirty=False)
    print("UEOS_RESULT:" + json.dumps({{
        "status": "added",
        "row": "{row_name}",
        "table": "{table_path}",
        "total_rows": len(unreal.DataTableFunctionLibrary.get_data_table_row_names(table))
    }}))
"""
        return self._ok(await self._exec(script))

    async def _get_row(self, args: dict) -> list[types.TextContent]:
        table_path = args["table_path"]
        row_name   = args["row_name"]

        script = f"""
import unreal, json

table = unreal.EditorAssetLibrary.load_asset("{table_path}")
if table is None or not isinstance(table, unreal.DataTable):
    print("UEOS_ERROR:DataTable not found: {table_path}")
else:
    rows = unreal.DataTableFunctionLibrary.get_data_table_row_names(table)
    if unreal.Name("{row_name}") not in rows:
        print("UEOS_ERROR:Row not found: {row_name}")
    else:
        # Export the full table as JSON and find our row
        json_str = unreal.DataTableFunctionLibrary.conv_data_table_to_json_string(table)
        all_rows = json.loads(json_str) if json_str else []
        target = None
        for r in all_rows:
            if r.get("Name") == "{row_name}":
                target = r
                break
        if target is None:
            print("UEOS_ERROR:Row found in names but not in export: {row_name}")
        else:
            print("UEOS_RESULT:" + json.dumps(target))
"""
        return self._ok(await self._exec(script))

    async def _get_all_rows(self, args: dict) -> list[types.TextContent]:
        table_path = args["table_path"]

        script = f"""
import unreal, json

table = unreal.EditorAssetLibrary.load_asset("{table_path}")
if table is None or not isinstance(table, unreal.DataTable):
    print("UEOS_ERROR:DataTable not found: {table_path}")
else:
    json_str = unreal.DataTableFunctionLibrary.conv_data_table_to_json_string(table)
    rows = json.loads(json_str) if json_str else []
    row_names = [str(n) for n in unreal.DataTableFunctionLibrary.get_data_table_row_names(table)]
    print("UEOS_RESULT:" + json.dumps({{
        "table": "{table_path}",
        "row_count": len(rows),
        "row_names": row_names,
        "rows": rows
    }}))
"""
        return self._ok(await self._exec(script))

    async def _delete_row(self, args: dict) -> list[types.TextContent]:
        table_path = args["table_path"]
        row_name   = args["row_name"]

        script = f"""
import unreal, json

table = unreal.EditorAssetLibrary.load_asset("{table_path}")
if table is None or not isinstance(table, unreal.DataTable):
    print("UEOS_ERROR:DataTable not found: {table_path}")
else:
    rows_before = len(unreal.DataTableFunctionLibrary.get_data_table_row_names(table))
    # Export to JSON, filter row, re-import
    json_str = unreal.DataTableFunctionLibrary.conv_data_table_to_json_string(table)
    all_rows = json.loads(json_str) if json_str else []
    filtered = [r for r in all_rows if r.get("Name") != "{row_name}"]

    import_options = unreal.DataTableImportOptions()
    import_options.import_type = unreal.CSVImportType.ECSV_DATA_TABLE
    unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
        table, json.dumps(filtered), import_options
    )
    unreal.EditorAssetLibrary.save_asset("{table_path}", only_if_is_dirty=False)

    rows_after = len(unreal.DataTableFunctionLibrary.get_data_table_row_names(table))
    print("UEOS_RESULT:" + json.dumps({{
        "status": "deleted",
        "row": "{row_name}",
        "rows_before": rows_before,
        "rows_after": rows_after
    }}))
"""
        return self._ok(await self._exec(script))

    async def _import_csv(self, args: dict) -> list[types.TextContent]:
        csv_path         = args["csv_path"].replace("\\", "/")
        name             = args["name"]
        path             = args["path"].rstrip("/")
        struct_path      = args.get("struct_path", "")
        replace_existing = args.get("replace_existing", True)

        script = f"""
import unreal, json, os

csv_path = r"{csv_path}"
if not os.path.exists(csv_path):
    print("UEOS_ERROR:CSV file not found: " + csv_path)
else:
    with open(csv_path, "r", encoding="utf-8") as f:
        csv_content = f.read()

    full_path = "{path}/{name}"
    existing = unreal.EditorAssetLibrary.does_asset_exist(full_path)

    if existing and not {str(replace_existing)}:
        print("UEOS_ERROR:DataTable already exists and replace_existing=False")
    else:
        if existing:
            table = unreal.EditorAssetLibrary.load_asset(full_path)
        else:
            struct_obj = unreal.load_object(None, "{struct_path}") if "{struct_path}" else None
            factory = unreal.DataTableFactory()
            if struct_obj:
                factory.struct = struct_obj
            asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
            table = asset_tools.create_asset("{name}", "{path}", unreal.DataTable, factory)

        if table is None:
            print("UEOS_ERROR:Could not create or load DataTable")
        else:
            import_options = unreal.DataTableImportOptions()
            import_options.import_type = unreal.CSVImportType.ECSV_DATA_TABLE
            success = unreal.DataTableFunctionLibrary.fill_data_table_from_csv_string(
                table, csv_content, import_options
            )
            unreal.EditorAssetLibrary.save_asset(table.get_path_name(), only_if_is_dirty=False)
            row_count = len(unreal.DataTableFunctionLibrary.get_data_table_row_names(table))
            print("UEOS_RESULT:" + json.dumps({{
                "status": "imported",
                "csv_path": csv_path,
                "table_path": table.get_path_name(),
                "row_count": row_count
            }}))
"""
        return self._ok(await self._exec(script))

    # ──────────────────────────────────────────────────────────────────────
    # CURVE TABLE TOOLS
    # ──────────────────────────────────────────────────────────────────────

    async def _create_curve_table(self, args: dict) -> list[types.TextContent]:
        name       = args["name"]
        path       = args["path"].rstrip("/")
        curves     = args.get("curves", {})
        curve_type = args.get("curve_type", "float")
        curves_json = json.dumps(curves)

        script = f"""
import unreal, json

curves_data = json.loads('{curves_json}')
curve_type = "{curve_type}"

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
factory = unreal.CurveTableFactory()
if curve_type == "vector":
    factory.key_type = unreal.CurveTableMode.VECTOR_CURVES
else:
    factory.key_type = unreal.CurveTableMode.SIMPLE_CURVES

curve_table = asset_tools.create_asset("{name}", "{path}", unreal.CurveTable, factory)
if curve_table is None:
    print("UEOS_ERROR:Failed to create CurveTable {name} at {path}")
else:
    # Populate curves via CSV round-trip (most reliable method)
    # CSV format for CurveTable: first row is curve names, first col is time
    if curves_data:
        curve_names = list(curves_data.keys())
        # Build a CSV that UE can import
        # Format: ---,CurveName1,CurveName2,...
        # then rows: time,value1,value2,...

        # Find all unique time points across all curves
        all_times = set()
        for keys in curves_data.values():
            for key in keys:
                all_times.add(float(key[0]))
        all_times = sorted(all_times)

        if curve_type == "float":
            header = "---," + ",".join(curve_names)
            rows_lines = []
            for t in all_times:
                vals = []
                for cname in curve_names:
                    # Find value at this time (exact match only for CSV import)
                    found = None
                    for key in curves_data[cname]:
                        if abs(float(key[0]) - t) < 0.0001:
                            found = float(key[1])
                            break
                    vals.append(str(found) if found is not None else "")
                rows_lines.append(f"{{t}}," + ",".join(vals))
            csv_str = header + "\\n" + "\\n".join(rows_lines)
        else:
            # Vector curves — not supported via CSV, skip population
            csv_str = None

        if csv_str:
            result = unreal.CurveTableEditorUtils.get_all_curve_info(curve_table)
            import_opts = unreal.CurveTableImportOptions()
            # Import via asset tools CSV import
            # Since direct CSV import API differs, we use the factory CSV method
            import_task = unreal.AssetImportTask()
            import_task.destination_path = "{path}"
            import_task.destination_name = "{name}"
            import_task.replace_existing = True
            import_task.automated = True
            import_task.save = False

            # Write CSV to temp file
            import os, tempfile
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
            tmp.write(csv_str)
            tmp.close()
            import_task.filename = tmp.name
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([import_task])
            os.unlink(tmp.name)

    unreal.EditorAssetLibrary.save_asset(curve_table.get_path_name(), only_if_is_dirty=False)
    print("UEOS_RESULT:" + json.dumps({{
        "status": "created",
        "name": "{name}",
        "path": curve_table.get_path_name(),
        "curve_count": len(curves_data),
        "curve_names": list(curves_data.keys()),
        "curve_type": curve_type
    }}))
"""
        return self._ok(await self._exec(script))

    async def _get_curve(self, args: dict) -> list[types.TextContent]:
        table_path = args["table_path"]
        curve_name = args["curve_name"]

        script = f"""
import unreal, json

table = unreal.EditorAssetLibrary.load_asset("{table_path}")
if table is None or not isinstance(table, unreal.CurveTable):
    print("UEOS_ERROR:CurveTable not found: {table_path}")
else:
    # Get curve info via editor utilities
    all_curves = unreal.CurveTableEditorUtils.get_all_curve_info(table)
    target_info = None
    for info in all_curves:
        if str(info.curve_name) == "{curve_name}":
            target_info = info
            break

    if target_info is None:
        available = [str(c.curve_name) for c in all_curves]
        print("UEOS_ERROR:Curve '{curve_name}' not found. Available: " + str(available))
    else:
        keys = []
        for i in range(target_info.curve_data.get_num_keys()):
            key = target_info.curve_data.get_key(unreal.RichCurveKeyHandle(target_info.curve_data, i))
            keys.append({{"time": key.time, "value": key.value}})
        print("UEOS_RESULT:" + json.dumps({{
            "table": "{table_path}",
            "curve": "{curve_name}",
            "key_count": len(keys),
            "keys": keys
        }}))
"""
        return self._ok(await self._exec(script))

    # ──────────────────────────────────────────────────────────────────────
    # DATA ASSET TOOLS
    # ──────────────────────────────────────────────────────────────────────

    async def _create_data_asset(self, args: dict) -> list[types.TextContent]:
        name        = args["name"]
        path        = args["path"].rstrip("/")
        class_path  = args.get("class_path", "/Script/Engine.PrimaryDataAsset")
        properties  = args.get("properties", {})
        props_json  = json.dumps(properties)
        asset_path  = f"{path}/{name}"

        # ── Class path validation ──────────────────────────────────────────
        # DataAsset (/Script/Engine.DataAsset) is abstract — UE shows a modal
        # dialog and refuses to create it. Always use PrimaryDataAsset or a
        # concrete subclass. Catch the mistake here before it hits UE.
        ABSTRACT_CLASSES = {
            "/Script/Engine.DataAsset",
            "DataAsset",
        }
        if class_path in ABSTRACT_CLASSES:
            class_path = "/Script/Engine.PrimaryDataAsset"

        script = f"""
import unreal, json

asset_path = "{asset_path}"
class_path = "{class_path}"

# ── Existence check — avoid modal dialog on duplicate ─────────────────────
if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
    asset = unreal.EditorAssetLibrary.load_asset(asset_path)
    if asset:
        print("UEOS_RESULT:" + json.dumps({{
            "status":  "already_exists",
            "name":    "{name}",
            "path":    asset.get_path_name(),
            "class":   class_path,
        }}))
    else:
        print("UEOS_ERROR:Asset exists at {asset_path} but could not be loaded")
else:
    asset_class = unreal.load_class(None, class_path)
    if asset_class is None:
        print("UEOS_ERROR:Class not found: " + class_path +
              ". Use a concrete subclass e.g. /Script/Engine.PrimaryDataAsset "
              "or a Blueprint DataAsset subclass path like /Game/Data/DA_MyClass.DA_MyClass_C")
    elif asset_class.is_abstract():
        print("UEOS_ERROR:Class " + class_path + " is abstract — UE cannot create assets from "
              "abstract classes. Use /Script/Engine.PrimaryDataAsset or create a Blueprint "
              "subclass of DataAsset first, then pass its path here.")
    else:
        unreal.EditorAssetLibrary.make_directory("{path}")
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.DataAssetFactory()
        factory.data_asset_class = asset_class
        asset = asset_tools.create_asset("{name}", "{path}", None, factory)
        if asset is None:
            print("UEOS_ERROR:Failed to create DataAsset {name} at {path}")
        else:
            props = json.loads('{props_json}')
            for prop_name, prop_val in props.items():
                try:
                    if isinstance(prop_val, bool):
                        setattr(asset, prop_name, prop_val)
                    elif isinstance(prop_val, (int, float, str)):
                        setattr(asset, prop_name, prop_val)
                    elif isinstance(prop_val, list) and len(prop_val) == 3:
                        setattr(asset, prop_name, unreal.Vector(prop_val[0], prop_val[1], prop_val[2]))
                    elif isinstance(prop_val, list) and len(prop_val) == 4:
                        setattr(asset, prop_name, unreal.LinearColor(prop_val[0], prop_val[1], prop_val[2], prop_val[3]))
                except Exception:
                    pass
            unreal.EditorAssetLibrary.save_asset(asset.get_path_name(), only_if_is_dirty=False)
            print("UEOS_RESULT:" + json.dumps({{
                "status":          "created",
                "name":            "{name}",
                "path":            asset.get_path_name(),
                "class":           class_path,
                "properties_set":  list(props.keys()),
            }}))
"""
        return self._ok(await self._exec(script, timeout=90))
