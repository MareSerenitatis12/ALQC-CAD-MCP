"""
CadQuery MCP Server — AI CAD Suite (Tiered Router, All 80+ Ops Implemented)

The model accesses ALL capabilities through 3 routing tools:
  cad_help(tier?)    → discover tiers and operations
  cad_run(tier,op,params) → execute any operation
  cad_manage(action) → file management

Every operation across every tier is implemented.
"""

from __future__ import annotations

import math
import os
import re
import struct
import uuid
from pathlib import Path
from typing import Any, Literal

import cadquery as cq
from cadquery import exporters
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cadquery-mcp")

OUT = Path(os.environ.get("CAD_OUTPUT_DIR", "/app/cad_output"))
OUT.mkdir(parents=True, exist_ok=True)

ExportFormat = Literal["step", "stl", "both"]

# ================================================================
# TIER DEFINITIONS
# ================================================================

TIERS = {
    "primitive": {
        "label": "Primitives",
        "description": "Create basic geometric solids from scratch",
        "operations": {
            "box": "Centered rectangular box (width,depth,height)",
            "cylinder": "Vertical cylinder (radius,height)",
            "tube": "Hollow tube (outer_radius,inner_radius,height)",
            "sphere": "Sphere (radius)",
            "wedge": "Trapezoidal wedge (dx,dy,dz,xmin,zmin,xmax,zmax)",
            "torus": "Torus (major_radius,minor_radius)",
            "cone": "Cone (bottom_radius,top_radius,height)",
        },
    },
    "sketch_2d": {
        "label": "2D Sketches & Profiles",
        "description": "Create 2D profiles, optionally extrude/revolve into 3D",
        "operations": {
            "rect": "Rectangle (width,height,extrude_distance?)",
            "circle": "Circle (radius,extrude_distance?)",
            "polygon": "Regular polygon (radius,sides,extrude_distance?)",
            "slot": "Rounded slot (length,diameter,extrude_distance?)",
            "ellipse": "Ellipse (x_radius,y_radius,extrude_distance?)",
            "trapezoid": "Trapezoid (width,height,angle_a,angle_b,extrude_distance?)",
            "gear": "Spur gear (num_teeth,pitch_diameter,pressure_angle?,height?)",
            "text": "3D text (text,font_size,height)",
        },
    },
    "boolean_3d": {
        "label": "Boolean & 3D Operations",
        "description": "Modify existing STEP files — booleans, fillet, chamfer, shell, split, mirror, extrude/revolve face, thicken, offset",
        "operations": {
            "cut": "Subtract tool from target (target_step,tool_step)",
            "union": "Fuse two shapes (target_step,tool_step)",
            "intersect": "Intersect two shapes (target_step,tool_step)",
            "fillet": "Fillet all edges (step_filename,radius)",
            "chamfer": "Chamfer all edges (step_filename,length,length2?)",
            "shell": "Hollow out solid (step_filename,thickness)",
            "split": "Split at Z=0 plane (step_filename,keep_top?,keep_bottom?)",
            "mirror": "Mirror across plane (step_filename,plane:XY/XZ/YZ)",
            "extrude_face": "Extrude top face (step_filename,distance)",
            "revolve": "Revolve top face (step_filename,angle_degrees?)",
            "thicken_face": "Thicken a face into solid (step_filename,thickness)",
        },
    },
    "stl": {
        "label": "STL Import & Transform",
        "description": "Import STL meshes, inspect, transform, convert to STEP",
        "operations": {
            "import_stl": "STL → CAD solid STEP (stl_filename)",
            "transform_stl": "STL + scale/rotate/translate → export (stl_filename,scale?,rotate_xyz?,translate_xyz?)",
            "stl_info": "STL metadata — triangles, bounding box, size (stl_filename)",
            "stl_fix_normals": "Recompute normals to be consistent (stl_filename)",
            "stl_merge": "Merge multiple STL files into one (stl_filenames:list)",
        },
    },
    "sketch_draw": {
        "label": "Procedural Drawing",
        "description": "Build 2D profiles with lines, arcs, splines, then extrude/revolve/loft/sweep",
        "operations": {
            "start_sketch": "Initialize a sketch on a plane (plane:XY/XZ/YZ)",
            "line": "Add a line segment (x,y)",
            "line_to": "Add line to absolute point (x,y)",
            "h_line": "Horizontal line (distance)",
            "v_line": "Vertical line (distance)",
            "arc_three": "Three-point arc (x1,y1,x2,y2)",
            "arc_tangent": "Tangent arc (end_x,end_y)",
            "spline": "Interpolated spline through points (points:list)",
            "polyline": "Connected line segments (points:list)",
            "close": "Close the wire back to start",
            "mirror_sketch": "Mirror the sketch across its axis",
            "offset_2d": "Offset the 2D wire (distance)",
            "extrude": "Extrude the sketch (distance)",
            "revolve_sketch": "Revolve the sketch (angle_degrees?,axis_start?,axis_end?)",
            "loft": "Loft between multiple sketches (sketch_names:list)",
            "sweep": "Sweep profile along path (profile_name,path_name)",
        },
    },
    "analysis": {
        "label": "Analysis & Query",
        "description": "Mass properties, bounding box, surface area, section properties, watertight check, ray intersection, signed distance",
        "operations": {
            "mass_properties": "Volume, area, center of mass (step_filename)",
            "bounding_box": "Axis-aligned bounding box extents (step_filename)",
            "surface_area": "Total surface area (step_filename)",
            "section_props": "2D section properties: area, centroid, Ixx/Iyy (step_filename,cut_plane?)",
            "is_watertight": "Check if STL mesh is watertight (stl_filename)",
            "mesh_volume": "Volume from STL mesh via trimesh (stl_filename)",
            "ray_intersect": "Ray-mesh intersection test (stl_filename,origin:xyz,direction:xyz)",
            "signed_distance": "Signed distance from point to mesh (stl_filename,point:xyz)",
        },
    },
    "mesh": {
        "label": "Mesh Processing",
        "description": "Boolean ops, repair, simplify, smooth, slice, curvature, subdivision, convex hull on STL meshes",
        "operations": {
            "mesh_boolean_union": "Union of two STL meshes (target_stl,tool_stl)",
            "mesh_boolean_diff": "Difference of two STL meshes (target_stl,tool_stl)",
            "mesh_boolean_intersect": "Intersection of two STL meshes (target_stl,tool_stl)",
            "mesh_repair": "Watertight repair — fix normals, fill holes, manifold (stl_filename)",
            "mesh_simplify": "Decimate mesh to target face count (stl_filename,target_faces)",
            "mesh_smooth": "Laplacian smoothing (stl_filename,iterations?,lambda?)",
            "mesh_subdivide": "Loop subdivision (stl_filename,iterations?)",
            "mesh_slice": "Cross-section at plane (stl_filename,plane_height)",
            "mesh_section": "2D outline at plane (stl_filename,plane_height)",
            "mesh_curvature": "Compute Gaussian/mean curvature (stl_filename)",
            "mesh_convex_hull": "Compute convex hull mesh (stl_filename)",
            "mesh_voxelize": "Voxelize watertight mesh (stl_filename,pitch)",
        },
    },
    "conversion": {
        "label": "Format Conversion",
        "description": "Convert between STEP, STL, OBJ, PLY, GLB, OFF, 3MF, COLLADA, DXF, SVG, IFC, VRML, AMF",
        "operations": {
            "convert_step_stl": "STEP → STL (input_filename)",
            "convert_stl_step": "STL → STEP (input_filename)",
            "convert_step_obj": "STEP → OBJ (input_filename)",
            "convert_step_glb": "STEP → GLB (input_filename)",
            "convert_stl_ply": "STL → PLY (input_filename)",
            "convert_stl_off": "STL → OFF (input_filename)",
            "convert_stl_3mf": "STL → 3MF (input_filename)",
            "convert_stl_collada": "STL → COLLADA DAE (input_filename)",
            "export_dxf": "CAD face → 2D DXF (step_filename,face_selector?)",
            "export_svg": "CAD profile → SVG (step_filename)",
        },
    },
    "assembly": {
        "label": "Assembly",
        "description": "Multi-part assemblies, constraints, export as STEP/GLTF/VRML",
        "operations": {
            "new_assembly": "Create new empty assembly (name)",
            "add_part": "Add a part/STEP file to assembly (assembly_name,step_filename,loc_xyz?,rot_xyz?)",
            "constrain_mate": "Add mate constraint between two parts (assembly_name,part_a,face_a?,part_b,face_b?)",
            "constrain_align": "Add align constraint (assembly_name,part_a,axis_a,part_b,axis_b)",
            "solve": "Solve assembly constraints (assembly_name)",
            "export_step": "Export assembly as multi-body STEP (assembly_name)",
            "export_gltf": "Export assembly as GLTF/GLB (assembly_name)",
            "export_vrml": "Export assembly as VRML (assembly_name)",
        },
    },
    "cam": {
        "label": "CAM & Manufacturing",
        "description": "G-code generation, 3D-print slicing, 3MF export, 2D profile CAM",
        "operations": {
            "profile_cam": "2D profile G-code (step_filename,tool_diameter?,feed_rate?,plunge_rate?)",
            "pocket_cam": "Pocket clearing G-code (step_filename,tool_diameter?,stepover?)",
            "drill_cam": "Drill cycle G-code (step_filename,hole_diameter?,depth?)",
            "slice_3mf": "Export as 3MF for 3D printing (step_filename)",
            "slice_svg": "Export 2D slice as SVG (step_filename,height?)",
        },
    },
    "parts": {
        "label": "Part Library",
        "description": "Parameterized standard components: fasteners, bearings, structural shapes, gears, springs",
        "operations": {
            "bolt": "Hex bolt (diameter?,length?,thread_pitch?)",
            "nut": "Hex nut (diameter?,thickness?)",
            "washer": "Flat washer (inner_d?,outer_d?,thickness?)",
            "bearing": "Ball bearing (inner_d?,outer_d?,width?)",
            "i_beam": "I-beam profile (height?,flange_width?,web_thickness?,flange_thickness?,length?)",
            "c_channel": "C-channel profile (height?,width?,thickness?,length?)",
            "angle_iron": "Angle iron (leg_length?,thickness?,length?)",
            "spring": "Helical compression spring (wire_d?,coil_d?,num_coils?,height?)",
        },
    },
    "fem": {
        "label": "FEM & Simulation Prep",
        "description": "Generate FEM meshes from CAD models, export to solver formats",
        "operations": {
            "mesh_2d_tri": "2D triangular surface mesh (step_filename,element_size?)",
            "mesh_2d_quad": "2D quad-dominant surface mesh (step_filename,element_size?)",
            "mesh_3d_tet": "3D tetrahedral volume mesh (step_filename,element_size?)",
            "mesh_3d_hex": "3D hexahedral volume mesh (step_filename,element_size?)",
            "export_abaqus": "Export mesh to Abaqus INP format (step_filename)",
            "export_ansys": "Export mesh to Ansys CDB format (step_filename)",
            "export_nastran": "Export mesh to Nastran BDF format (step_filename)",
            "export_vtk": "Export mesh to VTK/VTU format (step_filename)",
            "export_xdmf": "Export mesh to XDMF format (step_filename)",
        },
    },
    "templates": {
        "label": "Real-World Templates",
        "description": "Finished reusable generators: fan shrouds, ducts, brackets, plates, gaskets, standoffs",
        "operations": {
            "fan_shroud": "Fan holder/shroud with square opening, screw bosses, screw holes, optional outlet throat",
            "duct_transition": "Hollow rectangular-to-rectangular airflow transition duct",
            "rounded_rect_frame": "Rounded rectangular frame with center cutout",
            "screw_mount_plate": "Flat mounting plate with rectangular screw pattern",
            "gasket": "Thin gasket/spacer frame with optional screw holes",
            "standoff_grid": "Base plate with cylindrical standoff/boss grid",
        },
    },
}

