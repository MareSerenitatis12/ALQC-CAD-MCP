# CadQuery MCP — AI CAD Suite (Tiered Router, 80+ Operations, 13 Tiers)

[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://docker.com)
[![MCP](https://img.shields.io/badge/MCP-server-purple)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/python-3.11+-green)](https://python.org)
[![CadQuery](https://img.shields.io/badge/cadquery-2.5+-orange)](https://cadquery.readthedocs.io)

A **Model Context Protocol (MCP)** server that exposes the full power of [CadQuery](https://cadquery.readthedocs.io), [trimesh](https://trimsh.org), [gmsh](https://gmsh.info), and more — through a **lean 3-tool routing interface**. Instead of flooding the AI namespace with 80+ flat tools, the model discovers capabilities via `cad_help()`, executes any operation via `cad_run()`, and manages outputs via `cad_manage()`.

> **Design philosophy:** A model's tool namespace is precious. This server collapses an entire CAD suite into **3 router tools** across **13 capability tiers** — each tier a logically grouped set of operations.

---

## Features

- **80+ parametric CAD operations** across 13 tiers — primitives, sketches, booleans, mesh processing, FEM, CAM, assembly, format conversion, and more
- **3-router-tool architecture** — model calls `cad_help()` → discovers → calls `cad_run()` with tier + operation + params
- **Streamable HTTP transport** via `supergateway` — long-lived connections with health checks
- **Docker-first** deployment — single `docker compose up -d` to get a fully isolated CAD server
- **13th tier: `templates`** — real-world reusable generators (fan shrouds, ducts, brackets, gaskets, standoff grids)
- **Multi-format support** — STEP, STL, OBJ, GLB, PLY, 3MF, COLLADA, DXF, SVG, G-code, FEM mesh formats (INP, CDB, BDF, VTU, XDMF)
- **Parametric hardware library** — bolts, nuts, washers, bearings, I-beams, C-channels, angle iron, springs
- **STL mesh pipeline** — import, repair, simplify, smooth, subdivide, slice, boolean, convex hull, voxelize, curvature analysis
- **CAM G-code generation** — profile, pocket, drill cycles
- **FEM mesh export** — tetrahedral/hexahedral meshing via gmsh, solver format export via meshio
- **Assembly support** — multi-part assemblies with constraints, export as STEP/GLTF/VRML
- **CAD analysis** — mass properties, bounding box, surface area, ray intersection, signed distance, watertight check

---

## Architecture: Tiered Router

The model sees **only 3 tools** in its namespace. All 80+ operations live behind these routers:

```
┌─ Model's Tool Namespace ───────────────────────────────────────┐
│                                                                  │
│  cad_help(tier?)           → discover tiers + operations         │
│  cad_run(tier, op, params) → execute any CAD operation           │
│  cad_manage(action, file?) → list / delete / inspect output      │
│                                                                  │
│  (3 tools — NOT 80+ flat tools)                                 │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼  (internal dispatch)
┌──────────────────────────────────────────────────────────────────┐
│  13 Capability Tiers — 80+ operations                            │
│                                                                  │
│  primitive    sketch_2d    boolean_3d    stl                     │
│  sketch_draw  analysis     mesh         conversion               │
│  assembly     cam          parts        fem                      │
│  templates ← NEW!                                                │
└──────────────────────────────────────────────────────────────────┘
```

### Why this matters

- **Keeps the model's tool slot count low** — critical for LLMs with tight tool budgets
- **Self-documenting** — `cad_help()` returns tier descriptions + available operations + example usage
- **Extensible** — adding a new tier requires zero model-side changes (just a new TIERS entry + handler)
- **Type-safe parameter dispatch** — each operation validates its own params with clear error messages

---

## Quick Start (Docker)

```bash
# Clone or copy the project files, then:
docker compose up -d --build

# Verify it's running
curl http://localhost:8012/health
# → {"status":"ok"}
```

The server listens on `http://localhost:8012/mcp` using [Streamable HTTP](https://spec.modelcontextprotocol.io/) transport.

---

## Installation Options

### Option 1: Docker (Recommended)

```bash
docker compose up -d --build
```

All dependencies (CadQuery, OpenCASCADE, trimesh, gmsh, meshio, pymeshlab, manifold3d, etc.) are pre-installed in the container. Output files persist in [`./cad_output/`](./cad_output) via a bind mount.

### Option 2: Manual pip (Ubuntu/Debian)

```bash
# System dependencies for CadQuery/OpenCASCADE
sudo apt-get install -y \
  python3-dev build-essential pkg-config cmake \
  libgl1-mesa-dev libglu1-mesa-dev libxrender-dev libxext-dev \
  libxt-dev libxi-dev libsm-dev libglib2.0-0 libgomp1 \
  libspatialindex-dev

# Python packages
pip install 'cadquery>=2.5' 'mcp>=1.0' 'trimesh[easy]>=4.0' \
  manifold3d pymeshlab numpy-stl numpy scipy networkx shapely \
  rtree sympy meshio gmsh ezdxf svg.path svgpathtools lxml \
  pillow pycollada pygltflib ifcopenshell scikit-image

# Supergateway for Streamable HTTP transport
npm install -g supergateway

# Run
supergateway --stdio "python cadquery_mcp.py" \
  --outputTransport streamableHttp \
  --streamableHttpPath /mcp --port 8012 --host 0.0.0.0 \
  --cors --healthEndpoint /health
```

### Option 3: Conda (via environment.yml)

```bash
conda env create -f environment.yml
conda activate base
# Then pip install the dependencies listed in Option 2
```

> **Note:** The [`environment.yml`](environment.yml) is a reference stub. All actual dependencies are installed via `pip` in the [`Dockerfile`](Dockerfile). For conda, manually install the pip packages above.

---

## MCP Client Configuration

### Claude Desktop

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cadquery": {
      "type": "streamableHttp",
      "url": "http://localhost:8012/mcp"
    }
  }
}
```

### VS Code (MCP Extension)

```json
{
  "mcp": {
    "servers": {
      "cadquery-mcp": {
        "type": "streamableHttp",
        "url": "http://localhost:8012/mcp"
      }
    }
  }
}
```

### Cline / Roo Code

```json
{
  "mcpServers": {
    "cadquery-mcp": {
      "type": "streamableHttp",
      "url": "http://localhost:8012/mcp"
    }
  }
}
```

### Custom MCP Client (Python)

```python
import requests

MCP_URL = "http://localhost:8012/mcp"

# Discover tiers
response = requests.post(MCP_URL, json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "cad_help",
        "arguments": {}
    }
})
print(response.json())

# Create a box
response = requests.post(MCP_URL, json={
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "cad_run",
        "arguments": {
            "tier": "primitive",
            "operation": "box",
            "params": {"width": 50, "depth": 30, "height": 20},
            "export_format": "both"
        }
    }
})
print(response.json())
```

---

## Tool Reference

### 1. `cad_help(tier?)` — Discover Capabilities

The discovery tool. Call without arguments to list all 13 tiers. Call with a tier name to see available operations and their descriptions.

| Call | Returns |
|------|---------|
| `cad_help()` | All 13 tiers with labels, descriptions, and operation counts |
| `cad_help("mesh")` | Operations + descriptions for the mesh processing tier |
| `cad_help("fem")` | Operations + descriptions for the FEM tier |
| `cad_help("templates")` | The 6 real-world template generators |

### 2. `cad_run(tier, operation, params, export_format?)` — Execute CAD Operations

The execution router. Parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `tier` | `string` | Tier name (e.g. `"primitive"`, `"mesh"`, `"templates"`, `"fem"`) |
| `operation` | `string` | Operation name within the tier (e.g. `"box"`, `"mesh_smooth"`, `"fan_shroud"`) |
| `params` | `dict` | Operation-specific parameters (see tier tables below) |
| `export_format` | `string` | Optional. `"step"` (default), `"stl"`, or `"both"` |

### 3. `cad_manage(action, filename?)` — File Management

| Action | Parameters | Description |
|--------|-----------|-------------|
| `list` | none | List all exported STEP, STL, OBJ, GLB, PLY, OFF, 3MF, SVG, DXF, G-code files |
| `delete` | `filename` | Delete a file from the output directory |
| `stl_info` | `filename` | Get STL metadata (triangle count, bounding box, file size, header comment) |

---

## Complete Tier Reference — All 13 Tiers with Full Parameter Docs

### Tier 1: `primitive` — Geometric Primitives

Create basic 3D solids from scratch.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `box` | `width`, `depth`, `height` | Centered rectangular box |
| `cylinder` | `radius`, `height` | Vertical cylinder on XY plane |
| `tube` | `outer_radius`, `inner_radius`, `height` | Hollow cylinder (inner < outer) |
| `sphere` | `radius` | Solid sphere |
| `wedge` | `dx`, `dy`, `dz`, `xmin`, `zmin`, `xmax`, `zmax` | Trapezoidal wedge |
| `torus` | `major_radius`, `minor_radius` | Donut shape (via OCC BRepPrimAPI) |
| `cone` | `bottom_radius`, `top_radius`, `height` | Tapered cone/truncated cone |

**Example:**
```python
cad_run("primitive", "torus", {"major_radius": 30, "minor_radius": 8, "name": "donut"})
# → {"name": "donut", "step": "/app/cad_output/donut.step"}
```

### Tier 2: `sketch_2d` — 2D Sketches & Profiles

Create 2D profiles, optionally extruded into 3D.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `rect` | `width`, `height`, `extrude_distance?` | Rectangle, optionally extruded |
| `circle` | `radius`, `extrude_distance?` | Circle, optionally extruded |
| `polygon` | `radius`, `sides` (3–128), `extrude_distance?` | Regular polygon |
| `slot` | `length`, `diameter`, `extrude_distance?` | Stadium/obround shape |
| `ellipse` | `x_radius`, `y_radius`, `extrude_distance?` | Elliptical profile |
| `trapezoid` | `width`, `height`, `angle_a`, `angle_b`, `extrude_distance?` | Trapezoid with adjustable angles |
| `gear` | `num_teeth`, `pitch_diameter`, `pressure_angle?` (default 20°), `height?` | Spur gear approximation |
| `text` | `text`, `font_size`, `height` | 3D embossed text (raised) |

### Tier 3: `boolean_3d` — Boolean & 3D Operations

Modify existing STEP files. All operations read files from the output directory by filename.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `cut` | `target_step`, `tool_step` | Boolean subtraction (target − tool) |
| `union` | `target_step`, `tool_step` | Boolean fusion |
| `intersect` | `target_step`, `tool_step` | Boolean intersection |
| `fillet` | `step_filename`, `radius` | Round all edges |
| `chamfer` | `step_filename`, `length`, `length2?` | Bevel all edges |
| `shell` | `step_filename`, `thickness` | Hollow out a solid (positive = outward) |
| `split` | `step_filename`, `keep_top?` (True), `keep_bottom?` (True) | Split at Z=0 plane |
| `mirror` | `step_filename`, `plane` (XY/XZ/YZ) | Mirror across axis plane |
| `extrude_face` | `step_filename`, `distance` | Extrude the top face outward |
| `revolve` | `step_filename`, `angle_degrees?` (default 360) | Revolve the top face |
| `thicken_face` | `step_filename`, `thickness` | Thicken the top face into a solid |

### Tier 4: `stl` — STL Import & Transform

Import, inspect, and transform STL mesh files.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `import_stl` | `stl_filename` | Import STL → CAD solid → export as STEP/STL |
| `transform_stl` | `stl_filename`, `scale?`, `rotate_x/y/z?`, `translate_x/y/z?` | Scale, rotate, translate → re-export |
| `stl_info` | `stl_filename` | Binary STL metadata (triangles, bounding box, size, header) |
| `stl_fix_normals` | `stl_filename` | Recompute consistent face normals |
| `stl_merge` | `stl_filenames` (list) | Merge multiple STL files into one |

### Tier 5: `sketch_draw` — Procedural Drawing

Build 2D profiles programmatically with lines, arcs, and splines, then extrude, revolve, loft, or sweep into 3D. Uses in-memory sketch state keyed by name.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `start_sketch` | `plane?` (XY/XZ/YZ, default XY) | Initialize a named sketch workspace |
| `line` | `sketch_name?`, `x`, `y` | Add a line segment (relative) |
| `line_to` | `sketch_name?`, `x`, `y` | Line to absolute point |
| `h_line` | `sketch_name?`, `distance` | Horizontal line |
| `v_line` | `sketch_name?`, `distance` | Vertical line |
| `arc_three` | `sketch_name?`, `x1`, `y1`, `x2`, `y2` | Three-point arc |
| `arc_tangent` | `sketch_name?`, `end_x`, `end_y` | Tangent arc |
| `spline` | `sketch_name?`, `points` (list of [x,y]) | Interpolated spline |
| `polyline` | `sketch_name?`, `points` (list of [x,y]) | Connected line segments |
| `close` | `sketch_name?` | Close wire back to start point |
| `mirror_sketch` | `sketch_name?` | Mirror across axis |
| `offset_2d` | `sketch_name?`, `distance` | Offset the 2D wire |
| `extrude` | `sketch_name?`, `distance` | Extrude sketch into 3D |
| `revolve_sketch` | `sketch_name?`, `angle_degrees?` | Revolve (default 360°) |
| `loft` | `sketch_name?`, `sketch_names` (list) | Loft between multiple sketches |
| `sweep` | `profile_name`, `path_name` | Sweep profile along a path |

**Workflow:**
```
1. start_sketch("my_sketch", "XY")
2. h_line("my_sketch", 40)
3. v_line("my_sketch", 30)
4. arc_tangent("my_sketch", 0, 15)
5. close("my_sketch")
6. extrude("my_sketch", 10)
```

### Tier 6: `analysis` — Analysis & Query

Query geometric and physical properties of STEP and STL files.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `mass_properties` | `step_filename` | Volume, surface area, center of mass |
| `bounding_box` | `step_filename` | Axis-aligned bounding box extents |
| `surface_area` | `step_filename` | Total surface area (OCC BRepGProp) |
| `section_props` | `step_filename`, `cut_plane?` | 2D section properties |
| `is_watertight` | `stl_filename` | Watertight check + Euler number |
| `mesh_volume` | `stl_filename` | Volume + area from STL mesh via trimesh |
| `ray_intersect` | `stl_filename`, `origin` [x,y,z], `direction` [x,y,z] | Ray-mesh intersection test |
| `signed_distance` | `stl_filename`, `point` [x,y,z] | Signed distance from point to mesh |

### Tier 7: `mesh` — Mesh Processing (STL Pipeline)

Full mesh processing pipeline via trimesh + optional pymeshlab.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `mesh_boolean_union` | `target_stl`, `tool_stl` | Union of two STL meshes |
| `mesh_boolean_diff` | `target_stl`, `tool_stl` | Difference of two STL meshes |
| `mesh_boolean_intersect` | `target_stl`, `tool_stl` | Intersection of two STL meshes |
| `mesh_repair` | `stl_filename` | Fix normals, remove degenerate faces, manifold repair |
| `mesh_simplify` | `stl_filename`, `target_faces` | Quadric edge collapse decimation (pymeshlab or trimesh fallback) |
| `mesh_smooth` | `stl_filename`, `iterations?` (5), `lambda?` (0.5) | Laplacian smoothing |
| `mesh_subdivide` | `stl_filename`, `iterations?` (1) | Loop subdivision |
| `mesh_slice` | `stl_filename`, `plane_height`, `plane_axis?` (x/y/z) | Cross-section slice at plane |
| `mesh_section` | `stl_filename`, `plane_height` | 2D outline → SVG export |
| `mesh_curvature` | `stl_filename` | Principal curvature analysis (pymeshlab) |
| `mesh_convex_hull` | `stl_filename` | Convex hull mesh |
| `mesh_voxelize` | `stl_filename`, `pitch` | Voxelized representation → STL boxes |

### Tier 8: `conversion` — Format Conversion

Bidirectional conversion between CAD and mesh formats.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `convert_step_stl` | `input_filename` | STEP → STL |
| `convert_stl_step` | `input_filename` | STL → STEP |
| `convert_step_obj` | `input_filename` | STEP → Wavefront OBJ |
| `convert_step_glb` | `input_filename` | STEP → GLTF Binary (GLB) |
| `convert_stl_ply` | `input_filename` | STL → Stanford PLY |
| `convert_stl_off` | `input_filename` | STL → Object File Format |
| `convert_stl_3mf` | `input_filename` | STL → 3D Manufacturing Format |
| `convert_stl_collada` | `input_filename` | STL → COLLADA DAE |
| `export_dxf` | `step_filename` | CAD face → 2D DXF |
| `export_svg` | `step_filename` | CAD profile → SVG |

Supported format pairs:

```
STEP ⇄ STL, OBJ, GLB, DXF, SVG
STL → PLY, OFF, 3MF, COLLADA, STEP
```

### Tier 9: `assembly` — Multi-Part Assemblies

Create, populate, constrain, and export assemblies. Assembly state is held in memory.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `new_assembly` | `name` | Create a new empty assembly |
| `add_part` | `assembly_name`, `step_filename`, `loc_x/y/z?`, `rot_x/y/z?`, `part_name?` | Add a STEP file as a part |
| `constrain_mate` | `assembly_name`, `part_a`, `part_b` | Add plane mate constraint |
| `constrain_align` | `assembly_name`, `part_a`, `axis_a`, `part_b`, `axis_b` | Add axis alignment constraint |
| `solve` | `assembly_name` | Solve all constraints |
| `export_step` | `assembly_name` | Multi-body STEP export |
| `export_gltf` | `assembly_name` | GLTF/GLB export |
| `export_vrml` | `assembly_name` | VRML export |

### Tier 10: `cam` — CAM & Manufacturing

Generate G-code for CNC machining and prepare models for 3D printing.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `profile_cam` | `step_filename`, `tool_diameter?` (3.0), `feed_rate?` (1000), `plunge_rate?` | 2D profile G-code |
| `pocket_cam` | `step_filename`, `tool_diameter?` (3.0), `stepover?` | Pocket clearing G-code |
| `drill_cam` | `step_filename`, `hole_diameter?`, `depth?` | Drill cycle G-code |
| `slice_3mf` | `step_filename` | Export as 3MF for 3D printing |
| `slice_svg` | `step_filename`, `height?` (0) | Export 2D slice as SVG |

> **Note:** CAM operations generate simplified G-code based on bounding box geometry. For production CAM, use the output as a reference and refine with a dedicated CAM tool.

### Tier 11: `parts` — Parameterized Part Library

Standard mechanical components with sensible defaults.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `bolt` | `diameter?` (6), `length?` (30), `thread_pitch?` (1.0) | Hex head bolt (head + shank) |
| `nut` | `diameter?` (6), `thickness?` (5) | Hex nut |
| `washer` | `inner_d?` (6.5), `outer_d?` (14), `thickness?` (1.5) | Flat washer |
| `bearing` | `inner_d?` (10), `outer_d?` (26), `width?` (8) | Ball bearing (simplified) |
| `i_beam` | `height?` (100), `flange_width?` (50), `web_thickness?` (5), `flange_thickness?` (8), `length?` (1000) | I-beam profile |
| `c_channel` | `height?` (80), `width?` (40), `thickness?` (5), `length?` (1000) | C-channel profile |
| `angle_iron` | `leg_length?` (50), `thickness?` (5), `length?` (1000) | Angle iron (L-profile) |
| `spring` | `wire_d?` (2), `coil_d?` (20), `num_coils?` (8), `height?` (50) | Helical compression spring (spline sweep) |

### Tier 12: `fem` — FEM & Simulation Prep

Generate finite element meshes from CAD models and export to solver formats.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `mesh_2d_tri` | `step_filename`, `element_size?` (5.0) | 2D triangular surface mesh |
| `mesh_2d_quad` | `step_filename`, `element_size?` (5.0) | 2D quad-dominant surface mesh |
| `mesh_3d_tet` | `step_filename`, `element_size?` (5.0) | 3D tetrahedral volume mesh |
| `mesh_3d_hex` | `step_filename`, `element_size?` (5.0) | 3D hexahedral volume mesh |
| `export_abaqus` | `step_filename`, `element_size?`, `mesh_file?` | Export to Abaqus INP format |
| `export_ansys` | `step_filename`, `element_size?`, `mesh_file?` | Export to Ansys CDB format |
| `export_nastran` | `step_filename`, `element_size?`, `mesh_file?` | Export to Nastran BDF format |
| `export_vtk` | `step_filename`, `element_size?`, `mesh_file?` | Export to VTK/VTU format |
| `export_xdmf` | `step_filename`, `element_size?`, `mesh_file?` | Export to XDMF format |

Uses [gmsh](https://gmsh.info) for meshing and [meshio](https://github.com/nschloe/meshio) for format conversion.

### Tier 13: `templates` — Real-World Template Generators ⭐

**New in this version!** Pre-built, parameterized generators for common real-world parts. These are full, production-ready templates with sensible defaults — not just primitives.

| Operation | Parameters | Description |
|-----------|-----------|-------------|
| `fan_shroud` | `fan_size?` (60.5), `opening?` (fan_size), `wall?` (3.0), `depth?` (28.0), `screw_spacing?` (50.0), `screw_diameter?` (3.2), `boss_diameter?` (7.0), `fillet?` (1.5) | Fan holder/shroud with square opening, 4× screw bosses with holes, optional fillet. Output: STEP/STL |
| `duct_transition` | `inlet_width?` (60.5), `inlet_height?` (60.5), `outlet_width?` (49.1), `outlet_height?` (44.8), `length?` (35.0), `wall?` (2.4), `fillet?` (0.8) | Hollow rectangular-to-rectangular transition duct via loft |
| `rounded_rect_frame` | `width?` (70.0), `height?` (70.0), `thickness?` (5.0), `opening_width?` (60.5), `opening_height?` (60.5), `fillet?` (2.0) | Rounded rectangular frame/mount with center cutout |
| `screw_mount_plate` | `width?` (70.0), `height?` (70.0), `thickness?` (3.0), `screw_spacing_x?` (50.0), `screw_spacing_y?` (50.0), `screw_diameter?` (3.2), `fillet?` (1.0) | Flat mounting plate with 4× rectangular screw pattern |
| `gasket` | `width?` (70.0), `height?` (70.0), `thickness?` (1.2), `opening_width?` (60.5), `opening_height?` (60.5), `screw_spacing?` (50.0), `screw_diameter?` (3.2) | Thin gasket/spacer frame with optional screw holes |
| `standoff_grid` | `width?` (70.0), `height?` (70.0), `base_thickness?` (3.0), `standoff_height?` (8.0), `standoff_diameter?` (7.0), `hole_diameter?` (3.2), `spacing_x?` (50.0), `spacing_y?` (50.0) | Base plate with 4× cylindrical standoff/boss grid with screw holes |

**Example: GPU Fan Shroud**
```python
cad_run("templates", "fan_shroud", {
    "fan_size": 60.5,
    "opening": 55.0,
    "depth": 28.0,
    "screw_spacing": 50.0,
    "screw_diameter": 3.2,
    "fillet": 2.0,
    "name": "gpu_fan_shroud"
})
```

**Example: Airflow Duct Transition**
```python
cad_run("templates", "duct_transition", {
    "inlet_width": 60.5,
    "inlet_height": 60.5,
    "outlet_width": 49.1,
    "outlet_height": 44.8,
    "length": 35.0,
    "wall": 2.4,
    "name": "fan_duct_transition"
})
```

---

## Full Tier Summary

| # | Tier | Operations | Best For |
|---|------|-----------|----------|
| 1 | `primitive` | 7 | Boxes, cylinders, spheres, cones, torus shapes |
| 2 | `sketch_2d` | 8 | 2D profiles, extruded logos, gears, slots |
| 3 | `boolean_3d` | 11 | Cutting, fusing, filleting, mirroring, shelling |
| 4 | `stl` | 5 | Importing scanned meshes, transforming, merging |
| 5 | `sketch_draw` | 16 | Custom 2D wire profiles (lines, arcs, splines) → 3D |
| 6 | `analysis` | 8 | Volume, area, COM, bounding box, watertight check |
| 7 | `mesh` | 12 | Repair, simplify, smooth, slice, boolean on meshes |
| 8 | `conversion` | 10 | STEP↔STL↔OBJ↔GLB↔PLY↔3MF↔DXF↔SVG |
| 9 | `assembly` | 8 | Multi-part assemblies, constraints, GLTF export |
| 10 | `cam` | 5 | G-code generation, 3MF for printing, slice SVG |
| 11 | `parts` | 8 | Bolts, nuts, washers, bearings, beams, springs |
| 12 | `fem` | 9 | Tetra/hex meshing, Abaqus/Ansys/Nastran export |
| 13 | **`templates`** | **6** | **Fan shrouds, ducts, frames, plates, gaskets, standoffs** |

**Total: 81 operations** across 13 tiers.

---

## Workflow Examples

### Complete Part Creation → Analysis → Export Pipeline

```
# 1. Explore available tiers
cad_help()

# 2. See what's in the "templates" tier
cad_help("templates")

# 3. Generate a fan shroud
cad_run("templates", "fan_shroud", {
    "fan_size": 60.5,
    "opening": 55.0,
    "depth": 28.0,
    "screw_spacing": 50.0,
    "name": "my_shroud"
})

# 4. Check the output
cad_manage("list")

# 5. Analyze mass properties
cad_run("analysis", "mass_properties",
    {"step_filename": "my_shroud.step"})

# 6. Export as SVG
cad_run("conversion", "export_svg",
    {"step_filename": "my_shroud.step", "name": "my_shroud_svg"})

# 7. Generate G-code
cad_run("cam", "profile_cam", {
    "step_filename": "my_shroud.step",
    "tool_diameter": 3.0,
    "name": "my_shroud_gcode"
})
```

### STL Scan → Repair → Simplify → FEM

```
# 1. Import a 3D scan
cad_run("stl", "import_stl", {"stl_filename": "scan_raw.stl"})

# 2. Repair normals
cad_run("stl", "stl_fix_normals", {"stl_filename": "scan_raw.stl"})

# 3. Full repair + simplify
cad_run("mesh", "mesh_repair", {"stl_filename": "scan_raw.stl"})
cad_run("mesh", "mesh_simplify", {"stl_filename": "scan_raw.stl", "target_faces": 5000})

# 4. Convert to STEP for CAD
cad_run("conversion", "convert_stl_step", {"input_filename": "scan_raw_simplified.stl"})

# 5. FEM mesh
cad_run("fem", "mesh_3d_tet", {"step_filename": "scan_raw_simplified.step", "element_size": 2.0})

# 6. Export for Ansys
cad_run("fem", "export_ansys", {"step_filename": "scan_raw_simplified.step", "element_size": 2.0})
```

### Multi-Part Assembly Workflow

```
# 1. Create primitives
cad_run("primitive", "box", {"width": 100, "depth": 50, "height": 20, "name": "base_plate"})
cad_run("primitive", "cylinder", {"radius": 10, "height": 50, "name": "support_pillar"})

# 2. New assembly
cad_run("assembly", "new_assembly", {"name": "my_assembly"})

# 3. Add parts
cad_run("assembly", "add_part", {
    "name": "my_assembly",
    "step_filename": "base_plate.step",
    "loc_z": 0,
    "part_name": "base"
})
cad_run("assembly", "add_part", {
    "name": "my_assembly",
    "step_filename": "support_pillar.step",
    "loc_x": 30, "loc_y": 20, "loc_z": 10,
    "part_name": "pillar"
})

# 4. Export assembly
cad_run("assembly", "export_step", {"name": "my_assembly"})
cad_run("assembly", "export_gltf", {"name": "my_assembly"})
```

### Part Library + Analysis

```
# Generate hardware
cad_run("parts", "bolt", {"diameter": 8, "length": 40, "name": "m8_bolt"})
cad_run("parts", "nut", {"diameter": 8, "thickness": 6, "name": "m8_nut"})
cad_run("parts", "washer", {"inner_d": 8.5, "outer_d": 16, "name": "m8_washer"})

# Query mass properties
cad_run("analysis", "mass_properties", {"step_filename": "m8_bolt.step"})
```

---

## Output Directory & Format Support

Exports are written to [`./cad_output/`](./cad_output) (mounted at `/app/cad_output` inside the container).

### Supported Export Formats

| Format | Extension | Tier(s) | Notes |
|--------|-----------|---------|-------|
| STEP | `.step` | All | Primary CAD exchange format (AP203/214) |
| STL | `.stl` | All | Mesh format for 3D printing |
| OBJ | `.obj` | `conversion` | Wavefront mesh format |
| PLY | `.ply` | `conversion`, `mesh` | Stanford Polygon format |
| GLB | `.glb` | `conversion`, `assembly` | Binary glTF for web/3D viewers |
| OFF | `.off` | `conversion` | Object File Format |
| 3MF | `.3mf` | `conversion`, `cam` | 3D Manufacturing Format |
| COLLADA | `.dae` | `conversion` | Interoperability format |
| SVG | `.svg` | `conversion`, `cam`, `mesh` | 2D vector export |
| DXF | `.dxf` | `conversion` | 2D CAD exchange |
| G-code | `.gcode` | `cam` | CNC machining |
| GMSH | `.msh` | `fem` | Gmsh mesh format |
| Abaqus | `.inp` | `fem` | Abaqus/FEA input |
| Ansys | `.cdb` | `fem` | Ansys solver format |
| Nastran | `.bdf` | `fem` | Nastran bulk data |
| VTK/VTU | `.vtu` | `fem` | Visualization Toolkit |
| XDMF | `.xdmf` | `fem` | HDF5-based mesh format |
| VRML | `.wrl` | `assembly` | VRML export |
| GLTF | `.gltf` | `assembly` | JSON glTF export |

### Example Outputs

The [`cad_output/`](./cad_output) directory contains generated examples:

- [`TeslaP100_adapter.stl`](cad_output/TeslaP100_adapter.stl) & [`.dwg`](cad_output/TeslaP100_adapter.dwg) — GPU adapter bracket
- [`p100_side_60mm_fan_shroud_v1.step`](cad_output/p100_side_60mm_fan_shroud_v1.step) — Fan shroud from templates tier
- [`p100_side_transition_probe.step`](cad_output/p100_side_transition_probe.step) — Duct transition probe
- [`alqc_locus_core_seed.step`](cad_output/alqc_locus_core_seed.step) — ALQC locus geometry
- [`alqc_shadow_locus_ring.step`](cad_output/alqc_shadow_locus_ring.step) — ALQC ring geometry

---

## Health Check

```
curl http://localhost:8012/health
# → {"status":"ok"}
```

The health endpoint is served by `supergateway` and confirms the MCP server process is alive.

---

## Docker Reference

### [`Dockerfile`](Dockerfile)

- Base: `python:3.11-slim`
- System deps: OpenCASCADE, libGL, libspatialindex, build tools
- Python packages: cadquery, mcp, trimesh, manifold3d, pymeshlab, meshio, gmsh, ezdxf, pygltflib, ifcopenshell, scikit-image, and more
- Runtime: `supergateway` wrapping `python cadquery_mcp.py` via `--stdio`

### [`docker-compose.yml`](docker-compose.yml)

```yaml
services:
  cadquery-mcp:
    build: .
    ports:
      - "8012:8012"
    environment:
      CAD_OUTPUT_DIR: "/app/cad_output"
    volumes:
      - ./cad_output:/app/cad_output
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8012/health"]
```

---

## Remote Deployment

### Using rsync + docker compose

```bash
# Push files to remote VPS
rsync -avz --progress ./ user@your-server:~/cadquery-mcp/

# SSH in and deploy
ssh user@your-server
cd ~/cadquery-mcp
docker compose up -d --build

# Verify
curl http://localhost:8012/health
```

### Using the deploy script

A deploy workflow might use the same pattern — sync files, rebuild container, verify health.

---

## STL Metadata (Binary Scanning)

The `cad_stl_info` operation (`cad_manage("stl_info", "file.stl")`) parses **binary STL headers** directly — reading the 80-byte ASCII header comment, 4-byte triangle count, and scanning vertex data for bounding box computation. This works without loading the full mesh into memory, supporting files up to gigabytes in size.

For large files, the bounding box is sampled from the first 5,000 triangles, providing a fast (sub-millisecond) estimate of extents.

---

## Extending with New Tiers

Adding a new capability tier is straightforward:

1. **Add a `TIERS` entry** with label, description, and operation names:

```python
TIERS["pcb"] = {
    "label": "PCB Design",
    "description": "Generate PCB outlines, mounting holes, keepout zones",
    "operations": {
        "outline": "Board outline from dimensions",
        "mounting_holes": "Add mounting holes at positions",
        "keepout": "Add keepout zone",
    },
}
TIER_ORDER.insert(-1, "pcb")  # before templates
```

2. **Add handlers in `cad_run()`:**

```python
if tier == "pcb":
    if op == "outline":
        w = _extract_float(params, "width")
        h = _extract_float(params, "height")
        return _export(cq.Workplane("XY").rect(w, h).extrude(1.6), name, export_format)
```

3. **Rebuild** — the model discovers the new tier automatically via `cad_help()`.

No changes to the model's tool configuration are needed.

---

## Project Files

| File | Purpose |
|------|---------|
| [`cadquery_mcp.py`](cadquery_mcp.py) | MCP server — tiered router with 81 operations across 13 tiers |
| [`Dockerfile`](Dockerfile) | Container build (python:3.11-slim + apt + pip + supergateway) |
| [`docker-compose.yml`](docker-compose.yml) | Orchestration with bind mount + healthcheck |
| [`environment.yml`](environment.yml) | Reference conda environment (stub — pip deps in Dockerfile) |
| [`README.md`](README.md) | This file |
| `cad_output/` | Generated STEP, STL, OBJ, GLB, SVG, DXF exports |

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| `curl: connection refused` | Container not running | `docker compose up -d` first |
| `File not found in output directory` | Wrong filename or path | Use `cad_manage("list")` to see available files; pass only the basename |
| `cad_help("unknown")` → "Unknown tier" | Typo in tier name | `cad_help()` to see valid tier names |
| `gmsh not available` | gmsh not installed on host | Use Docker (gmsh pre-installed) or `pip install gmsh` |
| `pymeshlab not available` | pymeshlab not installed | `pip install pymeshlab` or use Docker |
| STL import fails | Non-manifold or corrupt mesh | Try `mesh_repair` first |
| `export_glb` returns `.gltf` | cadquery exports GLTF text format | Copy renamed — some viewers accept `.glb` |
| Supergateway port conflict | Port 8012 already in use | Change `ports:` in docker-compose.yml |

### FAQ

**Q: Why 3 tools instead of 80+?**  
A: LLMs have limited tool budgets. Exposing 80+ tools would consume the entire context window on tool definitions. The tiered router pattern keeps the model's tool namespace at 3 while providing discoverability via `cad_help()`.

**Q: Can I run this without Docker?**  
A: Yes. Install the dependencies listed under "Manual pip" and run via `supergateway`. See [Installation Option 2](#option-2-manual-pip-ubuntudebian).

**Q: What CAD formats can I import?**  
A: STEP (primary), STL. The STL → STEP conversion enables mesh-based workflows.

**Q: How do I change the output directory?**  
A: Set the `CAD_OUTPUT_DIR` environment variable (default: `/app/cad_output`).

**Q: Does the server persist state between calls?**  
A: Files persist in the output directory. Sketch and assembly state persists in memory for the lifetime of the server process.

**Q: Can I add custom operations without modifying the core file?**  
A: Currently, tiers are defined in [`cadquery_mcp.py`](cadquery_mcp.py). The code is designed for easy extension — add a tier entry + handler block.

---

## License

This project is provided as an open-source MCP server implementation. CadQuery is licensed under Apache 2.0. See individual package licenses for third-party dependencies.

---

*Built with [CadQuery](https://cadquery.readthedocs.io), [trimesh](https://trimsh.org), [gmsh](https://gmsh.info), [meshio](https://github.com/nschloe/meshio), [pymeshlab](https://pymeshlab.readthedocs.io), [supergateway](https://github.com/supercorp/supergateway), and the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).*
