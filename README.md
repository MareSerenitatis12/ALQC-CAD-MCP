# CadQuery MCP Docker Server — AI CAD Suite (Tiered Router)

Streamable HTTP MCP endpoint:

```text
http://localhost:8012/mcp
```

Health endpoint:

```text
http://localhost:8012/health
```

## Quick Start

```bash
# Build and start
docker compose up -d --build

# Check health
curl http://localhost:8012/health
```

## Architecture: Tiered Router

The model's tool namespace stays **lean** — only **3 router tools** are exposed to the model,
hiding **80+ operations** organized across **12 capability tiers**. The model calls
`cad_help()` to discover capabilities, `cad_run()` to execute, and `cad_manage()` for
file management.

```
┌─ Model's Tool Namespace ──────────────────────────┐
│                                                     │
│  cad_help(tier?)      → discover tiers + operations │
│  cad_run(tier, op, params) → execute operation     │
│  cad_manage(action, filename?) → file management    │
│                                                     │
│  (3 tools only — NOT 80 flat tools)                │
└─────────────────────────────────────────────────────┘
         │
         ▼  (internal dispatch via cad_run)
┌─────────────────────────────────────────────────────┐
│  12 capability tiers — all 80+ operations live      │
│                                                      │
│  primitive    sketch_2d    boolean_3d    stl         │
│  sketch_draw  analysis     mesh          conversion  │
│  assembly     cam          parts          fem        │
└─────────────────────────────────────────────────────┘
```

## Tool Reference

### `cad_help(tier?)` — Discover capabilities

| Call | Returns |
|------|---------|
| `cad_help()` | Overview of all 12 tiers with descriptions |
| `cad_help("primitive")` | Operations + parameters in the primitives tier |
| `cad_help("cam")` | CAM operations (profile_cam, pocket_cam, drill_cam, etc.) |

### `cad_run(tier, operation, params)` — Execute any CAD operation

| Example | What it does |
|---------|-------------|
| `cad_run("primitive", "box", {"width":50, "depth":30, "height":20})` | Create a 50×30×20 mm box → box.step |
| `cad_run("stl", "import_stl", {"stl_filename":"model.stl"})` | STL → CAD solid → model.step |
| `cad_run("boolean_3d", "cut", {"target_step":"a.step", "tool_step":"b.step"})` | Boolean subtract → result.step |
| `cad_run("mesh", "mesh_smooth", {"stl_filename":"rough.stl", "iterations":5})` | Laplacian smoothing → smooth.stl |
| `cad_run("fem", "mesh_3d_tet", {"step_filename":"part.step", "element_size":3})` | Tetrahedral FEM mesh → part.msh |
| `cad_run("parts", "bolt", {"diameter":6, "length":30})` | Parametric hex bolt → bolt.step |
| `cad_run("cam", "profile_cam", {"step_filename":"part.step", "tool_diameter":3})` | Profile G-code → part.gcode |

### `cad_manage(action, filename?)` — File management

| Call | What it does |
|------|-------------|
| `cad_manage("list")` | List all exported files |
| `cad_manage("delete", "bad_part.step")` | Delete a file |
| `cad_manage("stl_info", "model.stl")` | Get STL metadata (triangles, bounding box, size) |

## All 12 Capability Tiers (Fully Implemented)

