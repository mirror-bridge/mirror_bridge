#!/bin/bash
# Mirror Bridge - Comprehensive Benchmark Suite
# Compares compile-time and runtime performance against pybind11 and Boost.Python

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCHMARK_DIR="$PROJECT_ROOT/benchmarks"
BUILD_DIR="$PROJECT_ROOT/build"

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}  Mirror Bridge - Benchmark Suite${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""

# Check for required tools
if ! command -v clang++ &> /dev/null; then
    echo -e "${RED}Error: clang++ not found${NC}"
    echo "Run this script inside the Docker container"
    exit 1
fi

# Create build directory
mkdir -p "$BUILD_DIR"

# Function to measure compile time
measure_compile_time() {
    local binding_file=$1
    local output_file=$2
    local include_flags=$3

    # Clear cache
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

    # Measure compilation time (5 runs for better statistical significance)
    local times=()
    for i in {1..5}; do
        rm -f "$output_file"
        start=$(date +%s%3N)
        clang++ -std=c++2c -freflection -freflection-latest -stdlib=libc++ \
            -O3 -DNDEBUG \
            $include_flags -fPIC -shared \
            $(python3-config --includes --ldflags) \
            "$binding_file" -o "$output_file" 2>&1 | grep -v "mixture of designated" > /dev/null || true
        end=$(date +%s%3N)
        times+=($((end - start)))
    done

    # Calculate median and stddev
    IFS=$'\n' sorted=($(sort -n <<<"${times[*]}"))
    local median="${sorted[2]}"

    # Calculate mean for stddev
    local sum=0
    for t in "${times[@]}"; do
        sum=$((sum + t))
    done
    local mean=$((sum / 5))

    # Calculate standard deviation
    local sq_sum=0
    for t in "${times[@]}"; do
        local diff=$((t - mean))
        sq_sum=$((sq_sum + diff * diff))
    done
    local variance=$((sq_sum / 5))
    local stddev=$(awk "BEGIN {printf \"%.0f\", sqrt($variance)}")

    # Return "median±stddev"
    echo "${median} ${stddev}"
}

# Function to measure pybind11 compile time (uses same optimization flags)
measure_compile_time_pybind11() {
    local binding_file=$1
    local output_file=$2
    local include_flags=$3

    # Clear cache
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

    # Measure compilation time (5 runs for better statistical significance)
    local times=()
    for i in {1..5}; do
        rm -f "$output_file"
        start=$(date +%s%3N)
        clang++ -std=c++20 -stdlib=libc++ \
            -O3 -DNDEBUG \
            $include_flags -fPIC -shared \
            $(python3-config --includes --ldflags) \
            "$binding_file" -o "$output_file" 2>&1 | grep -v "mixture of designated" > /dev/null || true
        end=$(date +%s%3N)
        times+=($((end - start)))
    done

    # Calculate median and stddev
    IFS=$'\n' sorted=($(sort -n <<<"${times[*]}"))
    local median="${sorted[2]}"

    # Calculate mean for stddev
    local sum=0
    for t in "${times[@]}"; do
        sum=$((sum + t))
    done
    local mean=$((sum / 5))

    # Calculate standard deviation
    local sq_sum=0
    for t in "${times[@]}"; do
        local diff=$((t - mean))
        sq_sum=$((sq_sum + diff * diff))
    done
    local variance=$((sq_sum / 5))
    local stddev=$(awk "BEGIN {printf \"%.0f\", sqrt($variance)}")

    # Return "median±stddev"
    echo "${median} ${stddev}"
}

# Function to measure nanobind compile time (uses same optimization flags as pybind11)
# Note: Pre-compiles stub library once for fair comparison
measure_compile_time_nanobind() {
    local binding_file=$1
    local output_file=$2
    local include_flags=$3

    # Pre-compile nanobind stub library once (this is what would happen in real projects)
    local nb_src="/usr/local/nanobind/src"
    local nb_stub="$BUILD_DIR/nb_stub.o"

    if [ ! -f "$nb_stub" ]; then
        clang++ -std=c++17 -stdlib=libc++ \
            -O3 -DNDEBUG \
            -I/usr/local/nanobind/include \
            -I/usr/local/nanobind/ext/robin_map/include \
            $(python3-config --includes) \
            -fPIC -c \
            "$nb_src/nb_combined.cpp" -o "$nb_stub" 2>&1 | grep -v "mixture of designated" > /dev/null || true
    fi

    # Clear cache
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

    # Measure compilation time (5 runs for better statistical significance)
    # Now we only compile the binding file and link against pre-compiled stub
    local times=()
    for i in {1..5}; do
        rm -f "$output_file"
        start=$(date +%s%3N)
        clang++ -std=c++17 -stdlib=libc++ \
            -O3 -DNDEBUG \
            -I/usr/local/nanobind/include \
            -I/usr/local/nanobind/ext/robin_map/include \
            $include_flags -fPIC -shared \
            $(python3-config --includes --ldflags) \
            "$binding_file" \
            "$nb_stub" \
            -o "$output_file" 2>&1 | grep -v "mixture of designated" > /dev/null || true
        end=$(date +%s%3N)
        times+=($((end - start)))
    done

    # Calculate median and stddev
    IFS=$'\n' sorted=($(sort -n <<<"${times[*]}"))
    local median="${sorted[2]}"

    # Calculate mean for stddev
    local sum=0
    for t in "${times[@]}"; do
        sum=$((sum + t))
    done
    local mean=$((sum / 5))

    # Calculate standard deviation
    local sq_sum=0
    for t in "${times[@]}"; do
        local diff=$((t - mean))
        sq_sum=$((sq_sum + diff * diff))
    done
    local variance=$((sq_sum / 5))
    local stddev=$(awk "BEGIN {printf \"%.0f\", sqrt($variance)}")

    # Return "median±stddev"
    echo "${median} ${stddev}"
}

# Function to measure SWIG compile time
measure_compile_time_swig() {
    local binding_file=$1
    local output_file=$2
    local include_flags=$3

    # Clear cache
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

    # Measure compilation time (5 runs for better statistical significance)
    local times=()
    for i in {1..5}; do
        rm -f "$output_file" "${binding_file%.i}_wrap.cxx"
        start=$(date +%s%3N)
        # SWIG generates wrapper code, then compile it
        swig -c++ -python -o "${binding_file%.i}_wrap.cxx" "$binding_file" 2>/dev/null &&
        clang++ -std=c++20 -stdlib=libc++ \
            -O3 -DNDEBUG \
            $include_flags -fPIC -shared \
            $(python3-config --includes --ldflags) \
            "${binding_file%.i}_wrap.cxx" -o "$output_file" 2>&1 | grep -v "mixture of designated" > /dev/null || true
        end=$(date +%s%3N)
        times+=($((end - start)))
    done

    # Calculate median and stddev
    IFS=$'\n' sorted=($(sort -n <<<"${times[*]}"))
    local median="${sorted[2]}"

    # Calculate mean for stddev
    local sum=0
    for t in "${times[@]}"; do
        sum=$((sum + t))
    done
    local mean=$((sum / 5))

    # Calculate standard deviation
    local sq_sum=0
    for t in "${times[@]}"; do
        local diff=$((t - mean))
        sq_sum=$((sq_sum + diff * diff))
    done
    local variance=$((sq_sum / 5))
    local stddev=$(awk "BEGIN {printf \"%.0f\", sqrt($variance)}")

    # Return "median±stddev"
    echo "${median} ${stddev}"
}

# Function to get file size in KB
get_size_kb() {
    if [ -f "$1" ]; then
        # Try macOS stat first, then Linux stat
        size=$(stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo "0")
        echo $((size / 1024))
    else
        echo "0"
    fi
}

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  PART 1: Compile-Time Benchmarks${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

# Simple benchmark
echo -e "${BLUE}Simple Project (1 class, ~10 methods)${NC}"
echo ""

cd "$BENCHMARK_DIR/compile_time/simple"

echo -n "  Mirror Bridge (manual)...       "
rm -f "$BUILD_DIR/simple_mb_manual.so"
result_mb_manual=($(measure_compile_time "mirror_bridge_binding.cpp" "$BUILD_DIR/simple_mb_manual.so" "-I$PROJECT_ROOT"))
time_mb_manual=${result_mb_manual[0]}
stddev_mb_manual=${result_mb_manual[1]}
size_mb_manual=$(get_size_kb "$BUILD_DIR/simple_mb_manual.so")
echo -e "${GREEN}${time_mb_manual}ms ±${stddev_mb_manual}ms  (${size_mb_manual} KB)${NC}"

echo -n "  Mirror Bridge (auto-discovery)..."
rm -f "$BUILD_DIR/simple_mb_auto.so"
start=$(date +%s%3N)
cd "$PROJECT_ROOT" && ./mirror_bridge_auto "$BENCHMARK_DIR/compile_time/simple" --module simple_mb_auto > /dev/null 2>&1
end=$(date +%s%3N)
time_mb_auto=$((end - start))
size_mb_auto=$(get_size_kb "$BUILD_DIR/simple_mb_auto.so")
cd "$BENCHMARK_DIR/compile_time/simple"
echo -e "${GREEN}${time_mb_auto}ms  (${size_mb_auto} KB)${NC}"

echo -n "  pybind11 (manual)...            "
rm -f "$BUILD_DIR/simple_pb.so"
result_pb=($(measure_compile_time_pybind11 "pybind11_binding.cpp" "$BUILD_DIR/simple_pb.so" "-I/usr/include/python3.10"))
time_pb=${result_pb[0]}
stddev_pb=${result_pb[1]}
size_pb=$(get_size_kb "$BUILD_DIR/simple_pb.so")
echo -e "${GREEN}${time_pb}ms ±${stddev_pb}ms  (${size_pb} KB)${NC}"

echo -n "  nanobind (manual)...            "
rm -f "$BUILD_DIR/simple_nb.so"
result_nb=($(measure_compile_time_nanobind "nanobind_binding.cpp" "$BUILD_DIR/simple_nb.so" "-I/usr/local/include"))
time_nb=${result_nb[0]}
stddev_nb=${result_nb[1]}
size_nb=$(get_size_kb "$BUILD_DIR/simple_nb.so")
echo -e "${GREEN}${time_nb}ms ±${stddev_nb}ms  (${size_nb} KB)${NC}"

echo -n "  SWIG (manual)...                "
rm -f "$BUILD_DIR/_simple_swig.so"
result_swig=($(measure_compile_time_swig "swig_binding.i" "$BUILD_DIR/_simple_swig.so" "-I."))
time_swig=${result_swig[0]}
stddev_swig=${result_swig[1]}
size_swig=$(get_size_kb "$BUILD_DIR/_simple_swig.so")
echo -e "${GREEN}${time_swig}ms ±${stddev_swig}ms  (${size_swig} KB)${NC}"

echo ""
ratio_manual_pb=$(awk "BEGIN {printf \"%.2f\", $time_pb/$time_mb_manual}")
ratio_auto_pb=$(awk "BEGIN {printf \"%.2f\", $time_pb/$time_mb_auto}")
ratio_manual_nb=$(awk "BEGIN {printf \"%.2f\", $time_nb/$time_mb_manual}")
ratio_auto_nb=$(awk "BEGIN {printf \"%.2f\", $time_nb/$time_mb_auto}")
ratio_manual_swig=$(awk "BEGIN {printf \"%.2f\", $time_swig/$time_mb_manual}")
ratio_auto_swig=$(awk "BEGIN {printf \"%.2f\", $time_swig/$time_mb_auto}")
echo -e "  Speedup vs pybind11:"
echo -e "    Manual binding:       ${ratio_manual_pb}x faster"
echo -e "    Auto-discovery:       ${ratio_auto_pb}x faster"
echo -e "  Speedup vs nanobind:"
echo -e "    Manual binding:       ${ratio_manual_nb}x faster"
echo -e "    Auto-discovery:       ${ratio_auto_nb}x faster"
echo -e "  Speedup vs SWIG:"
echo -e "    Manual binding:       ${ratio_manual_swig}x faster"
echo -e "    Auto-discovery:       ${ratio_auto_swig}x faster"
echo ""

# Medium benchmark
echo -e "${BLUE}Medium Project (10 classes, ~50 methods)${NC}"
echo ""

cd "$BENCHMARK_DIR/compile_time/medium"

echo -n "  Mirror Bridge (manual)...       "
rm -f "$BUILD_DIR/medium_mb_manual.so"
result_mb_med_manual=($(measure_compile_time "mirror_bridge_binding.cpp" "$BUILD_DIR/medium_mb_manual.so" "-I$PROJECT_ROOT"))
time_mb_med_manual=${result_mb_med_manual[0]}
stddev_mb_med_manual=${result_mb_med_manual[1]}
size_mb_med_manual=$(get_size_kb "$BUILD_DIR/medium_mb_manual.so")
echo -e "${GREEN}${time_mb_med_manual}ms ±${stddev_mb_med_manual}ms  (${size_mb_med_manual} KB)${NC}"

echo -n "  Mirror Bridge (auto-discovery)..."
rm -f "$BUILD_DIR/medium_mb_auto.so"
start=$(date +%s%3N)
cd "$PROJECT_ROOT" && ./mirror_bridge_auto "$BENCHMARK_DIR/compile_time/medium" --module medium_mb_auto > /dev/null 2>&1
end=$(date +%s%3N)
time_mb_med_auto=$((end - start))
size_mb_med_auto=$(get_size_kb "$BUILD_DIR/medium_mb_auto.so")
cd "$BENCHMARK_DIR/compile_time/medium"
echo -e "${GREEN}${time_mb_med_auto}ms  (${size_mb_med_auto} KB)${NC}"

echo -n "  pybind11 (manual)...            "
rm -f "$BUILD_DIR/medium_pb.so"
result_pb_med=($(measure_compile_time_pybind11 "pybind11_binding.cpp" "$BUILD_DIR/medium_pb.so" "-I/usr/include/python3.10"))
time_pb_med=${result_pb_med[0]}
stddev_pb_med=${result_pb_med[1]}
size_pb_med=$(get_size_kb "$BUILD_DIR/medium_pb.so")
echo -e "${GREEN}${time_pb_med}ms ±${stddev_pb_med}ms  (${size_pb_med} KB)${NC}"

echo -n "  nanobind (manual)...            "
rm -f "$BUILD_DIR/medium_nb.so"
result_nb_med=($(measure_compile_time_nanobind "nanobind_binding.cpp" "$BUILD_DIR/medium_nb.so" "-I/usr/local/include"))
time_nb_med=${result_nb_med[0]}
stddev_nb_med=${result_nb_med[1]}
size_nb_med=$(get_size_kb "$BUILD_DIR/medium_nb.so")
echo -e "${GREEN}${time_nb_med}ms ±${stddev_nb_med}ms  (${size_nb_med} KB)${NC}"

echo -n "  SWIG (manual)...                "
rm -f "$BUILD_DIR/_medium_swig.so"
result_swig_med=($(measure_compile_time_swig "swig_binding.i" "$BUILD_DIR/_medium_swig.so" "-I."))
time_swig_med=${result_swig_med[0]}
stddev_swig_med=${result_swig_med[1]}
size_swig_med=$(get_size_kb "$BUILD_DIR/_medium_swig.so")
echo -e "${GREEN}${time_swig_med}ms ±${stddev_swig_med}ms  (${size_swig_med} KB)${NC}"

echo ""
ratio_manual_med_pb=$(awk "BEGIN {printf \"%.2f\", $time_pb_med/$time_mb_med_manual}")
ratio_auto_med_pb=$(awk "BEGIN {printf \"%.2f\", $time_pb_med/$time_mb_med_auto}")
ratio_manual_med_nb=$(awk "BEGIN {printf \"%.2f\", $time_nb_med/$time_mb_med_manual}")
ratio_auto_med_nb=$(awk "BEGIN {printf \"%.2f\", $time_nb_med/$time_mb_med_auto}")
ratio_manual_med_swig=$(awk "BEGIN {printf \"%.2f\", $time_swig_med/$time_mb_med_manual}")
ratio_auto_med_swig=$(awk "BEGIN {printf \"%.2f\", $time_swig_med/$time_mb_med_auto}")
echo -e "  Speedup vs pybind11:"
echo -e "    Manual binding:       ${ratio_manual_med_pb}x faster"
echo -e "    Auto-discovery:       ${ratio_auto_med_pb}x faster"
echo -e "  Speedup vs nanobind:"
echo -e "    Manual binding:       ${ratio_manual_med_nb}x faster"
echo -e "    Auto-discovery:       ${ratio_auto_med_nb}x faster"
echo -e "  Speedup vs SWIG:"
echo -e "    Manual binding:       ${ratio_manual_med_swig}x faster"
echo -e "    Auto-discovery:       ${ratio_auto_med_swig}x faster"
echo ""

# Developer Experience metrics
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  Developer Experience Metrics${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

echo -e "${BLUE}Lines of Binding Code${NC}"
echo ""
echo "  Simple project:"
echo "    Mirror Bridge (manual):        $(wc -l < "$BENCHMARK_DIR/compile_time/simple/mirror_bridge_binding.cpp" | tr -d ' ') lines"
echo "    Mirror Bridge (auto-discovery): 0 lines (just: mirror_bridge_auto src/ --module name)"
echo "    pybind11:                      $(wc -l < "$BENCHMARK_DIR/compile_time/simple/pybind11_binding.cpp" | tr -d ' ') lines"
echo ""
echo "  Medium project:"
echo "    Mirror Bridge (manual):        $(wc -l < "$BENCHMARK_DIR/compile_time/medium/mirror_bridge_binding.cpp" | tr -d ' ') lines"
echo "    Mirror Bridge (auto-discovery): 0 lines (just: mirror_bridge_auto src/ --module name)"
echo "    pybind11:                      $(wc -l < "$BENCHMARK_DIR/compile_time/medium/pybind11_binding.cpp" | tr -d ' ') lines"
echo ""
echo "  Code reduction vs pybind11:"
echo "    Simple:  $(wc -l < "$BENCHMARK_DIR/compile_time/simple/pybind11_binding.cpp" | tr -d ' ')x less with manual, infinite with auto-discovery"
echo "    Medium:  $(wc -l < "$BENCHMARK_DIR/compile_time/medium/pybind11_binding.cpp" | tr -d ' ')x less with manual, infinite with auto-discovery"
echo ""

# Runtime benchmarks
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  PART 2: Runtime Performance${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""

cd "$BENCHMARK_DIR/runtime/python"

# Build runtime benchmark modules
echo "Building runtime benchmark modules..."
echo ""

# One compile command for HEAD and for the gate's baseline. The gate divides
# one module's timings by the other's, so a flag that differed between the two
# builds would be reported as a regression, or hide one.
#   $1  root of the source tree to build from
#   $2  output module
build_mirror_bridge_bench() {
    local root=$1 out=$2
    rm -f "$out"
    clang++ -std=c++2c -freflection -freflection-latest -stdlib=libc++ \
        -O3 -DNDEBUG \
        -I"$root" -I"$root/benchmarks/runtime/shared" -fPIC -shared \
        $(python3-config --includes --ldflags) \
        "$root/benchmarks/runtime/python/mirror_bridge_binding.cpp" -o "$out" 2>&1 | grep -v "mixture of designated" || true
}

build_mirror_bridge_bench "$PROJECT_ROOT" "$BUILD_DIR/bench_mb.so"

# The regression gate (check_ratios.py) compares HEAD with mirror_bridge at the
# commit named in gate_baseline.json, built here and timed below in the same
# run. The module is built from that commit's own tree -- its headers, its
# binding file, its benchmark class -- into a directory of its own, because
# its init symbol is PyInit_bench_mb just like HEAD's and only the path tells
# the two apart.
#
# Nothing in here may abort the suite. A baseline that cannot be fetched or no
# longer compiles is a reason for the gate to fail, and it does, by name; it is
# not a reason to lose the month's table. So every failure is recorded in
# status.json, which the runner copies into the results for the gate to print.
#
# MB_GATE_BASELINE_ROOT points at an already checked-out tree to use instead,
# for asking "did my change slow anything down" against another worktree.
GATE_BASELINE_DIR="$BUILD_DIR/gate_baseline"

build_gate_baseline() {
    local sha tree="" scratch="" reason=""
    rm -rf "$GATE_BASELINE_DIR"
    mkdir -p "$GATE_BASELINE_DIR"

    sha=$(python3 -c 'import json, re, sys
commit = json.load(open(sys.argv[1]))["commit"]
assert re.fullmatch("[0-9a-f]{40}", commit)
print(commit)' "$BENCHMARK_DIR/gate_baseline.json" 2>/dev/null) || sha=""

    if [ -n "${MB_GATE_BASELINE_ROOT:-}" ]; then
        tree="$MB_GATE_BASELINE_ROOT"
        sha="local tree $tree"
        [ -d "$tree" ] || reason="MB_GATE_BASELINE_ROOT=$tree is not a directory"
    elif [ -z "$sha" ]; then
        reason="benchmarks/gate_baseline.json does not name a full 40-character commit"
    else
        # CI checks out one commit deep, so the baseline is usually not in the
        # object store yet. Fetching by SHA needs no branch or tag to exist.
        if ! git -C "$PROJECT_ROOT" cat-file -e "$sha^{commit}" 2>/dev/null; then
            git -C "$PROJECT_ROOT" fetch --quiet --depth 1 origin "$sha" || true
        fi
        if ! git -C "$PROJECT_ROOT" cat-file -e "$sha^{commit}" 2>/dev/null; then
            reason="commit $sha is not in this checkout and could not be fetched from origin"
        else
            scratch=$(mktemp -d)
            tree="$scratch"
            if ! git -C "$PROJECT_ROOT" archive "$sha" | tar -x -C "$tree"; then
                reason="commit $sha could not be extracted with git archive"
            fi
        fi
    fi

    if [ -z "$reason" ]; then
        echo "Building the gate baseline from $sha..."
        build_mirror_bridge_bench "$tree" "$GATE_BASELINE_DIR/bench_mb.so"
        if [ ! -f "$GATE_BASELINE_DIR/bench_mb.so" ]; then
            reason="the benchmark module at $sha did not compile with this toolchain"
        fi
    fi
    [ -n "$scratch" ] && rm -rf "$scratch"

    if [ -n "$reason" ]; then
        echo -e "${YELLOW}Gate baseline unavailable: $reason${NC}"
    fi
    python3 -c 'import json, sys
json.dump({"commit": sys.argv[2], "reason": sys.argv[3] or None}, open(sys.argv[1], "w"))' \
        "$GATE_BASELINE_DIR/status.json" "$sha" "$reason"
}

build_gate_baseline

clang++ -std=c++20 -stdlib=libc++ \
    -O3 -DNDEBUG \
    -I"$(python3 -c 'import pybind11; print(pybind11.get_include())')" \
    -I"$BENCHMARK_DIR/runtime/shared" -fPIC -shared \
    $(python3-config --includes --ldflags) \
    pybind11_binding.cpp -o "$BUILD_DIR/bench_pb.so" 2>&1 | grep -v "mixture of designated" || true

# Build nanobind runtime module (reuse pre-compiled stub if available)
if [ -f "$BUILD_DIR/nb_stub.o" ]; then
    clang++ -std=c++17 -stdlib=libc++ \
        -O3 -DNDEBUG \
        -I/usr/local/nanobind/include \
        -I/usr/local/nanobind/ext/robin_map/include \
        -I"$BENCHMARK_DIR/runtime/shared" \
        -fPIC -shared \
        $(python3-config --includes --ldflags) \
        nanobind_binding.cpp \
        "$BUILD_DIR/nb_stub.o" \
        -o "$BUILD_DIR/bench_nb.so" 2>&1 | grep -v "mixture of designated" || true
else
    clang++ -std=c++17 -stdlib=libc++ \
        -O3 -DNDEBUG \
        -I/usr/local/include \
        -I"$BENCHMARK_DIR/runtime/shared" \
        -fPIC -shared \
        $(python3-config --includes --ldflags) \
        nanobind_binding.cpp \
        -o "$BUILD_DIR/bench_nb.so" 2>&1 | grep -v "mixture of designated" || true
fi

# Build SWIG runtime module
swig -c++ -python -I"$BENCHMARK_DIR/runtime/shared" -o "$BUILD_DIR/swig_binding_wrap.cpp" swig_binding.i 2>/dev/null || true
clang++ -std=c++20 -stdlib=libc++ \
    -O3 -DNDEBUG \
    -I"$BENCHMARK_DIR/runtime/shared" \
    -fPIC -shared \
    $(python3-config --includes --ldflags) \
    "$BUILD_DIR/swig_binding_wrap.cpp" \
    -o "$BUILD_DIR/_bench_swig.so" 2>&1 | grep -v "mixture of designated" || true
# Copy Python wrapper for SWIG
cp "$BUILD_DIR/bench_swig.py" "$BUILD_DIR/" 2>/dev/null || true

# Try to build Boost.Python module (may fail with libc++)
if clang++ -std=c++20 -stdlib=libc++ \
    -O3 -DNDEBUG \
    -I/usr/include/python3.10 -I"$BENCHMARK_DIR/runtime/shared" -fPIC -shared \
    $(python3-config --includes --ldflags) \
    -lboost_python310 \
    boost_python_binding.cpp -o "$BUILD_DIR/bench_bp.so" 2>&1 | grep -v "mixture of designated" > /dev/null; then
    echo "Boost.Python module built successfully"
else
    echo -e "${YELLOW}Boost.Python skipped (build failed - likely libc++ incompatibility)${NC}"
fi
echo ""

echo "Running runtime benchmarks (this may take a few minutes)..."
export LD_LIBRARY_PATH=/usr/local/lib/aarch64-unknown-linux-gnu:/usr/local/lib/x86_64-unknown-linux-gnu:$LD_LIBRARY_PATH
MB_BENCH_BUILD="$BUILD_DIR" MB_BENCH_BASELINE_BUILD="$GATE_BASELINE_DIR" \
    python3 run_runtime_benchmarks.py run

# ============================================================================
# PART 3: Trading Workloads
# ============================================================================
# Three shapes of real work rather than one operation at a time, so the page
# can say where the binding layer decides the result and where it does not.
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  PART 3: Trading Workloads${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

TRADE_PYINC=$(python3-config --includes)
TRADE_OK=0

echo -n "  Building mirror_bridge module... "
if clang++ -std=c++2c -freflection -freflection-latest -stdlib=libc++ -O3 -DNDEBUG -fPIC -shared \
    -I"$PROJECT_ROOT" -I"$BENCHMARK_DIR/runtime/python" $TRADE_PYINC \
    "$BENCHMARK_DIR/runtime/python/trading_mirror_bridge_binding.cpp" \
    -o "$BUILD_DIR/trade_mb.so" > /dev/null 2>&1; then
    echo "ok"; TRADE_OK=1
else
    echo -e "${YELLOW}failed${NC}"
fi

PB_INC=$(python3 -c "import pybind11; print(pybind11.get_include())" 2>/dev/null || echo "")
if [ -n "$PB_INC" ]; then
    echo -n "  Building pybind11 module...      "
    clang++ -std=c++17 -O3 -DNDEBUG -fPIC -shared -I"$PB_INC" \
        -I"$BENCHMARK_DIR/runtime/python" $TRADE_PYINC \
        "$BENCHMARK_DIR/runtime/python/trading_pybind11_binding.cpp" \
        -o "$BUILD_DIR/trade_pb.so" > /dev/null 2>&1 && echo "ok" || echo -e "${YELLOW}failed${NC}"
fi

NB_ROOT=$(python3 -c "import nanobind, os; print(os.path.dirname(nanobind.__file__))" 2>/dev/null || echo "")
[ -d "/usr/local/nanobind" ] && NB_ROOT=/usr/local/nanobind
if [ -n "$NB_ROOT" ] && [ -d "$NB_ROOT/include" ]; then
    echo -n "  Building nanobind module...      "
    if [ ! -f "$BUILD_DIR/nb_stub_trade.o" ]; then
        clang++ -std=c++17 -O3 -DNDEBUG -fPIC -c -I"$NB_ROOT/include" \
            -I"$NB_ROOT/ext/robin_map/include" $TRADE_PYINC \
            "$NB_ROOT/src/nb_combined.cpp" -o "$BUILD_DIR/nb_stub_trade.o" > /dev/null 2>&1 || true
    fi
    clang++ -std=c++17 -O3 -DNDEBUG -fPIC -shared -I"$NB_ROOT/include" \
        -I"$NB_ROOT/ext/robin_map/include" -I"$BENCHMARK_DIR/runtime/python" $TRADE_PYINC \
        "$BENCHMARK_DIR/runtime/python/trading_nanobind_binding.cpp" "$BUILD_DIR/nb_stub_trade.o" \
        -o "$BUILD_DIR/trade_nb.so" > /dev/null 2>&1 && echo "ok" || echo -e "${YELLOW}failed${NC}"
fi

if [ "$TRADE_OK" -eq 1 ]; then
    echo ""
    MB_BENCH_BUILD="$BUILD_DIR" python3 "$BENCHMARK_DIR/runtime/python/run_trading_benchmarks.py" || true
else
    echo -e "${YELLOW}  Trading workloads skipped (no module built)${NC}"
fi

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Benchmark Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Results summary:"
echo "  - Compile-time results: See above"
echo "  - Runtime results: See above table"
echo "  - Detailed runtime data: benchmarks/runtime/python/runtime_results.json"
echo "  - Trading workloads:     benchmarks/runtime/python/trading_results.json"
echo ""
