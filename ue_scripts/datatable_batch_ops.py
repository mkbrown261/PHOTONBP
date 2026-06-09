"""
UEOS Utility Script — DataTable Batch Operations
Runs INSIDE Unreal Engine 5.4 via Remote Control execute_python.

Supports:
  - Merging two DataTables into one
  - Exporting a DataTable to JSON or CSV on disk
  - Importing rows from a Python dict list
  - Searching rows by field value

Configure via globals:

    UEOS_DT_OP       = "export_json"   # or "merge", "search", "import_rows"
    UEOS_TABLE_PATH  = "/Game/Data/DT_Characters"
    ...
"""

import unreal, json, os

OP          = globals().get("UEOS_DT_OP",      "dump")
TABLE_PATH  = globals().get("UEOS_TABLE_PATH", "")
TABLE_PATH2 = globals().get("UEOS_TABLE_PATH2","")  # for merge
OUTPUT_PATH = globals().get("UEOS_OUTPUT_PATH","")  # for export
ROWS        = globals().get("UEOS_ROWS",       [])  # for import_rows
SEARCH_FIELD = globals().get("UEOS_SEARCH_FIELD","")
SEARCH_VALUE = globals().get("UEOS_SEARCH_VALUE","")

try:
    # ── Helpers ───────────────────────────────────────────────────────────────
    def load_table(path):
        t = unreal.EditorAssetLibrary.load_asset(path)
        if t is None or not isinstance(t, unreal.DataTable):
            raise ValueError(f"DataTable not found: {path}")
        return t

    def get_rows_json(table):
        s = unreal.DataTableFunctionLibrary.conv_data_table_to_json_string(table)
        return json.loads(s) if s else []

    # ── Operations ────────────────────────────────────────────────────────────

    if OP == "dump":
        table = load_table(TABLE_PATH)
        rows = get_rows_json(table)
        names = [str(n) for n in unreal.DataTableFunctionLibrary.get_data_table_row_names(table)]
        print("UEOS_RESULT:" + json.dumps({
            "table": TABLE_PATH, "row_count": len(rows),
            "row_names": names, "rows": rows
        }))

    elif OP == "export_json":
        table = load_table(TABLE_PATH)
        rows  = get_rows_json(table)
        if OUTPUT_PATH:
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2)
        print("UEOS_RESULT:" + json.dumps({
            "status": "exported", "row_count": len(rows),
            "output_path": OUTPUT_PATH or "stdout"
        }))

    elif OP == "export_csv":
        table = load_table(TABLE_PATH)
        rows  = get_rows_json(table)
        if rows:
            headers = list(rows[0].keys())
            lines   = [",".join(headers)]
            for row in rows:
                lines.append(",".join(str(row.get(h, "")) for h in headers))
            csv_str = "\n".join(lines)
            if OUTPUT_PATH:
                os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
                with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                    f.write(csv_str)
        print("UEOS_RESULT:" + json.dumps({"status": "exported", "output_path": OUTPUT_PATH}))

    elif OP == "merge":
        t1   = load_table(TABLE_PATH)
        t2   = load_table(TABLE_PATH2)
        rows1 = get_rows_json(t1)
        rows2 = get_rows_json(t2)

        # Merge: rows from t2 override rows1 if same Name
        combined = {r["Name"]: r for r in rows1}
        combined.update({r["Name"]: r for r in rows2})
        merged_rows = list(combined.values())

        import_opts = unreal.DataTableImportOptions()
        import_opts.import_type = unreal.CSVImportType.ECSV_DATA_TABLE
        unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
            t1, json.dumps(merged_rows), import_opts
        )
        unreal.EditorAssetLibrary.save_asset(TABLE_PATH, only_if_is_dirty=False)
        print("UEOS_RESULT:" + json.dumps({
            "status": "merged", "rows_t1": len(rows1), "rows_t2": len(rows2),
            "total": len(merged_rows), "result_table": TABLE_PATH
        }))

    elif OP == "import_rows":
        table = load_table(TABLE_PATH)
        existing = get_rows_json(table)
        existing_map = {r["Name"]: r for r in existing}
        for row in ROWS:
            row_name = row.get("Name", row.get("name", ""))
            if not row_name:
                continue
            d = dict(row)
            d["Name"] = row_name
            existing_map[row_name] = d
        new_rows = list(existing_map.values())
        import_opts = unreal.DataTableImportOptions()
        import_opts.import_type = unreal.CSVImportType.ECSV_DATA_TABLE
        unreal.DataTableFunctionLibrary.fill_data_table_from_json_string(
            table, json.dumps(new_rows), import_opts
        )
        unreal.EditorAssetLibrary.save_asset(TABLE_PATH, only_if_is_dirty=False)
        print("UEOS_RESULT:" + json.dumps({
            "status": "imported", "rows_added_or_updated": len(ROWS), "total": len(new_rows)
        }))

    elif OP == "search":
        table = load_table(TABLE_PATH)
        rows  = get_rows_json(table)
        found = []
        for row in rows:
            val = row.get(SEARCH_FIELD)
            if val is None:
                continue
            if str(val).lower() == str(SEARCH_VALUE).lower():
                found.append(row)
        print("UEOS_RESULT:" + json.dumps({
            "field": SEARCH_FIELD, "value": SEARCH_VALUE,
            "matches": len(found), "rows": found
        }))

    else:
        print(f"UEOS_ERROR:Unknown operation: {OP}. Valid: dump/export_json/export_csv/merge/import_rows/search")

except Exception as ex:
    import traceback
    print("UEOS_ERROR:" + traceback.format_exc().replace("\n", " | "))