| # | Tier | Label | Operations |
|---|------|-------|------------|
| 1 | `primitive` | Primitives | box, cylinder, tube, sphere, wedge, torus, cone |
| 2 | `sketch_2d` | 2D Sketches & Profiles | rect, circle, polygon, slot, ellipse, trapezoid, gear, text |
| 3 | `boolean_3d` | Boolean & 3D Ops | cut, union, intersect, fillet, chamfer, shell, split, mirror, extrude_face, revolve, thicken_face |
| 4 | `stl` | STL Import & Transform | import_stl, transform_stl, stl_info, stl_fix_normals, stl_merge |
| 5 | `sketch_draw` | Procedural Drawing | start_sketch, line, line_to, h_line, v_line, arc_three, arc_tangent, spline, polyline, close, mirror_sketch, offset_2d, extrude, revolve_sketch, loft, sweep |
| 6 | `analysis` | Analysis & Query | mass_properties, bounding_box, surface_area, section_props, is_watertight, mesh_volume, ray_intersect, signed_distance |
| 7 | `mesh` | Mesh Processing | mesh_boolean_union, mesh_boolean_diff, mesh_boolean_intersect, mesh_repair, mesh_simplify, mesh_smooth, mesh_subdivide, mesh_slice, mesh_section, mesh_curvature, mesh_convex_hull, mesh_voxelize |
| 8 | `conversion` | Format Conversion | convert_step_stl, convert_stl_step, convert_step_obj, convert_step_glb, convert_stl_ply, convert_stl_off, convert_stl_3mf, convert_stl_collada, export_dxf, export_svg |
| 9 | `assembly` | Assembly | new_assembly, add_part, constrain_mate, constrain_align, solve, export_step, export_gltf, export_vrml |
| 10 | `cam` | CAM & Manufacturing | profile_cam, pocket_cam, drill_cam, slice_3mf, slice_svg |
| 11 | `parts` | Part Library | bolt, nut, washer, bearing, i_beam, c_channel, angle_iron, spring |
| 12 | `fem` | FEM & Simulation Prep | mesh_2d_tri, mesh_2d_quad, mesh_3d_tet, mesh_3d_hex, export_abaqus, export_ansys, export_nastran, export_vtk, export_xdmf |

## Workflow Example

```
1. cad_help()                                       → see all 12 tiers
2. cad_help("primitive")                            → see box params
3. cad_run("primitive", "box", {width:50, depth:30, height:20}) → box.step
4. cad_manage("list")                                → confirm box.step
5. cad_run("analysis", "mass_properties", {step_filename:"box.step"}) → volume, area, COM
6. cad_run("conversion", "export_svg", {step_filename:"box.step"})   → box.svg
```

## Output Directory

Exports are written to `./cad_output/` (mounted at `/app/cad_output` inside the container).

Supported export formats: `.step`, `.stl`, `.obj`, `.ply`, `.glb`, `.off`, `.3mf`, `.dae`,
`.svg`, `.dxf`, `.gcode`, `.msh`, `.inp`, `.cdb`, `.bdf`, `.vtu`, `.xdmf`

## Project Files

| File | Purpose |
|------|---------|
| [`cadquery_mcp.py`](cadquery_mcp.py) | MCP server — tiered router with 80+ operations across 12 tiers |
| [`Dockerfile`](Dockerfile) | Container build (python:3.11-slim + pip) |
| [`docker-compose.yml`](docker-compose.yml) | Orchestration with bind mount + healthcheck |
| [`environment.yml`](environment.yml) | Minimal conda env (python, nodejs, curl, pip) |
| [`deploy.sh`](deploy.sh) | SCP + deploy script for updating remote VPS |
| [`CADQUERY_AI_CAPABILITIES_RESEARCH.md`](CADQUERY_AI_CAPABILITIES_RESEARCH.md) | Full research: 140+ ops, 7+ libraries, 30+ formats |
| [`README.md`](README.md) | This file |
| `cad_output/` | Generated STEP/STL/OBJ/GLB exports |

## Deploying to Remote Machine

```bash
# 1. Push files to remote VPS
rsync -avz --progress ./ avhea@10.10.1.11:~/cadquery-mcp/

# 2. SSH in and rebuild
ssh avhea@10.10.1.11
cd ~/cadquery-mcp
docker compose up -d --build

# 3. Verify
curl http://localhost:8012/health
```

---

*See [`CADQUERY_AI_CAPABILITIES_RESEARCH.md`](CADQUERY_AI_CAPABILITIES_RESEARCH.md) for the complete research backing this system.*
