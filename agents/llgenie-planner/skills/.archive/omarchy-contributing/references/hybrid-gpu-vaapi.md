# Hybrid GPU VA-API Configuration

Worked example: fixing broken video decode and rendering on hybrid NVIDIA laptops
where the panel scans out through Intel.

## Problem

On hybrid GPU laptops (e.g., MSI Titan GT77HX with RTX 4090 + Intel UHD),
Omarchy's `default/hypr/nvidia.lua` sets `LIBVA_DRIVER_NAME=nvidia` when an NVIDIA
GPU is detected. This breaks Chromium-based browsers — black screen, spinner,
audio-only playback — because decoded frames from the NVIDIA GPU cannot be handed
back to the Intel compositor over Wayland.

Additionally, GL rendering defaults to NVIDIA even when VA-API is fixed, causing
rendering glitches because NVIDIA-rendered frames must cross the PCIe bus to the
Intel compositor. Both must be addressed.

## Solution

### For end-user systems (browser-scoped fix)

**NEVER use global Hyprland overrides** — the user explicitly wants browser-only
changes that don't affect the system or other apps. System stays `nvidia`.

Scope env vars to browser launch wrappers in `/usr/bin/`:

```bash

# /usr/bin/brave — add before exec /opt/brave-bin/brave:
export LIBVA_DRIVER_NAME=iHD
export MESA_LOADER_DRIVER_OVERRIDE=iris

# /usr/bin/google-chrome-beta — add before exec:
export LIBVA_DRIVER_NAME=iHD
export MESA_LOADER_DRIVER_OVERRIDE=iris

# /usr/bin/chromium — move binary to chromium.real, create wrapper:
export LIBVA_DRIVER_NAME=iHD
export MESA_LOADER_DRIVER_OVERRIDE=iris
exec /usr/bin/chromium.real "$@"
```

**Why both env vars:** `LIBVA_DRIVER_NAME=iHD` fixes video decode. `MESA_LOADER_DRIVER_OVERRIDE=iris` forces Intel for GL rendering too, so everything stays on the iGPU and avoids cross-GPU copies.

**Pitfall — Hyprland Lua override path is WRONG for this.** `bootstrap.lua` adds
`~/.config/?.lua` to Lua's package.path, so `require("default.hypr.nvidia")`
resolves to `~/.config/default/hypr/nvidia.lua`, NOT
`~/.config/omarchy/default/hypr/nvidia.lua`. Putting the override at the
wrong path means it never loads and the upstream version wins silently.

### For upstream Omarchy contribution

Two parts are needed:

#### 1. Driver selection (`default/hypr/nvidia.lua`)

Detect hybrid GPU configurations and use Intel iHD for VA-API video decoding
while keeping NVIDIA for GL rendering:

```lua
local hybrid_gpu = paths.omarchy_path .. "/bin/omarchy-hw-hybrid-gpu"

if o.shell_succeeds(o.shell_quote(nvidia)) then
  if o.shell_succeeds(o.shell_quote(nvidia_gsp)) then
    hl.env("NVD_BACKEND", "direct")
    hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    if o.shell_succeeds(o.shell_quote(hybrid_gpu)) then
      hl.env("LIBVA_DRIVER_NAME", "iHD")
    else
      hl.env("LIBVA_DRIVER_NAME", "nvidia")
    end
  elseif o.shell_succeeds(o.shell_quote(nvidia_without_gsp)) then
    hl.env("NVD_BACKEND", "egl")
    hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    if o.shell_succeeds(o.shell_quote(hybrid_gpu)) then
      hl.env("LIBVA_DRIVER_NAME", "iHD")
    else
      hl.env("LIBVA_DRIVER_NAME", "nvidia")
    end
  end
end
```

#### 2. Browser flags (`config/chromium-flags.conf`)

```
--enable-features=VaapiVideoDecoder,VaapiIgnoreDriverChecks
--disable-features=UseChromeOSDirectVideoDecoder
```

Without these flags, Chromium falls back to software decode regardless of the
driver. Both parts are required for the fix to work.

## Testing Pattern (upstream contributions only)

To test Hyprland Lua modules without a compositor:

1. **Create a Lua harness** (`test/shell.d/fixtures/<name>.lua`) that stubs
   `hl.env`, `o.shell_succeeds`, `o.shell_quote`, and prints captured env as JSON.
2. **Create a bash driver** (`test/shell.d/<name>-test.sh`) that sources
   `test/shell.d/base-test.sh`, creates a temp `OMARCHY_PATH` with mock `bin/`
   commands, and runs the harness for each test case.
3. **Mock hardware commands** as scripts that exit 0 (yes) or 1 (no).

## Pitfalls

### chmod on directory vs files

```bash

# WRONG — only chmods the directory, not the files inside
chmod +x "$MOCK_DIR/bin/"

# CORRECT — chmods each file
chmod +x "$MOCK_DIR/bin/"*
```

### jq path in assertions

The Lua harness prints `{ "env": { ... }, "order": [...] }`. Use `.env.<NAME>`:

```bash
actual=$(echo "$output" | jq -r '.env.__GLX_VENDOR_LIBRARY_NAME')  # CORRECT
actual=$(echo "$output" | jq -r '.__GLX_VENDOR_LIBRARY_NAME')       # WRONG
```

### os.execute return value

Lua 5.3+ `os.execute` returns `true` for exit 0. Use `return success == true`.

### grep with `--` for flags starting with `-`

```bash

# WRONG — grep treats --enable-features=... as an option
grep -Fxq '--enable-features=VaapiVideoDecoder' file.conf

# CORRECT
grep -Fxq -- '--enable-features=VaapiVideoDecoder' file.conf
```

### Browser wrapper env vars must be scoped

User explicitly requires browser-only fixes. System must stay `nvidia`.
Patched wrappers in `/usr/bin/` are the correct approach — not global
Hyprland Lua overrides.

### Duplicate issue commenting

When the same root cause produces multiple open issues, do NOT paste the same
full analysis to every issue. Instead:
1. Find the canonical issue (most comments/traction) — that's the one that
   holds the full root-cause analysis, regression history, and workaround.
2. For all other duplicates, post a brief comment stating `Duplicate of #<canonical>`
   with a one-line summary of the fix/workaround. Do NOT duplicate the full analysis.

This avoids noise and keeps discussion focused.

### Verify PR merge status before claiming fixes landed

`gh pr view <num> --json state,mergedAt` — a PR with `state=CLOSED` and
`mergedAt=null` was closed without merge. Zero fix PRs for a given bug means
no upstream fix has landed — every upgrade re-regresses. Always verify before
reporting status.

## Key Insight

The module constructs paths as `paths.omarchy_path .. "/bin/omarchy-hw-*"`.
The `paths.lua` module reads `OMARCHY_PATH` from the environment, so setting
`OMARCHY_PATH` to a temp directory with mock `bin/` commands makes the module
use your mocks instead of real hardware detection.
