"""
UEOS Search Tools — UE 5.4 Semantic Asset Search + Blueprint Thumbnail Vision

Natural-language asset discovery powered by the UE Remote Control HTTP API:
  PUT /remote/search/assets   — text search with class/path filters
  PUT /remote/object/thumbnail — Content Browser thumbnail for any asset path

Three tools:
  search_assets          — find assets by natural language ("find buildings, roads")
  search_get_thumbnail   — get a Content Browser thumbnail as a base64 image
  search_list_folder     — list all assets in a folder with optional class filter

The alias table maps game-design vocabulary to search terms so Claude can say
"find a stop sign" and get results even if the asset is named "SM_StopSign_01".
"""

import base64
import json
import logging
from mcp import types

log = logging.getLogger("ueos.search")


# ─────────────────────────────────────────────────────────────────────────────
# Alias / synonym table
# Maps user vocabulary → list of search terms to try
# ─────────────────────────────────────────────────────────────────────────────

ALIASES: dict[str, list[str]] = {
    # ── Urban / city ──────────────────────────────────────────────────────────
    "building":       ["building", "house", "structure", "warehouse", "office",
                       "shop", "store", "skyscraper", "tower", "apartment"],
    "road":           ["road", "street", "path", "lane", "asphalt", "highway",
                       "avenue", "pavement", "sidewalk", "curb"],
    "intersection":   ["intersection", "crossroad", "crossing", "junction"],
    "sidewalk":       ["sidewalk", "pavement", "walkway", "footpath"],
    "city block":     ["city", "block", "urban", "downtown", "street"],
    "parking lot":    ["parking", "lot", "carpark"],
    "fence":          ["fence", "barrier", "wall", "railing", "gate"],
    "wall":           ["wall", "barrier", "concrete", "brick"],
    "alley":          ["alley", "alleyway", "backstreet"],
    "lamp":           ["lamp", "light", "streetlight", "lantern", "lamppost"],
    "streetlight":    ["streetlight", "lamp", "light", "lantern", "pole"],
    "fire hydrant":   ["hydrant", "firehydrant", "fire_hydrant"],
    "mailbox":        ["mailbox", "mail", "postbox"],
    "bench":          ["bench", "seat", "seating"],
    "bus stop":       ["busstop", "bus_stop", "shelter", "transit"],
    "trash":          ["trash", "garbage", "bin", "can", "dumpster", "waste"],
    "dumpster":       ["dumpster", "trash", "bin", "container"],
    "manhole":        ["manhole", "sewer", "grate", "drain"],
    "billboard":      ["billboard", "sign", "advertisement", "ad"],
    # ── Traffic / signs ───────────────────────────────────────────────────────
    "stop sign":      ["stop", "sign", "stopsign", "stop_sign"],
    "traffic light":  ["traffic", "light", "signal", "trafficlight",
                       "traffic_light", "stoplight"],
    "sign":           ["sign", "signage", "placard", "notice"],
    "cone":           ["cone", "traffic_cone", "barrier", "pylon"],
    "barrier":        ["barrier", "cone", "bollard", "blockade"],
    "bollard":        ["bollard", "post", "barrier"],
    # ── Vehicles ──────────────────────────────────────────────────────────────
    "car":            ["car", "vehicle", "automobile", "sedan", "coupe"],
    "truck":          ["truck", "lorry", "vehicle"],
    "bus":            ["bus", "vehicle", "transit"],
    "bicycle":        ["bicycle", "bike", "cycle"],
    "motorcycle":     ["motorcycle", "motorbike", "bike"],
    # ── Nature / environment ──────────────────────────────────────────────────
    "tree":           ["tree", "plant", "foliage", "bush", "shrub", "oak",
                       "pine", "palm"],
    "bush":           ["bush", "shrub", "plant", "hedge"],
    "rock":           ["rock", "stone", "boulder", "pebble"],
    "grass":          ["grass", "lawn", "ground", "terrain"],
    "flower":         ["flower", "plant", "bloom", "garden"],
    "water":          ["water", "river", "lake", "pond", "fountain", "pool"],
    # ── Interiors ─────────────────────────────────────────────────────────────
    "door":           ["door", "doorway", "entrance", "gate"],
    "window":         ["window", "glass", "pane"],
    "stairs":         ["stairs", "staircase", "steps", "ladder"],
    "chair":          ["chair", "seat", "stool"],
    "table":          ["table", "desk", "surface"],
    "sofa":           ["sofa", "couch", "settee"],
    "shelf":          ["shelf", "rack", "shelving"],
    "cabinet":        ["cabinet", "cupboard", "locker"],
    "bed":            ["bed", "mattress", "bunk"],
    "lamp post":      ["lamppost", "lamp", "light", "pole"],
    # ── Weapons / gameplay props ───────────────────────────────────────────────
    "weapon":         ["weapon", "gun", "rifle", "pistol", "sword", "axe"],
    "pickup":         ["pickup", "collectible", "item", "powerup"],
    "chest":          ["chest", "crate", "box", "container"],
    "crate":          ["crate", "box", "container", "chest"],
    # ── Sci-fi / industrial ────────────────────────────────────────────────────
    "pipe":           ["pipe", "tube", "duct", "conduit"],
    "tank":           ["tank", "barrel", "drum", "silo"],
    "barrel":         ["barrel", "drum", "container", "oil"],
    "cable":          ["cable", "wire", "cord", "line"],
    "generator":      ["generator", "machine", "industrial"],
    "crate stack":    ["crate", "stack", "storage", "box"],
    # ── Characters / creatures ────────────────────────────────────────────────
    "character":      ["character", "person", "human", "npc", "player",
                       "mannequin", "figure"],
    "enemy":          ["enemy", "monster", "creature", "npc", "villain"],
    "animal":         ["animal", "creature", "beast", "wolf", "bear", "bird"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ─────────────────────────────────────────────────────────────────────────────

def _expand_query(query: str) -> list[str]:
    """
    Expand a natural-language query into a list of search terms.
    Checks every alias key for substring matches, returns all associated terms
    plus the original words.
    """
    q_lower = query.lower()
    terms: list[str] = []

    # Check every alias key
    for key, synonyms in ALIASES.items():
        if key in q_lower:
            terms.extend(synonyms)

    # Also add the raw words from the query (split on spaces / punctuation)
    import re
    raw_words = re.split(r"[\s,;.!?/\\]+", q_lower)
    terms.extend(w for w in raw_words if len(w) > 2)

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def _score_asset(asset: dict, terms: list[str]) -> int:
    """
    Score an asset result by how many search terms appear in its name or path.
    Higher = better match. Used to sort results.
    """
    name  = (asset.get("Name", "") or "").lower()
    path  = (asset.get("Path", "") or asset.get("PackageName", "") or "").lower()
    haystack = name + " " + path
    score = 0
    for term in terms:
        if term in haystack:
            score += 2 if term in name else 1
    return score


# ─────────────────────────────────────────────────────────────────────────────
# SearchTools
# ─────────────────────────────────────────────────────────────────────────────

class SearchTools:

    def __init__(self, ue):
        self.ue = ue

    # ──────────────────────────────────────────────────────────────────────────
    # Tool definitions
    # ──────────────────────────────────────────────────────────────────────────

    async def get_tool_definitions(self) -> list[types.Tool]:
        return [

            types.Tool(
                name="search_assets",
                description=(
                    "Semantic asset search. Find UE project assets using natural language.\n"
                    "Examples:\n"
                    "  'find buildings, roads, and stop signs for a city block'\n"
                    "  'search for traffic lights and bollards'\n"
                    "  'find all static meshes in /Game/Environment'\n\n"
                    "The tool expands game-design vocabulary (building, road, stop sign, tree, etc.) "
                    "to relevant search terms and ranks results by relevance.\n"
                    "Returns: name, class, path, and relevance score for each match.\n"
                    "Use search_get_thumbnail after this to visually confirm assets."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Natural language description of what to find. "
                                "E.g. 'buildings and roads for a city block', "
                                "'stop sign', 'traffic light', 'trees and rocks'"
                            )
                        },
                        "class_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional UE class filter. E.g. ['StaticMesh'], "
                                "['Blueprint'], ['StaticMesh', 'SkeletalMesh']. "
                                "Leave empty to search all asset types."
                            ),
                            "default": []
                        },
                        "package_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional content paths to restrict search. "
                                "E.g. ['/Game/Environment'], ['/Game']. "
                                "Leave empty to search all of /Game."
                            ),
                            "default": []
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Search sub-folders recursively",
                            "default": True
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 20)",
                            "default": 20
                        }
                    },
                    "required": ["query"]
                }
            ),

            types.Tool(
                name="search_get_thumbnail",
                description=(
                    "Get the Content Browser thumbnail for any UE asset as an inline image.\n"
                    "Use this after search_assets to visually confirm an asset looks right "
                    "before using it (e.g. before placing a city block mesh).\n"
                    "Also works for Blueprints — shows the Blueprint icon or component preview.\n"
                    "Returns an inline image Claude can see directly."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {
                            "type": "string",
                            "description": (
                                "Full content path to the asset. "
                                "E.g. /Game/Environment/SM_Building_01"
                            )
                        }
                    },
                    "required": ["asset_path"]
                }
            ),

            types.Tool(
                name="search_list_folder",
                description=(
                    "List all assets in a content folder, optionally filtered by class.\n"
                    "Faster than search_assets when you know the exact folder.\n"
                    "Returns: name, class, path for every asset found.\n\n"
                    "Examples:\n"
                    "  folder='/Game/Environment', filter_class='StaticMesh'\n"
                    "  folder='/Game/Blueprints', filter_class='Blueprint'\n"
                    "  folder='/Game/Characters' (no filter = all types)"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "folder": {
                            "type": "string",
                            "description": "Content path to folder. E.g. /Game/Environment"
                        },
                        "filter_class": {
                            "type": "string",
                            "description": (
                                "Optional class name to filter by. "
                                "E.g. StaticMesh, Blueprint, Material, Texture2D. "
                                "Leave empty for all types."
                            ),
                            "default": ""
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Search sub-folders recursively",
                            "default": True
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results to return (default 50)",
                            "default": 50
                        }
                    },
                    "required": ["folder"]
                }
            ),

        ]

    # ──────────────────────────────────────────────────────────────────────────
    # Handler dispatch
    # ──────────────────────────────────────────────────────────────────────────

    async def handle(self, name: str, args: dict):
        handlers = {
            "search_assets":        self._search_assets,
            "search_get_thumbnail": self._search_get_thumbnail,
            "search_list_folder":   self._search_list_folder,
        }
        handler = handlers.get(name)
        if not handler:
            return [types.TextContent(type="text",
                text=json.dumps({"error": f"Unknown search tool: {name}"}))]
        return await handler(args)

    # ──────────────────────────────────────────────────────────────────────────
    # search_assets
    # ──────────────────────────────────────────────────────────────────────────

    async def _search_assets(self, args: dict):
        query        = args["query"]
        class_names  = args.get("class_names", [])
        package_paths = args.get("package_paths", [])
        recursive    = args.get("recursive", True)
        max_results  = args.get("max_results", 20)

        # Expand natural language to search terms
        terms = _expand_query(query)
        log.info(f"search_assets: query={query!r} → terms={terms[:8]}")

        # We run one RC search per term and aggregate results.
        # The RC /remote/search/assets endpoint does prefix/substring matching
        # on the asset name — we'll fan-out to the top 4 most specific terms
        # and deduplicate by path.

        all_assets: dict[str, dict] = {}  # path → asset dict

        # Use up to 4 terms to keep round-trips bounded.
        # Prefer longer terms (more specific).
        search_terms = sorted(terms, key=len, reverse=True)[:4]

        for term in search_terms:
            try:
                results = await self.ue.search_assets(
                    query        = term,
                    class_names  = class_names,
                    package_paths = package_paths if package_paths else ["/Game"],
                    recursive    = recursive,
                )
                for asset in results:
                    path = asset.get("Path") or asset.get("PackageName") or ""
                    if path and path not in all_assets:
                        all_assets[path] = asset
            except Exception as e:
                log.warning(f"search_assets term={term!r} failed: {e}")
                continue

        if not all_assets:
            # Fallback: use AssetRegistry via Python bridge
            log.info("RC search returned nothing — falling back to Python bridge")
            return await self._fallback_search(query, terms, class_names,
                                               package_paths, recursive, max_results)

        # Score and sort
        assets_list = list(all_assets.values())
        scored = [(a, _score_asset(a, terms)) for a in assets_list]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Format output
        top = scored[:max_results]
        output_assets = []
        for asset, score in top:
            output_assets.append({
                "name":    asset.get("Name", ""),
                "class":   asset.get("Class", ""),
                "path":    asset.get("Path", "") or asset.get("PackageName", ""),
                "score":   score,
            })

        result = {
            "query":        query,
            "terms_used":   search_terms,
            "total_found":  len(all_assets),
            "returned":     len(output_assets),
            "assets":       output_assets,
        }
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _fallback_search(
        self,
        query:         str,
        terms:         list[str],
        class_names:   list[str],
        package_paths: list[str],
        recursive:     bool,
        max_results:   int,
    ):
        """
        Python-bridge fallback when RC search returns nothing.
        Uses AssetRegistry.get_assets_by_path() with substring matching.
        """
        search_path   = package_paths[0] if package_paths else "/Game"
        class_filter  = class_names[0] if class_names else ""
        terms_json    = json.dumps(terms[:8])
        cls_lower     = class_filter.lower()

        script = f"""
import unreal, json

registry  = unreal.AssetRegistryHelpers.get_asset_registry()
all_assets = registry.get_assets_by_path("{search_path}", recursive={str(recursive)})

terms      = {terms_json}
cls_filter = "{cls_lower}"
results    = []

for a in all_assets:
    cls  = str(a.asset_class_path.asset_name)
    name = str(a.asset_name).lower()
    path = str(a.object_path).lower()
    haystack = name + " " + path

    if cls_filter and cls_filter not in cls.lower():
        continue

    score = sum(2 if t in name else 1 for t in terms if t in haystack)
    if score > 0:
        results.append({{
            "name":  str(a.asset_name),
            "class": cls,
            "path":  str(a.object_path),
            "score": score,
        }})

results.sort(key=lambda x: x["score"], reverse=True)
print("UEOS_RESULT:" + json.dumps({{
    "query":       "{query}",
    "source":      "fallback_registry",
    "total_found": len(results),
    "returned":    len(results[:{max_results}]),
    "assets":      results[:{max_results}],
}}))
"""
        raw = await self.ue.execute_python(script)
        output = raw.get("output", "")
        for line in output.split("\n"):
            if line.startswith("UEOS_RESULT:"):
                try:
                    data = json.loads(line[len("UEOS_RESULT:"):])
                    return [types.TextContent(type="text",
                        text=json.dumps(data, indent=2))]
                except Exception:
                    pass
        # Nothing at all
        return [types.TextContent(type="text", text=json.dumps({
            "query":   query,
            "error":   "No assets found via RC search or fallback registry",
            "assets":  [],
        }, indent=2))]

    # ──────────────────────────────────────────────────────────────────────────
    # search_get_thumbnail
    # ──────────────────────────────────────────────────────────────────────────

    async def _search_get_thumbnail(self, args: dict):
        asset_path = args["asset_path"]
        log.info(f"search_get_thumbnail: {asset_path}")

        try:
            result = await self.ue.get_asset_thumbnail(asset_path)
        except Exception as e:
            return [types.TextContent(type="text", text=json.dumps({
                "error": f"Thumbnail request failed: {e}",
                "asset_path": asset_path,
            }))]

        if not result:
            return [types.TextContent(type="text", text=json.dumps({
                "error": "No thumbnail returned (asset may not exist or has no thumbnail)",
                "asset_path": asset_path,
            }))]

        # The RC thumbnail endpoint returns { "data": "<base64>", "mimeType": "image/png" }
        # or { "thumbnail": "<base64>" } depending on UE version.
        img_data = (
            result.get("data")
            or result.get("thumbnail")
            or result.get("Thumbnail")
            or result.get("image")
            or None
        )
        mime_type = result.get("mimeType", "image/png")

        if img_data:
            # Strip data: URI prefix if present
            if isinstance(img_data, str) and img_data.startswith("data:"):
                header, _, img_data = img_data.partition(",")
                mime_type = header.split(":")[1].split(";")[0] if ":" in header else mime_type
            return [
                types.TextContent(type="text", text=f"Thumbnail for: {asset_path}"),
                types.ImageContent(
                    type="image",
                    data=img_data,
                    mimeType=mime_type,
                ),
            ]

        # Thumbnail data not in expected field — return raw dict as debug info
        return [types.TextContent(type="text", text=json.dumps({
            "asset_path": asset_path,
            "note": "Thumbnail returned but image data not found in expected field",
            "raw_keys": list(result.keys()),
        }, indent=2))]

    # ──────────────────────────────────────────────────────────────────────────
    # search_list_folder
    # ──────────────────────────────────────────────────────────────────────────

    async def _search_list_folder(self, args: dict):
        folder       = args["folder"]
        filter_class = args.get("filter_class", "")
        recursive    = args.get("recursive", True)
        max_results  = args.get("max_results", 50)

        cls_lower = filter_class.lower()

        script = f"""
import unreal, json

registry   = unreal.AssetRegistryHelpers.get_asset_registry()
all_assets = registry.get_assets_by_path("{folder}", recursive={str(recursive)})

cls_filter = "{cls_lower}"
results    = []

for a in all_assets:
    cls = str(a.asset_class_path.asset_name)
    if cls_filter and cls_filter not in cls.lower():
        continue
    results.append({{
        "name":    str(a.asset_name),
        "class":   cls,
        "path":    str(a.object_path),
        "package": str(a.package_name),
    }})

print("UEOS_RESULT:" + json.dumps({{
    "folder":       "{folder}",
    "filter_class": "{filter_class}",
    "total_found":  len(results),
    "returned":     len(results[:{max_results}]),
    "assets":       results[:{max_results}],
}}))
"""
        raw    = await self.ue.execute_python(script)
        output = raw.get("output", "")
        for line in output.split("\n"):
            if line.startswith("UEOS_RESULT:"):
                try:
                    data = json.loads(line[len("UEOS_RESULT:"):])
                    return [types.TextContent(type="text",
                        text=json.dumps(data, indent=2))]
                except Exception:
                    pass
        return [types.TextContent(type="text", text=json.dumps({
            "error":  "search_list_folder returned no output",
            "folder": folder,
            "raw":    output[:500],
        }, indent=2))]
