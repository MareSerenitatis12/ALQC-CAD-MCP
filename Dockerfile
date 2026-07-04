FROM python:3.11-slim

WORKDIR /app

# System dependencies for CadQuery/OCC/OpenGL, healthcheck curl, and supergateway/npm.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    git \
    build-essential \
    pkg-config \
    cmake \
    libgl1 \
    libgl1-mesa-dri \
    libglu1-mesa \
    libxrender1 \
    libxext6 \
    libxt6 \
    libxi6 \
    libsm6 \
    libglib2.0-0 \
    libgomp1 \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g supergateway

# Quote version specifiers so the shell does not treat >= as output redirection.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
      'cadquery>=2.5' \
      'mcp>=1.0' \
      'trimesh[easy]>=4.0' \
      manifold3d \
      pymeshlab \
      numpy-stl \
      numpy \
      scipy \
      networkx \
      shapely \
      rtree \
      sympy \
      meshio \
      gmsh \
      ezdxf \
      svg.path \
      svgpathtools \
      lxml \
      pillow \
      pycollada \
      pygltflib \
      ifcopenshell \
      scikit-image

COPY cadquery_mcp.py /app/cadquery_mcp.py

RUN mkdir -p /app/cad_output

EXPOSE 8012

CMD ["supergateway", "--stdio", "python /app/cadquery_mcp.py", "--outputTransport", "streamableHttp", "--streamableHttpPath", "/mcp", "--port", "8012", "--host", "0.0.0.0", "--cors", "--healthEndpoint", "/health"]