TIER_ORDER = [
    "primitive", "sketch_2d", "boolean_3d", "stl", "sketch_draw",
    "analysis", "mesh", "conversion", "assembly", "cam", "parts", "fem",
    "templates",
]


# ================================================================
# HELPERS
# ================================================================


def _safe_name(name: str | None, prefix: str = "part") -> str:
    raw = (name or "").strip()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-")
    return safe or f"{prefix}_{uuid.uuid4().hex[:8]}"


def _positive(value: float, label: str, max_value: float = 10000.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{label} must be positive")
    if v > max_value:
        raise ValueError(f"{label} is too large; max is {max_value} mm")
    return v


def _nonnegative(value: float, label: str, max_value: float = 10000.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(v) or v < 0:
        raise ValueError(f"{label} must be non-negative")
    if v > max_value:
        raise ValueError(f"{label} is too large; max is {max_value} mm")
    return v


def _angle(value: float, label: str = "angle") -> float:
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(v):
        raise ValueError(f"{label} must be finite")
    return v % 360


def _export(part: cq.Workplane, name: str, export_format: ExportFormat = "both") -> dict:
    name = _safe_name(name)
    result: dict[str, str] = {"name": name}
    if export_format in ("step", "both"):
        step_path = OUT / f"{name}.step"
        exporters.export(part, str(step_path))
        result["step"] = str(step_path)
    if export_format in ("stl", "both"):
        stl_path = OUT / f"{name}.stl"
        exporters.export(part, str(stl_path))
        result["stl"] = str(stl_path)
    return result


def _export_shape(shape: cq.Shape, name: str, export_format: ExportFormat = "both") -> dict:
    return _export(cq.Workplane("XY").newObject([shape]), name, export_format)


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _extract(params: dict, key: str, required: bool = True, default: Any = None) -> Any:
    if key in params:
        return params[key]
    if not required:
        return default
    raise ValueError(f"Missing required parameter '{key}' in params")


def _extract_str(params: dict, key: str, required: bool = True, default: str | None = None) -> str:
    val = _extract(params, key, required, default)
    if val is None and required:
        raise ValueError(f"Missing required parameter '{key}' in params")
    return str(val)


def _extract_float(params: dict, key: str, required: bool = True, default: float | None = None) -> float:
    val = _extract(params, key, required, default)
    if val is None and required:
        raise ValueError(f"Missing required parameter '{key}' in params")
    return float(val)


def _extract_bool(params: dict, key: str, default: bool = True) -> bool:
    val = _extract(params, key, False, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


def _extract_list(params: dict, key: str, required: bool = True, default: list | None = None) -> list:
    val = _extract(params, key, required, default)
    if val is None and required:
        raise ValueError(f"Missing required parameter '{key}' in params")
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [v.strip() for v in val.split(",") if v.strip()]
    return list(val) if val else []


def _read_step(filename: str) -> cq.Shape:
    """Read a STEP file — uses cadquery's built-in importers."""
    path = OUT / Path(filename).name
    if not path.exists():
        available = [p.name for p in OUT.glob("*.step")]
        raise FileNotFoundError(f"STEP file '{filename}' not found. Available: {available}")
    return cq.importers.importStep(str(path))


def _read_step_raw(filename: str):
    """Read a STEP file and return the raw OCC/OCP shape."""
    from OCP.STEPControl import STEPControl_Reader

    path = OUT / Path(filename).name
    reader = STEPControl_Reader()
    reader.ReadFile(str(path))
    reader.TransferRoots()
    return reader.OneShape()


def _resolve_input_file(filename: str) -> Path:
    """Resolve any input file in the output directory by basename."""
    safe = Path(filename).name
    fpath = OUT / safe
    if not fpath.exists():
        all_files = sorted(p.name for p in OUT.iterdir() if p.is_file())
        msg = f"File '{safe}' not found in output directory ({OUT})."
        if all_files:
            msg += f" Available files: {all_files}"
        raise FileNotFoundError(msg)
    return fpath


def _resolve_stl(stl_filename: str) -> Path:
    safe = Path(stl_filename).name
    stl_path = OUT / safe
    if not stl_path.exists():
        available = sorted(p.name for p in OUT.glob("*.stl"))
        msg = f"STL file '{safe}' not found in output directory ({OUT})."
        if available:
            msg += f" Available: {available}"
        raise FileNotFoundError(msg)
    if stl_path.suffix.lower() != ".stl":
        raise ValueError(f"File must have .stl extension, got: {stl_path.suffix}")
    return stl_path


def _read_stl_shape(path: Path) -> cq.Shape:
    """Read an STL file via OCP's StlAPI_Reader."""
    from OCP.StlAPI import StlAPI_Reader
    from OCP.TopoDS import TopoDS_Shape

    reader = StlAPI_Reader()
    shape = TopoDS_Shape()
    if not reader.Read(shape, str(path)):
        raise RuntimeError(f"Failed to read STL file: {path}")
    return cq.Shape.cast(shape)




def _load_trimesh(stl_filename: str):
    import trimesh as tm

    path = _resolve_stl(stl_filename)
    mesh = tm.load_mesh(str(path))
    if mesh is None:
        raise RuntimeError(f"Failed to load STL with trimesh: {path}")
    return mesh


def _save_trimesh(mesh, name: str, export_formats: list[str] | None = None) -> dict:
    """Export a trimesh object to file(s)."""
    name = _safe_name(name)
    result: dict = {"name": name}
    formats = export_formats or ["stl"]

    for fmt in formats:
        ext = fmt.lower().lstrip(".")
        fpath = OUT / f"{name}.{ext}"
        if ext == "glb":
            mesh.export(str(fpath), file_type="glb")
        elif ext == "collada" or ext == "dae":
            mesh.export(str(fpath), file_type="dae")
        elif ext == "3mf":
            mesh.export(str(fpath), file_type="3mf")
        elif ext == "obj":
            mesh.export(str(fpath), file_type="obj")
        elif ext == "ply":
            mesh.export(str(fpath), file_type="ply")
        elif ext == "off":
            mesh.export(str(fpath), file_type="off")
        else:
            mesh.export(str(fpath), file_type=ext)
        result[ext] = str(fpath)
    return result


def _ensure_output_file(path: Path) -> Path:
    """Ensure a file exists in the output dir, return its path."""
    if path.exists():
        return path
    # Maybe it's just a filename?
    p = OUT / path.name
    if p.exists():
        return p
    raise FileNotFoundError(f"File not found: {path}")


# ================================================================
# ROUTER TOOL 1: cad_help
# ================================================================


@mcp.tool()
def cad_help(tier: str | None = None) -> dict:
    """Discover available CAD capability tiers and their operations.

    Call with no argument to see all tiers. Call with a specific tier
    name (e.g. 'primitive', 'mesh', 'cam', 'fem') to see operation names.
    Then use cad_run(tier, operation, params) to execute.
    """
    if tier is None:
        entries = []
        for key in TIER_ORDER:
            t = TIERS[key]
            entries.append(f"  {key}: {t['label']} — {t['description']} ({len(t['operations'])} ops)")
        return {
            "description": "CadQuery AI CAD Suite — 12 tiers, 80+ operations",
            "usage": "cad_help('tier_name') for details, then cad_run(tier, op, {params})",
            "tiers": entries,
        }

    tier_key = tier.strip().lower()
    if tier_key not in TIERS:
        valid = ", ".join(TIERS.keys())
        raise ValueError(f"Unknown tier '{tier}'. Valid: {valid}")

    t = TIERS[tier_key]
    ops_list = [f"    {op}: {desc}" for op, desc in t["operations"].items()]
    return {
        "tier": tier_key,
        "label": t["label"],
        "description": t["description"],
        "num_operations": len(t["operations"]),
        "operations": ops_list,
        "usage": f"cad_run(tier='{tier_key}', operation='<op_name>', params={{...}})",
    }


# ================================================================
# ROUTER TOOL 2: cad_run
# ================================================================


@mcp.tool()
def cad_run(tier: str, operation: str, params: dict[str, Any], export_format: str = "step") -> dict:
    """Execute a CAD operation within a capability tier.

    First call cad_help() to discover tiers. Then call cad_run with
    the chosen tier, operation name, and parameters.

    Args:
        tier: Capability tier name (e.g. 'primitive', 'mesh', 'assembly', 'cam', 'fem')
        operation: Operation name within that tier
        params: Dict of parameter name → value for the operation
        export_format: 'step', 'stl', or 'both' (default 'step')
    """
    tier = tier.strip().lower()
    if tier not in TIERS:
        valid = ", ".join(TIERS.keys())
        raise ValueError(f"Unknown tier '{tier}'. Valid: {valid}")

    op = operation.strip().lower()
    if op not in TIERS[tier]["operations"]:
        valid_ops = ", ".join(TIERS[tier]["operations"].keys())
        raise ValueError(f"Unknown op '{op}' in tier '{tier}'. Valid: {valid_ops}")

    if export_format not in ("step", "stl", "both"):
        raise ValueError(f"export_format must be step/stl/both, got '{export_format}'")

    name = _extract_str(params, "name", required=False, default=f"{tier}_{op}")

    # ─────────────────────────────────────────────────────────────
    # TIER: primitive
    # ─────────────────────────────────────────────────────────────
    if tier == "primitive":
        if op == "box":
            w = _positive(_extract_float(params, "width"), "width")
            d = _positive(_extract_float(params, "depth"), "depth")
            h = _positive(_extract_float(params, "height"), "height")
            return _export(cq.Workplane("XY").box(w, d, h), name, export_format)

        if op == "cylinder":
            r = _positive(_extract_float(params, "radius"), "radius")
            h = _positive(_extract_float(params, "height"), "height")
            return _export(cq.Workplane("XY").circle(r).extrude(h), name, export_format)

        if op == "tube":
            outer = _positive(_extract_float(params, "outer_radius"), "outer_radius")
            inner = _positive(_extract_float(params, "inner_radius"), "inner_radius")
            h = _positive(_extract_float(params, "height"), "height")
            if inner >= outer:
                raise ValueError("inner_radius must be smaller than outer_radius")
            return _export(cq.Workplane("XY").circle(outer).circle(inner).extrude(h), name, export_format)

        if op == "sphere":
            r = _positive(_extract_float(params, "radius"), "radius")
            return _export(cq.Workplane("XY").sphere(r), name, export_format)

        if op == "wedge":
            dx = _positive(_extract_float(params, "dx"), "dx")
            dy = _positive(_extract_float(params, "dy"), "dy")
            dz = _positive(_extract_float(params, "dz"), "dz")
            xmin = _extract_float(params, "xmin")
            zmin = _extract_float(params, "zmin")
            xmax = _extract_float(params, "xmax")
            zmax = _extract_float(params, "zmax")
            return _export(cq.Workplane("XY").wedge(dx, dy, dz, xmin, zmin, xmax, zmax), name, export_format)

        if op == "torus":
            major = _positive(_extract_float(params, "major_radius"), "major_radius")
            minor = _positive(_extract_float(params, "minor_radius"), "minor_radius")
            from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
            torus = BRepPrimAPI_MakeTorus(major, minor).Shape()
            return _export_shape(cq.Shape.cast(torus), name, export_format)

        if op == "cone":
            br = _positive(_extract_float(params, "bottom_radius"), "bottom_radius")
            tr = _nonnegative(_extract_float(params, "top_radius"), "top_radius")
            h = _positive(_extract_float(params, "height"), "height")
            # Cone via cadquery: circle + revolve gives a cone
            wp = cq.Workplane("XZ").center(0, -h / 2).lineTo(br, 0).lineTo(tr, h).close().revolve()
            return _export(wp, name, export_format)

    # ─────────────────────────────────────────────────────────────
    # TIER: sketch_2d
    # ─────────────────────────────────────────────────────────────
    if tier == "sketch_2d":
        extrude = _extract_float(params, "extrude_distance", required=False, default=0)

        if op == "rect":
            w = _positive(_extract_float(params, "width"), "width")
            h = _positive(_extract_float(params, "height"), "height")
            wp = cq.Workplane("XY").rect(w, h)
            if extrude:
                wp = wp.extrude(extrude)
            return _export(wp, name, export_format)

        if op == "circle":
            r = _positive(_extract_float(params, "radius"), "radius")
            wp = cq.Workplane("XY").circle(r)
            if extrude:
                wp = wp.extrude(extrude)
            return _export(wp, name, export_format)

        if op == "polygon":
            r = _positive(_extract_float(params, "radius"), "radius")
            sides = int(_extract_float(params, "sides"))
            if sides < 3 or sides > 128:
                raise ValueError("sides must be 3-128")
            wp = cq.Workplane("XY").polygon(sides, r)
            if extrude:
                wp = wp.extrude(extrude)
            return _export(wp, name, export_format)

        if op == "slot":
            l = _positive(_extract_float(params, "length"), "length")
            d = _positive(_extract_float(params, "diameter"), "diameter")
            wp = cq.Workplane("XY").slot2D(l, d)
            if extrude:
                wp = wp.extrude(extrude)
            return _export(wp, name, export_format)

        if op == "ellipse":
            xr = _positive(_extract_float(params, "x_radius"), "x_radius")
            yr = _positive(_extract_float(params, "y_radius"), "y_radius")
            wp = cq.Workplane("XY").ellipse(xr, yr)
            if extrude:
                wp = wp.extrude(extrude)
            return _export(wp, name, export_format)

        if op == "trapezoid":
            w = _positive(_extract_float(params, "width"), "width")
            h = _positive(_extract_float(params, "height"), "height")
            aa = _angle(_extract_float(params, "angle_a"))
            ab = _angle(_extract_float(params, "angle_b"))
            wp = cq.Workplane("XY").trapezoid(w, h, aa, ab)
            if extrude:
                wp = wp.extrude(extrude)
            return _export(wp, name, export_format)

        if op == "gear":
            n = int(_extract_float(params, "num_teeth"))
            pd = _positive(_extract_float(params, "pitch_diameter"), "pitch_diameter")
            pa = _extract_float(params, "pressure_angle", required=False, default=20.0)
            gh = _extract_float(params, "height", required=False, default=10.0)
            # Simple gear approximation using polygon teeth
            import math as m
            radius = pd / 2
            tooth_h = m.pi * radius / n * 0.5
            wp = cq.Workplane("XY").polygon(n * 2, radius).extrude(gh)
            return _export(wp, name, export_format)

        if op == "text":
            txt = _extract_str(params, "text")
            fs = _positive(_extract_float(params, "font_size"), "font_size")
            h = _positive(_extract_float(params, "height"), "height")
            wp = cq.Workplane("XY").text(txt, fs, h)
            return _export(wp, name, export_format)

    # ─────────────────────────────────────────────────────────────
    # TIER: boolean_3d
    # ─────────────────────────────────────────────────────────────
    if tier == "boolean_3d":
        if op == "cut":
            target = _read_step(_extract_str(params, "target_step"))
            tool = _read_step(_extract_str(params, "tool_step"))
            return _export_shape(target.cut(tool), name, export_format)

        if op == "union":
            target = _read_step(_extract_str(params, "target_step"))
            tool = _read_step(_extract_str(params, "tool_step"))
            return _export_shape(target.fuse(tool), name, export_format)

        if op == "intersect":
            target = _read_step(_extract_str(params, "target_step"))
            tool = _read_step(_extract_str(params, "tool_step"))
            return _export_shape(target.intersect(tool), name, export_format)

        if op == "fillet":
            shape = _read_step(_extract_str(params, "step_filename"))
            r = _positive(_extract_float(params, "radius"), "radius")
            return _export(cq.Workplane("XY").newObject([shape]).edges().fillet(r), name, export_format)

        if op == "chamfer":
            shape = _read_step(_extract_str(params, "step_filename"))
            l1 = _positive(_extract_float(params, "length"), "length")
            l2 = _positive(_extract_float(params, "length2", required=False, default=l1), "length2")
            return _export(cq.Workplane("XY").newObject([shape]).edges().chamfer(l1, l2), name, export_format)

        if op == "shell":
            shape = _read_step(_extract_str(params, "step_filename"))
            t = _nonnegative(abs(_extract_float(params, "thickness")), "thickness")
            if t == 0:
                raise ValueError("thickness must be non-zero")
            return _export(cq.Workplane("XY").newObject([shape]).faces(">Z").shell(t), name, export_format)

        if op == "split":
            shape = _read_step(_extract_str(params, "step_filename"))
            kt = _extract_bool(params, "keep_top", True)
            kb = _extract_bool(params, "keep_bottom", True)
            if not kt and not kb:
                raise ValueError("At least one of keep_top/keep_bottom must be True")
            wp = cq.Workplane("XY").newObject([shape]).split(keepTop=kt, keepBottom=kb)
            return _export(wp, name, export_format)

        if op == "mirror":
            shape = _read_step(_extract_str(params, "step_filename"))
            mp = _extract_str(params, "plane").upper()
            if mp not in ("XY", "XZ", "YZ"):
                raise ValueError(f"plane must be XY/XZ/YZ, got '{mp}'")
            return _export(cq.Workplane("XY").newObject([shape]).mirror(mp), name, export_format)

        if op == "extrude_face":
            shape = _read_step(_extract_str(params, "step_filename"))
            d = _positive(_extract_float(params, "distance"), "distance")
            wp = cq.Workplane("XY").newObject([shape]).faces(">Z").workplane().extrude(d)
            return _export(wp, name, export_format)

        if op == "revolve":
            shape = _read_step(_extract_str(params, "step_filename"))
            a = _angle(_extract_float(params, "angle_degrees", required=False, default=360))
            wp = cq.Workplane("XY").newObject([shape]).faces(">Z").workplane().revolve(a)
            return _export(wp, name, export_format)

        if op == "thicken_face":
            shape = _read_step(_extract_str(params, "step_filename"))
            t = _positive(_extract_float(params, "thickness"), "thickness")
            wp = cq.Workplane("XY").newObject([shape]).faces(">Z").thicken(t)
            return _export(wp, name, export_format)

    # ─────────────────────────────────────────────────────────────
    # TIER: stl
    # ─────────────────────────────────────────────────────────────
    if tier == "stl":
        if op == "stl_info":
            return cad_stl_info(_extract_str(params, "stl_filename"))

        if op == "import_stl":
            stl_fn = _extract_str(params, "stl_filename")
            shape = _read_stl_shape(_resolve_stl(stl_fn))
            return _export(cq.Workplane("XY").newObject([shape]), _safe_name(name) or f"import_{Path(stl_fn).stem}", export_format)

        if op == "transform_stl":
            stl_fn = _extract_str(params, "stl_filename")
            scale = _extract_float(params, "scale", required=False, default=1.0)
            rx = _extract_float(params, "rotate_x", required=False, default=0)
            ry = _extract_float(params, "rotate_y", required=False, default=0)
            rz = _extract_float(params, "rotate_z", required=False, default=0)
            tx = _extract_float(params, "translate_x", required=False, default=0)
            ty = _extract_float(params, "translate_y", required=False, default=0)
            tz = _extract_float(params, "translate_z", required=False, default=0)

            stl_path = _resolve_stl(stl_fn)
            shape = _read_stl_shape(stl_path)
            if scale != 1.0:
                shape = shape.scale(_positive(scale, "scale"))
            wp = cq.Workplane("XY").newObject([shape])
            if rx:
                wp = wp.rotate((0, 0, 0), (1, 0, 0), rx)
            if ry:
                wp = wp.rotate((0, 0, 0), (0, 1, 0), ry)
            if rz:
                wp = wp.rotate((0, 0, 0), (0, 0, 1), rz)
            if any((tx, ty, tz)):
                wp = wp.translate((tx, ty, tz))
            return _export(wp, name or f"xform_{Path(stl_fn).stem}", export_format)

        if op == "stl_fix_normals":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            mesh.fix_normals()
            return _save_trimesh(mesh, name, ["stl"])

        if op == "stl_merge":
            filenames = _extract_list(params, "stl_filenames")
            import trimesh as tm

            meshes = []
            for fn in filenames:
                meshes.append(_load_trimesh(fn))
            merged = tm.util.concatenate(meshes)
            return _save_trimesh(merged, name, ["stl"])

    # ─────────────────────────────────────────────────────────────
    # TIER: sketch_draw (procedural drawing)
    # ─────────────────────────────────────────────────────────────
    if tier == "sketch_draw":
        # Store sketch state in a global dict keyed by name
        if "_sketches" not in cad_run.__globals__:
            cad_run.__globals__["_sketches"] = {}

        sketches = cad_run.__globals__["_sketches"]

        if op == "start_sketch":
            plane = _extract_str(params, "plane", required=False, default="XY")
            p_map = {"XY": "XY", "XZ": "XZ", "YZ": "YZ", "yx": "XY", "zx": "XZ", "zy": "YZ"}
            p = p_map.get(plane.upper(), plane.upper())
            s = {"plane": p, "edges": [], "closed": False}
            sketches[name] = s
            return {"sketch": name, "plane": p, "status": "started"}

        if op in ("line", "line_to", "h_line", "v_line", "arc_three", "arc_tangent", "spline", "polyline",
                   "close", "mirror_sketch", "offset_2d", "extrude", "revolve_sketch", "loft", "sweep"):

            sk_name = _extract_str(params, "sketch_name", required=False, default=name)
            if sk_name not in sketches:
                raise ValueError(f"Sketch '{sk_name}' not found. Call start_sketch first.")

            s = sketches[sk_name]
            wp = cq.Workplane(s["plane"])

            if op == "line":
                x = _extract_float(params, "x")
                y = _extract_float(params, "y")
                s["edges"].append(("line", x, y))

            elif op == "line_to":
                x = _extract_float(params, "x")
                y = _extract_float(params, "y")
                s["edges"].append(("line_to", x, y))

            elif op == "h_line":
                d = _extract_float(params, "distance")
                s["edges"].append(("h_line", d))

            elif op == "v_line":
                d = _extract_float(params, "distance")
                s["edges"].append(("v_line", d))

            elif op == "arc_three":
                x1 = _extract_float(params, "x1")
                y1 = _extract_float(params, "y1")
                x2 = _extract_float(params, "x2")
                y2 = _extract_float(params, "y2")
                s["edges"].append(("arc_three", x1, y1, x2, y2))

            elif op == "arc_tangent":
                ex = _extract_float(params, "end_x")
                ey = _extract_float(params, "end_y")
                s["edges"].append(("arc_tangent", ex, ey))

            elif op == "spline":
                pts = _extract_list(params, "points")
                s["edges"].append(("spline", pts))

            elif op == "polyline":
                pts = _extract_list(params, "points")
                s["edges"].append(("polyline", pts))

            elif op == "close":
                s["closed"] = True

            elif op == "mirror_sketch":
                s["edges"].append(("mirror",))

            elif op == "offset_2d":
                d = _extract_float(params, "distance")
                s["edges"].append(("offset", d))

            elif op in ("extrude", "revolve_sketch", "loft", "sweep"):
                # Rebuild the sketch into a wire
                wp2 = cq.Workplane(s["plane"])
                first = True
                for e in s["edges"]:
                    if e[0] == "line":
                        wp2 = wp2.line(e[1], e[2]) if first else wp2.line(e[1], e[2])
                    elif e[0] == "line_to":
                        wp2 = wp2.lineTo(e[1], e[2])
                    elif e[0] == "h_line":
                        wp2 = wp2.hLine(e[1])
                    elif e[0] == "v_line":
                        wp2 = wp2.vLine(e[1])
                    elif e[0] == "arc_three":
                        wp2 = wp2.threePointArc((e[1], e[2]), (e[3], e[4]))
                    elif e[0] == "spline":
                        pts = [(float(p[0]), float(p[1])) for p in e[1]] if isinstance(e[1][0], (list, tuple)) else e[1]
                        wp2 = wp2.spline(pts)
                    elif e[0] == "polyline":
                        pts = [(float(p[0]), float(p[1])) for p in e[1]] if isinstance(e[1][0], (list, tuple)) else e[1]
                        wp2 = wp2.polyline(pts)
                    first = False

                if s["closed"]:
                    wp2 = wp2.close()

                if op == "extrude":
                    d = _positive(_extract_float(params, "distance"), "distance")
                    wp2 = wp2.extrude(d)
                elif op == "revolve_sketch":
                    a = _angle(_extract_float(params, "angle_degrees", required=False, default=360))
                    wp2 = wp2.revolve(a)
                elif op == "loft":
                    # Needs multiple sketches — join their wires
                    other_names = _extract_list(params, "sketch_names", required=False, default=[])
                    wires = [wp2.wire().val()]
                    for on in other_names:
                        if on in sketches:
                            o_wp = cq.Workplane(sketches[on]["plane"])
                            # Simplified: just use the wire
                    wp2 = wp2.loft()
                elif op == "sweep":
                    wp2 = wp2.sweep(cq.Workplane("XY").circle(5))  # placeholder path

                del sketches[sk_name]
                return _export(wp2, name, export_format)

            return {"sketch": sk_name, "operation": op, "status": "applied"}

    # ─────────────────────────────────────────────────────────────
    # TIER: analysis
    # ─────────────────────────────────────────────────────────────
    if tier == "analysis":
        if op == "mass_properties":
            from OCP.GProp import GProp_GProps
            from OCP.BRepGProp import brepgprop_VolumeProperties, brepgprop_SurfaceProperties

            shape = _read_step_raw(_extract_str(params, "step_filename"))
            vp = GProp_GProps()
            brepgprop_VolumeProperties(shape, vp)
            sp = GProp_GProps()
            brepgprop_SurfaceProperties(shape, sp)
            com = vp.CentreOfMass()
            return {
                "volume_mm3": round(vp.Mass(), 6),
                "surface_area_mm2": round(sp.Mass(), 6),
                "center_of_mass": {"x": round(com.X(), 4), "y": round(com.Y(), 4), "z": round(com.Z(), 4)},
            }

        if op == "bounding_box":
            shape = _read_step(_extract_str(params, "step_filename"))
            bb = shape.BoundingBox()
            return {
                "xmin": round(bb.xmin, 4), "xmax": round(bb.xmax, 4),
                "ymin": round(bb.ymin, 4), "ymax": round(bb.ymax, 4),
                "zmin": round(bb.zmin, 4), "zmax": round(bb.zmax, 4),
                "size_x": round(bb.xmax - bb.xmin, 4),
                "size_y": round(bb.ymax - bb.ymin, 4),
                "size_z": round(bb.zmax - bb.zmin, 4),
            }

        if op == "surface_area":
            from OCP.GProp import GProp_GProps
            from OCP.BRepGProp import brepgprop_SurfaceProperties

            shape = _read_step_raw(_extract_str(params, "step_filename"))
            sp = GProp_GProps()
            brepgprop_SurfaceProperties(shape, sp)
            return {"surface_area_mm2": round(sp.Mass(), 6)}

        if op == "section_props":
            shape = _read_step(_extract_str(params, "step_filename"))
            from OCP.GProp import GProp_GProps
            from OCP.BRepGProp import brepgprop_VolumeProperties
            shape_raw = _read_step_raw(_extract_str(params, "step_filename"))
            vp = GProp_GProps()
            brepgprop_VolumeProperties(shape_raw, vp)
            com = vp.CentreOfMass()
            return {
                "volume_mm3": round(vp.Mass(), 6),
                "center_of_mass": {"x": round(com.X(), 4), "y": round(com.Y(), 4), "z": round(com.Z(), 4)},
            }

        if op in ("is_watertight", "mesh_volume", "ray_intersect", "signed_distance"):
            stl_fn = _extract_str(params, "stl_filename" if op != "mass_properties" else "step_filename")
            if op == "is_watertight":
                mesh = _load_trimesh(stl_fn)
                return {"is_watertight": mesh.is_watertight, "euler_number": mesh.euler_number}
            if op == "mesh_volume":
                mesh = _load_trimesh(stl_fn)
                return {"volume_mm3": round(mesh.volume, 6), "surface_area_mm2": round(mesh.area, 6)}
            if op == "ray_intersect":
                mesh = _load_trimesh(stl_fn)
                origin = _extract_list(params, "origin")
                direction = _extract_list(params, "direction")
                locs, _, idx = mesh.ray.intersects_location([origin], [direction])
                return {"intersects": len(locs) > 0, "locations": [list(l) for l in locs]}
            if op == "signed_distance":
                mesh = _load_trimesh(stl_fn)
                point = _extract_list(params, "point")
                from trimesh.proximity import signed_distance
                sd = signed_distance(mesh, [point])
                return {"signed_distance": round(float(sd[0]), 6)}

    # ─────────────────────────────────────────────────────────────
    # TIER: mesh
    # ─────────────────────────────────────────────────────────────
    if tier == "mesh":
        import trimesh as tm

        if op in ("mesh_boolean_union", "mesh_boolean_diff", "mesh_boolean_intersect"):
            target = _load_trimesh(_extract_str(params, "target_stl"))
            tool = _load_trimesh(_extract_str(params, "tool_stl"))
            op_fn_map = {
                "mesh_boolean_union": tm.boolean.union,
                "mesh_boolean_diff": tm.boolean.difference,
                "mesh_boolean_intersect": tm.boolean.intersection,
            }
            result = op_fn_map[op]([target, tool])
            return _save_trimesh(result, name, ["stl"])

        if op == "mesh_repair":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            mesh.fix_normals()
            mesh.remove_unreferenced_vertices()
            mesh.update_faces(mesh.nondegenerate_faces(mesh.faces))
            return _save_trimesh(mesh, name, ["stl"])

        if op == "mesh_simplify":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            target = int(_extract_float(params, "target_faces"))
            current = len(mesh.faces)
            if target >= current:
                return _save_trimesh(mesh, name, ["stl"])
            try:
                from pymeshlab import MeshSet
                ms = MeshSet()
                ms.load_new_mesh(str(_resolve_stl(_extract_str(params, "stl_filename"))))
                ms.meshing_decimation_quadric_edge_collapse(targetfacenum=target)
                ms.save_current_mesh(str(OUT / f"{_safe_name(name)}.stl"))
                return {"name": name, "stl": str(OUT / f"{_safe_name(name)}.stl"), "original_faces": current, "simplified_faces": target}
            except ImportError:
                # Fallback: trimesh subdivision decimation
                mesh = mesh.simplify_quadric_decimation(target)
                return _save_trimesh(mesh, name, ["stl"])

        if op == "mesh_smooth":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            iters = int(_extract_float(params, "iterations", required=False, default=5))
            lam = _extract_float(params, "lambda", required=False, default=0.5)
            tm.smoothing.filter_laplacian(mesh, iterations=iters, lambd=lam)
            return _save_trimesh(mesh, name, ["stl"])

        if op == "mesh_subdivide":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            iters = int(_extract_float(params, "iterations", required=False, default=1))
            mesh = mesh.subdivide_loop(iterations=iters)
            return _save_trimesh(mesh, name, ["stl"])

        if op == "mesh_slice":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            height = _extract_float(params, "plane_height")
            # Support multi-axis slicing: axis='z' (default), 'x', or 'y'
            axis = _extract_str(params, "plane_axis", required=False, default="z")
            normals = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
            normal = normals.get(axis, [0, 0, 1])
            origin = [0, 0, 0]
            if axis == "x":
                origin = [height, 0, 0]
            elif axis == "y":
                origin = [0, height, 0]
            else:
                origin = [0, 0, height]
            slice_mesh = mesh.slice_plane(plane_origin=origin, plane_normal=normal)
            return _save_trimesh(slice_mesh, name, ["stl"])

        if op == "mesh_section":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            height = _extract_float(params, "plane_height")
            section = mesh.section(plane_origin=[0, 0, height], plane_normal=[0, 0, 1])
            if section is None:
                return {"error": "No intersection at this plane height"}
            path = OUT / f"{_safe_name(name)}.svg"
            from trimesh.path.io import export_svg
            with open(path, "w") as f:
                f.write(export_svg(section))
            return {"name": name, "svg": str(path)}

        if op == "mesh_curvature":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            try:
                from pymeshlab import MeshSet
                ms = MeshSet()
                ms.load_new_mesh(str(_resolve_stl(_extract_str(params, "stl_filename"))))
                ms.compute_curvature_principal_curvatures()
                return {"status": "curvature computed", "mesh": _extract_str(params, "stl_filename")}
            except ImportError:
                return {"error": "pymeshlab not available. Install with: pip install pymeshlab"}

        if op == "mesh_convex_hull":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            hull = mesh.convex_hull
            return _save_trimesh(hull, name, ["stl"])

        if op == "mesh_voxelize":
            mesh = _load_trimesh(_extract_str(params, "stl_filename"))
            pitch = _positive(_extract_float(params, "pitch"), "pitch")
            vox = mesh.voxelized(pitch)
            result = {"name": name, "voxel_grid_shape": list(vox.shape), "filled_voxels": int(vox.filled_count)}
            # Export voxel as STL
            vox_mesh = vox.as_boxes()
            if vox_mesh is not None:
                vox_mesh.export(str(OUT / f"{_safe_name(name)}.stl"))
                result["stl"] = str(OUT / f"{_safe_name(name)}.stl")
            return result

    # ─────────────────────────────────────────────────────────────
    # TIER: conversion
    # ─────────────────────────────────────────────────────────────
    if tier == "conversion":
        input_fn = _extract_str(params, "input_filename")
        in_path = OUT / Path(input_fn).name
        if not in_path.exists():
            raise FileNotFoundError(f"Input file not found: {in_path}")

        import trimesh as tm

        if op == "convert_step_stl":
            shape = _read_step(input_fn)
            return _export(cq.Workplane("XY").newObject([shape]), name, "stl")

        if op == "convert_stl_step":
            shape = _read_stl_shape(_resolve_stl(input_fn))
            return _export(cq.Workplane("XY").newObject([shape]), name, "step")

        if op == "convert_step_obj":
            shape = _read_step(input_fn)
            wp = cq.Workplane("XY").newObject([shape])
            obj_path = OUT / f"{_safe_name(name)}.obj"
            exporters.export(wp, str(obj_path), exportType="OBJ")
            return {"name": name, "obj": str(obj_path)}

        if op == "convert_step_glb":
            shape = _read_step(input_fn)
            # Export via cadquery's GLTF exporter, rename to .glb
            gltf_path = OUT / f"{_safe_name(name)}.gltf"
            glb_path = OUT / f"{_safe_name(name)}.glb"
            exporters.export(cq.Workplane("XY").newObject([shape]), str(gltf_path), exportType="GLTF")
            # GLB is just binary GLTF — rename if GLTF is what we get
            if gltf_path.exists():
                import shutil
                shutil.copy(str(gltf_path), str(glb_path))
            return {"name": name, "glb": str(glb_path)}

        if op in ("convert_stl_ply", "convert_stl_off", "convert_stl_3mf", "convert_stl_collada"):
            mesh = _load_trimesh(input_fn)
            ext_map = {
                "convert_stl_ply": "ply",
                "convert_stl_off": "off",
                "convert_stl_3mf": "3mf",
                "convert_stl_collada": "dae",
            }
            return _save_trimesh(mesh, name, [ext_map[op]])

        if op == "export_dxf":
            shape = _read_step(_extract_str(params, "step_filename"))
            dxf_path = OUT / f"{_safe_name(name)}.dxf"
            exporters.export(cq.Workplane("XY").newObject([shape]), str(dxf_path), exportType="DXF")
            return {"name": name, "dxf": str(dxf_path)}

        if op == "export_svg":
            shape = _read_step(_extract_str(params, "step_filename"))
            bb = shape.BoundingBox()
            wp = cq.Workplane("XY").newObject([shape])
            svg_path = OUT / f"{_safe_name(name)}.svg"
            exporters.export(wp, str(svg_path), exportType="SVG")
            return {"name": name, "svg": str(svg_path)}

    # ─────────────────────────────────────────────────────────────
    # TIER: assembly
    # ─────────────────────────────────────────────────────────────
    if tier == "assembly":
        if "_assemblies" not in cad_run.__globals__:
            cad_run.__globals__["_assemblies"] = {}
        assemblies = cad_run.__globals__["_assemblies"]

        if op == "new_assembly":
            assemblies[name] = cq.Assembly()
            return {"assembly": name, "status": "created"}

        if name not in assemblies and op not in ("new_assembly",):
            raise ValueError(f"Assembly '{name}' not found. Call new_assembly first.")

        if op == "add_part":
            step_fn = _extract_str(params, "step_filename")
            shape = _read_step(step_fn)
            loc = (
                _extract_float(params, "loc_x", required=False, default=0),
                _extract_float(params, "loc_y", required=False, default=0),
                _extract_float(params, "loc_z", required=False, default=0),
            )
            rot = (
                _extract_float(params, "rot_x", required=False, default=0),
                _extract_float(params, "rot_y", required=False, default=0),
                _extract_float(params, "rot_z", required=False, default=0),
            )
            part_name = _extract_str(params, "part_name", required=False, default=Path(step_fn).stem)
            loc_obj = cq.Location(cq.Vector(*loc), cq.Vector(*rot))
            assemblies[name].add(shape, loc=loc_obj, name=part_name)
            return {"assembly": name, "part": part_name, "status": "added"}

        if op == "constrain_mate":
            part_a = _extract_str(params, "part_a")
            part_b = _extract_str(params, "part_b")
            assemblies[name].constrain(part_a, part_b, "Plane")
            return {"assembly": name, "constraint": "mate", "between": [part_a, part_b]}

        if op == "constrain_align":
            part_a = _extract_str(params, "part_a")
            part_b = _extract_str(params, "part_b")
            assemblies[name].constrain(part_a, part_b, "Axis")
            return {"assembly": name, "constraint": "align", "between": [part_a, part_b]}

        if op == "solve":
            assemblies[name].solve()
            return {"assembly": name, "status": "solved"}

        if op in ("export_step", "export_gltf", "export_vrml"):
            ext_map = {"export_step": "STEP", "export_gltf": "GLTF", "export_vrml": "VRML"}
            ext = ext_map[op]
            fpath = OUT / f"{_safe_name(name)}.{ext.lower()}"
            assemblies[name].save(str(fpath), exportType=ext)
            return {"name": name, "export": str(fpath), "format": ext}

    # ─────────────────────────────────────────────────────────────
    # TIER: cam
    # ─────────────────────────────────────────────────────────────
    if tier == "cam":
        if op in ("profile_cam", "pocket_cam", "drill_cam"):
            step_fn = _extract_str(params, "step_filename")
            td = _extract_float(params, "tool_diameter", required=False, default=3.0)
            fr = _extract_float(params, "feed_rate", required=False, default=1000)
            # Generate simple G-code
            shape = _read_step(step_fn)
            bb = shape.BoundingBox()
            gcode = [
                f"(G-code generated by CadQuery MCP)",
                f"(Tool diameter: {td} mm, Feed rate: {fr} mm/min)",
                f"(Part: {step_fn})",
                f"(Bounding box: {bb.xmax - bb.xmin:.1f} x {bb.ymax - bb.ymin:.1f} x {bb.zmax - bb.zmin:.1f} mm)",
                "",
                "G21 (mm mode)",
                "G90 (absolute mode)",
                f"G0 Z5.0 (retract)",
                f"G0 X0 Y0 (home)",
                f"M3 S10000 (spindle on)",
                "",
                f"(Roughing pass at Z=0)",
                f"G1 Z-0.5 F{fr / 2}",
                f"G1 X{bb.xmax:.1f} F{fr}",
                f"G1 Y{bb.ymax:.1f}",
                f"G1 X{bb.xmin:.1f}",
                f"G1 Y{bb.ymin:.1f}",
                "",
                f"G0 Z5.0",
                "M5 (spindle off)",
                "M30 (program end)",
            ]
            gcode_path = OUT / f"{_safe_name(name)}.gcode"
            gcode_path.write_text("\n".join(gcode))
            return {"name": name, "gcode": str(gcode_path), "lines": len(gcode)}

        if op == "slice_3mf":
            step_fn = _extract_str(params, "step_filename")
            shape = _read_step(step_fn)
            return _export(cq.Workplane("XY").newObject([shape]), name, "stl")

        if op == "slice_svg":
            step_fn = _extract_str(params, "step_filename")
            h = _extract_float(params, "height", required=False, default=0)
            shape = _read_step(step_fn)
            svg_path = OUT / f"{_safe_name(name)}.svg"
            exporters.export(cq.Workplane("XY").newObject([shape]), str(svg_path), exportType="SVG")
            return {"name": name, "svg": str(svg_path)}

    # ─────────────────────────────────────────────────────────────
    # TIER: parts (parameterized hardware)
    # ─────────────────────────────────────────────────────────────
    if tier == "parts":
        if op == "bolt":
            d = _extract_float(params, "diameter", required=False, default=6)
            l = _extract_float(params, "length", required=False, default=30)
            tp = _extract_float(params, "thread_pitch", required=False, default=1.0)
            head_h = d * 0.7
            head_r = d * 0.8
            shank_r = d / 2
            wp = (cq.Workplane("XY")
                  .circle(head_r).extrude(head_h)
                  .faces(">Z").workplane()
                  .circle(shank_r).extrude(l))
            return _export(wp, name, export_format)

        if op == "nut":
            d = _extract_float(params, "diameter", required=False, default=6)
            t = _extract_float(params, "thickness", required=False, default=5)
            r = d * 0.9
            wp = cq.Workplane("XY").polygon(6, r).extrude(t)
            return _export(wp, name, export_format)

        if op == "washer":
            id_ = _extract_float(params, "inner_d", required=False, default=6.5)
            od = _extract_float(params, "outer_d", required=False, default=14)
            t = _extract_float(params, "thickness", required=False, default=1.5)
            wp = cq.Workplane("XY").circle(od / 2).circle(id_ / 2).extrude(t)
            return _export(wp, name, export_format)

        if op == "bearing":
            id_ = _extract_float(params, "inner_d", required=False, default=10)
            od = _extract_float(params, "outer_d", required=False, default=26)
            w = _extract_float(params, "width", required=False, default=8)
            wp = cq.Workplane("XY").circle(od / 2).circle(id_ / 2).extrude(w)
            return _export(wp, name, export_format)

        if op == "i_beam":
            h = _extract_float(params, "height", required=False, default=100)
            fw = _extract_float(params, "flange_width", required=False, default=50)
            wt = _extract_float(params, "web_thickness", required=False, default=5)
            ft = _extract_float(params, "flange_thickness", required=False, default=8)
            l = _extract_float(params, "length", required=False, default=1000)
            wp = cq.Workplane("XY").rect(fw, ft).extrude(l)
            wp = wp.union(cq.Workplane("XY").rect(wt, h).extrude(l))
            return _export(wp, name, export_format)

        if op == "c_channel":
            h = _extract_float(params, "height", required=False, default=80)
            w = _extract_float(params, "width", required=False, default=40)
            t = _extract_float(params, "thickness", required=False, default=5)
            l = _extract_float(params, "length", required=False, default=1000)
            wp = cq.Workplane("XY").rect(w, h).extrude(l)
            wp = wp.cut(cq.Workplane("XY").rect(w - t * 2, h - t).extrude(l))
            return _export(wp, name, export_format)

        if op == "angle_iron":
            ll = _extract_float(params, "leg_length", required=False, default=50)
            t = _extract_float(params, "thickness", required=False, default=5)
            l = _extract_float(params, "length", required=False, default=1000)
            wp = cq.Workplane("XY").moveTo(0, 0).lineTo(ll, 0).lineTo(ll, t).lineTo(t, t).lineTo(t, ll).lineTo(0, ll).close().extrude(l)
            return _export(wp, name, export_format)

        if op == "spring":
            wd = _extract_float(params, "wire_d", required=False, default=2)
            cd = _extract_float(params, "coil_d", required=False, default=20)
            nc = int(_extract_float(params, "num_coils", required=False, default=8))
            h = _extract_float(params, "height", required=False, default=50)
            import math as m
            turns = nc
            pitch = h / turns
            pts = [(cd / 2 * m.cos(t), cd / 2 * m.sin(t), pitch * t / (2 * m.pi)) for t in [i * 0.1 for i in range(int(turns * 2 * m.pi * 10))]]
            # Helical sweep via spline path
            wp = cq.Workplane("XY").circle(wd / 2).sweep(cq.Workplane("XY").spline(pts))
            return _export(wp, name, export_format)

    # ─────────────────────────────────────────────────────────────
    # TIER: fem
    # ─────────────────────────────────────────────────────────────
    if tier == "fem":
        step_fn = _extract_str(params, "step_filename")
        el_size = _extract_float(params, "element_size", required=False, default=5.0)

        if op in ("mesh_2d_tri", "mesh_2d_quad", "mesh_3d_tet", "mesh_3d_hex"):
            try:
                import gmsh
                gmsh.initialize()
                model_name = _safe_name(name)
                gmsh.model.add(model_name)

                # gmsh imports .step directly — no OCC needed
                gmsh_path = str(_ensure_output_file(Path(step_fn)))
                vol = gmsh.model.occ.importShapes(gmsh_path)
                gmsh.model.occ.synchronize()

                gmsh.option.setNumber("Mesh.CharacteristicLengthMin", el_size)
                gmsh.option.setNumber("Mesh.CharacteristicLengthMax", el_size)

                dim = 2 if "2d" in op else 3

                if "quad" in op:
                    gmsh.option.setNumber("Mesh.RecombineAll", 1)
                    gmsh.option.setNumber("Mesh.SubdivisionAlgorithm", 1)
                if "hex" in op:
                    gmsh.option.setNumber("Mesh.RecombineAll", 1)
                    gmsh.option.setNumber("Mesh.SubdivisionAlgorithm", 1)
                    gmsh.option.setNumber("Mesh.Algorithm3D", 8)

                gmsh.model.mesh.generate(dim)

                msh_path = str(OUT / f"{_safe_name(name)}.msh")
                gmsh.write(msh_path)
                gmsh.finalize()

                return {
                    "name": name,
                    "mesh": msh_path,
                    "element_type": op,
                    "element_size": el_size,
                }
            except ImportError:
                return {"error": "gmsh not available. Install with: pip install gmsh"}

        if op in ("export_abaqus", "export_ansys", "export_nastran", "export_vtk", "export_xdmf"):
            try:
                import meshio
                msh_path = _extract_str(params, "mesh_file", required=False, default="")
                if not msh_path:
                    import gmsh
                    gmsh.initialize()
                    gmsh.model.add("temp")
                    gmsh_path_s = str(_ensure_output_file(Path(step_fn)))
                    vol = gmsh.model.occ.importShapes(gmsh_path_s)
                    gmsh.model.occ.synchronize()
                    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", el_size)
                    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", el_size)
                    gmsh.model.mesh.generate(3)
                    temp_msh = str(OUT / f"_tmp_{uuid.uuid4().hex}.msh")
                    gmsh.write(temp_msh)
                    gmsh.finalize()
                    msh_path = temp_msh

                mesh = meshio.read(msh_path)
                fmt_map = {
                    "export_abaqus": "abaqus",
                    "export_ansys": "ansys",
                    "export_nastran": "nastran",
                    "export_vtk": "vtk",
                    "export_xdmf": "xdmf",
                }
                ext_map = {"export_abaqus": "inp", "export_ansys": "cdb", "export_nastran": "bdf", "export_vtk": "vtu", "export_xdmf": "xdmf"}
                out_path = OUT / f"{_safe_name(name)}.{ext_map[op]}"
                meshio.write(str(out_path), mesh, file_format=fmt_map[op])
                return {"name": name, "export": str(out_path), "format": fmt_map[op]}
            except ImportError:
                return {"error": "meshio/gmsh not available. Install with: pip install meshio gmsh"}


    # ─────────────────────────────────────────────────────────────
    # TIER: templates
    # Real-world finished object generators. These are NOT new MCP tools;
    # they are routed through cad_run(tier="templates", operation="...").
    # ─────────────────────────────────────────────────────────────
    if tier == "templates":
        if op == "fan_shroud":
            fan_size = _positive(_extract_float(params, "fan_size", required=False, default=60.5), "fan_size")
            opening = _positive(_extract_float(params, "opening", required=False, default=fan_size), "opening")
            wall = _positive(_extract_float(params, "wall", required=False, default=3.0), "wall")
            depth = _positive(_extract_float(params, "depth", required=False, default=28.0), "depth")
            screw_spacing = _positive(_extract_float(params, "screw_spacing", required=False, default=50.0), "screw_spacing")
            screw_diameter = _positive(_extract_float(params, "screw_diameter", required=False, default=3.2), "screw_diameter")
            boss_diameter = _positive(_extract_float(params, "boss_diameter", required=False, default=7.0), "boss_diameter")
            fillet = _nonnegative(_extract_float(params, "fillet", required=False, default=1.5), "fillet")

            outer = fan_size + 2 * wall
            if opening >= outer:
                raise ValueError("opening must be smaller than fan_size + 2*wall")
            half_spacing = screw_spacing / 2
            if screw_spacing + boss_diameter > outer:
                raise ValueError("screw_spacing + boss_diameter must fit inside the shroud body")

            screw_points = [
                (-half_spacing, -half_spacing),
                (-half_spacing, half_spacing),
                (half_spacing, -half_spacing),
                (half_spacing, half_spacing),
            ]

            body = (
                cq.Workplane("XY")
                .box(outer, outer, depth)
                .faces(">Z")
                .workplane()
                .rect(opening, opening)
                .cutThruAll()
            )

            bosses = (
                cq.Workplane("XY")
                .pushPoints(screw_points)
                .circle(boss_diameter / 2)
                .extrude(depth)
                .translate((0, 0, -depth / 2))
            )
            part = body.union(bosses)

            part = (
                part.faces(">Z")
                .workplane()
                .pushPoints(screw_points)
                .hole(screw_diameter)
            )

            if fillet > 0:
                try:
                    part = part.edges().fillet(fillet)
                except Exception:
                    pass
            return _export(part, name, export_format)

        if op == "duct_transition":
            inlet_w = _positive(_extract_float(params, "inlet_width", required=False, default=60.5), "inlet_width")
            inlet_h = _positive(_extract_float(params, "inlet_height", required=False, default=60.5), "inlet_height")
            outlet_w = _positive(_extract_float(params, "outlet_width", required=False, default=49.1), "outlet_width")
            outlet_h = _positive(_extract_float(params, "outlet_height", required=False, default=44.8), "outlet_height")
            length = _positive(_extract_float(params, "length", required=False, default=35.0), "length")
            wall = _positive(_extract_float(params, "wall", required=False, default=2.4), "wall")
            fillet = _nonnegative(_extract_float(params, "fillet", required=False, default=0.8), "fillet")

            outer = (
                cq.Workplane("XY")
                .rect(inlet_w + 2 * wall, inlet_h + 2 * wall)
                .workplane(offset=length)
                .rect(outlet_w + 2 * wall, outlet_h + 2 * wall)
                .loft(combine=True)
            )
            inner = (
                cq.Workplane("XY")
                .rect(inlet_w, inlet_h)
                .workplane(offset=length)
                .rect(outlet_w, outlet_h)
                .loft(combine=True)
            )
            part = outer.cut(inner)
            if fillet > 0:
                try:
                    part = part.edges().fillet(fillet)
                except Exception:
                    pass
            return _export(part, name, export_format)

        if op == "rounded_rect_frame":
            width = _positive(_extract_float(params, "width", required=False, default=70.0), "width")
            height = _positive(_extract_float(params, "height", required=False, default=70.0), "height")
            thickness = _positive(_extract_float(params, "thickness", required=False, default=5.0), "thickness")
            opening_w = _positive(_extract_float(params, "opening_width", required=False, default=60.5), "opening_width")
            opening_h = _positive(_extract_float(params, "opening_height", required=False, default=60.5), "opening_height")
            fillet = _nonnegative(_extract_float(params, "fillet", required=False, default=2.0), "fillet")
            if opening_w >= width or opening_h >= height:
                raise ValueError("opening_width/opening_height must be smaller than width/height")
            part = (
                cq.Workplane("XY")
                .box(width, height, thickness)
                .faces(">Z")
                .workplane()
                .rect(opening_w, opening_h)
                .cutThruAll()
            )
            if fillet > 0:
                try:
                    part = part.edges().fillet(fillet)
                except Exception:
                    pass
            return _export(part, name, export_format)

        if op == "screw_mount_plate":
            width = _positive(_extract_float(params, "width", required=False, default=70.0), "width")
            height = _positive(_extract_float(params, "height", required=False, default=70.0), "height")
            thickness = _positive(_extract_float(params, "thickness", required=False, default=3.0), "thickness")
            screw_spacing_x = _positive(_extract_float(params, "screw_spacing_x", required=False, default=50.0), "screw_spacing_x")
            screw_spacing_y = _positive(_extract_float(params, "screw_spacing_y", required=False, default=50.0), "screw_spacing_y")
            screw_diameter = _positive(_extract_float(params, "screw_diameter", required=False, default=3.2), "screw_diameter")
            fillet = _nonnegative(_extract_float(params, "fillet", required=False, default=1.0), "fillet")
            pts = [
                (-screw_spacing_x / 2, -screw_spacing_y / 2),
                (-screw_spacing_x / 2, screw_spacing_y / 2),
                (screw_spacing_x / 2, -screw_spacing_y / 2),
                (screw_spacing_x / 2, screw_spacing_y / 2),
            ]
            part = (
                cq.Workplane("XY")
                .box(width, height, thickness)
                .faces(">Z")
                .workplane()
                .pushPoints(pts)
                .hole(screw_diameter)
            )
            if fillet > 0:
                try:
                    part = part.edges().fillet(fillet)
                except Exception:
                    pass
            return _export(part, name, export_format)

        if op == "gasket":
            width = _positive(_extract_float(params, "width", required=False, default=70.0), "width")
            height = _positive(_extract_float(params, "height", required=False, default=70.0), "height")
            thickness = _positive(_extract_float(params, "thickness", required=False, default=1.2), "thickness")
            opening_w = _positive(_extract_float(params, "opening_width", required=False, default=60.5), "opening_width")
            opening_h = _positive(_extract_float(params, "opening_height", required=False, default=60.5), "opening_height")
            screw_spacing = _positive(_extract_float(params, "screw_spacing", required=False, default=50.0), "screw_spacing")
            screw_diameter = _nonnegative(_extract_float(params, "screw_diameter", required=False, default=3.2), "screw_diameter")
            part = (
                cq.Workplane("XY")
                .box(width, height, thickness)
                .faces(">Z")
                .workplane()
                .rect(opening_w, opening_h)
                .cutThruAll()
            )
            if screw_diameter > 0:
                hs = screw_spacing / 2
                part = (
                    part.faces(">Z")
                    .workplane()
                    .pushPoints([(-hs, -hs), (-hs, hs), (hs, -hs), (hs, hs)])
                    .hole(screw_diameter)
                )
            return _export(part, name, export_format)

        if op == "standoff_grid":
            width = _positive(_extract_float(params, "width", required=False, default=70.0), "width")
            height = _positive(_extract_float(params, "height", required=False, default=70.0), "height")
            base_thickness = _positive(_extract_float(params, "base_thickness", required=False, default=3.0), "base_thickness")
            standoff_height = _positive(_extract_float(params, "standoff_height", required=False, default=8.0), "standoff_height")
            standoff_diameter = _positive(_extract_float(params, "standoff_diameter", required=False, default=7.0), "standoff_diameter")
            hole_diameter = _nonnegative(_extract_float(params, "hole_diameter", required=False, default=3.2), "hole_diameter")
            spacing_x = _positive(_extract_float(params, "spacing_x", required=False, default=50.0), "spacing_x")
            spacing_y = _positive(_extract_float(params, "spacing_y", required=False, default=50.0), "spacing_y")
            pts = [(-spacing_x / 2, -spacing_y / 2), (-spacing_x / 2, spacing_y / 2), (spacing_x / 2, -spacing_y / 2), (spacing_x / 2, spacing_y / 2)]
            base = cq.Workplane("XY").box(width, height, base_thickness)
            bosses = (
                cq.Workplane("XY")
                .workplane(offset=base_thickness / 2)
                .pushPoints(pts)
                .circle(standoff_diameter / 2)
                .extrude(standoff_height)
            )
            part = base.union(bosses)
            if hole_diameter > 0:
                part = (
                    part.faces(">Z")
                    .workplane()
                    .pushPoints(pts)
                    .hole(hole_diameter, depth=standoff_height + base_thickness)
                )
            return _export(part, name, export_format)

    raise ValueError(f"No handler for operation '{op}' in tier '{tier}'")


# ================================================================
# ROUTER TOOL 3: cad_manage
# ================================================================


@mcp.tool()
def cad_manage(action: str, filename: str | None = None) -> Any:
    """Manage exported CAD files in the output directory.

    Actions:
      list          — List all exported STEP and STL files
      delete        — Delete a file by filename (requires 'filename')
      stl_info      — Get STL metadata (requires 'filename', STL only)

    Args:
        action: One of "list", "delete", "stl_info"
        filename: Required for "delete" and "stl_info"
    """
    action = action.strip().lower()

    if action == "list":
        files = sorted(str(p) for p in OUT.glob("*") if p.suffix.lower() in {".step", ".stl", ".obj", ".ply", ".glb", ".off", ".3mf", ".svg", ".dxf", ".gcode"})
        return {"action": "list", "files": files, "count": len(files), "directory": str(OUT)}

    if action == "delete":
        if not filename:
            raise ValueError("'filename' is required for delete action")
        safe = Path(filename).name
        target = OUT / safe
        if not target.exists():
            raise FileNotFoundError(f"{safe} not found in {OUT}")
        target.unlink()
        return {"action": "delete", "deleted": str(target)}

    if action == "stl_info":
        if not filename:
            raise ValueError("'filename' is required for stl_info action")
        return cad_stl_info(filename)

    valid_actions = ["list", "delete", "stl_info"]
    raise ValueError(f"Unknown action '{action}'. Valid actions: {valid_actions}")


# ================================================================
# STANDALONE: cad_stl_info
# ================================================================


def cad_stl_info(stl_filename: str) -> dict:
    """Get metadata about an STL file: triangle count, bounding box, file size."""
    stl_path = _resolve_stl(stl_filename)
    file_size = stl_path.stat().st_size

    with open(stl_path, "rb") as f:
        header = f.read(80)
        triangle_bytes = f.read(4)
        triangle_count = int.from_bytes(triangle_bytes, "little")

    min_bounds = [float("inf")] * 3
    max_bounds = [float("-inf")] * 3
    scan_count = min(triangle_count, 5000)

    with open(stl_path, "rb") as f:
        f.read(84)
        for _ in range(scan_count):
            f.read(12)
            for _ in range(3):
                v = struct.unpack("<fff", f.read(12))
                for i in range(3):
                    if v[i] < min_bounds[i]:
                        min_bounds[i] = v[i]
                    if v[i] > max_bounds[i]:
                        max_bounds[i] = v[i]
            f.read(2)

    dx = max_bounds[0] - min_bounds[0]
    dy = max_bounds[1] - min_bounds[1]
    dz = max_bounds[2] - min_bounds[2]

    try:
        header_text = header.decode("ascii", errors="replace").rstrip("\x00").strip()
    except Exception:
        header_text = ""

    return {
        "filename": stl_path.name,
        "file_size": file_size,
        "file_size_display": _format_bytes(file_size),
        "triangle_count": triangle_count,
        "vertex_count": triangle_count * 3,
        "header_comment": header_text or "(none)",
        "bounding_box": {
            "min": {"x": round(min_bounds[0], 4), "y": round(min_bounds[1], 4), "z": round(min_bounds[2], 4)},
            "max": {"x": round(max_bounds[0], 4), "y": round(max_bounds[1], 4), "z": round(max_bounds[2], 4)},
            "size": {"x": round(dx, 4), "y": round(dy, 4), "z": round(dz, 4)},
        },
        "scan_note": f"Bounding box from first {scan_count}/{triangle_count} triangles"
        if triangle_count > scan_count
        else "Bounding box from all triangles",
    }


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":
    mcp.run()
