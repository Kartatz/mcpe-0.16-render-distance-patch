# MCPE 0.16.2 — Render Distance Cap: Full Context Dump

Everything discovered while reverse-engineering the render distance ("chunks") limit of
Minecraft Pocket Edition **0.16.2** for Android, and how it was raised to 64 chunks
(steps: powers of two, 2 → 64).

---

## 1. Target

| | |
|---|---|
| APK | `minecraft-pe-0-16-2.apk` (stock, 2016-11-16) |
| Library | `lib/armeabi-v7a/libminecraftpe.so` |
| Format | ELF 32-bit LSB, ARM EABI5, **Thumb-2 code, stripped of `.symtab`** |
| Symbols | `.dynsym` intact: ~54,067 exported mangled C++ symbols |
| `.text` | addr/off `0x00695580`, size `0x11714EA` (identity-mapped; vaddr == file offset for `.text` and `.rodata`) |
| `.got` | `0x01BD6578` |
| Dynamic relocs | `.rel.dyn` @ `0x535968`, `.rel.plt` @ `0x5E2EA8` |

Strings in `.rodata` confirm option keys:

```
gfx_renderdistance        gfx_renderdistance_new
viewDistanceChunks        options.renderDistanceNew ...
```

## 2. How MCPE 0.16 decides the maximum

Decision function: **`MinecraftOptionValue::getRenderDistanceLevels()`** @ `0x00ADF1C8`

1. Calls `AppPlatform::singleton` → virtual method (vtable slot `+0x138`) that returns the
   **device's total physical RAM in bytes** as a 64-bit value (`r0:r1`).
2. Compares it (unsigned, 64-bit as `high==0 && low<C`) against **four hard-coded thresholds**
   and selects one preset level list:

| Total RAM | Threshold constant | Level list (`.rodata`) | Slider/buttons max |
|---|---|---|---|
| ≥ ~3.80 GiB | `0xF3C00001` | `[8,10,12,14,18,22]` | **22** |
| ~1.86–3.79 GiB | `0x76C00001` | `[8,10,12,14,18,22]` | **22** |
| ~491 MiB–1.85 GiB | `0x1EA00000` (514,850,816) | `[6,8,10,12,14]` | 14 |
| ~230–490 MiB | `0x0E600000` (241,591,808) | `[4,6,8,10]` | 10 |
| < 230 MiB | — | fall-through small list | < 10 |

The top two tiers are **literally identical** copies. Devices with ≥1.86 GiB RAM are all
capped at **22 chunks** — that is the entire origin of the "22".

The chosen list's **last element = UI maximum**. It is consumed by:
- the new (0.16 JSON) settings UI via `SettingsScreenControllerBase::setUpCallbacksForStepOption`
  (steps provider = `getRenderDistanceLevels()`)
- the legacy +/- buttons via `MinecraftClient::handleIncreaseRenderDistanceButtonPress`
  (picks "first level > current" from the vector)
- VR mode: `MinecraftOptionValue::getVRRenderDistanceLevels()` @ `0x00ADF3E0` derives its own
  list by **multiplying each level by 0.5** at runtime.

`Options::getMaxViewDistanceChunks()` @ `0x00AE349A` returns a cached copy of the device max
(stored in the Options object at startup), used by the slider-setup text path
(`ParameterStringify`) and by `MinecraftClient::startLocalServer` (the integrated server max).

## 3. Key symbols & addresses (stock binary)

| Address | Symbol | Role |
|---|---|---|
| `0x00AE3476` | `Options::setViewDistanceChunks(int)` | writes stored option (field `+0x64` / VR `+0xAC`), **no clamp** |
| `0x00AE3486` | `Options::getViewDistanceChunks()` | reads stored option, **no clamp** |
| `0x00AE349A` | `Options::getMaxViewDistanceChunks()` | device max accessor (**patch point #1**) |
| `0x00ADF1C8` | `MinecraftOptionValue::getRenderDistanceLevels()` | RAM-tier level list selector |
| `0x00ADF3E0` | `MinecraftOptionValue::getVRRenderDistanceLevels()` | halves the list |
| `0x00AFB810` | `LocalPlayer::requestChunkRadius(int)` | stores requested radius (`[this+0x11FC]`), **no clamp**, notifies server |
| `0x00AFBEB4` | `LocalPlayer::getViewBlockRadius()` | `min(requested, Player::getChunkRadius()) * 16` → blocks |
| `0x00DF2DF8` | `ServerPlayer::setRequestedChunkRadius(int)` | `clamp(req, 4, serverMax)` ← **`[this+0x10B4]` = server max** |
| `0x00DF2E60` | `ServerPlayer::calculateNewChunkRadius()` | same clamp |
| `0x00F9CC38/40` | `Player::getChunkRadius` / `setChunkRadius(int)` | actual radius (`[this+0x1090]`), **no clamp** |
| `0x00BF2668` | `LevelRenderer::onViewRadiusChanged(bool,bool)` | rebuilds view state every radius change |
| `0x00BF2900` | `LevelRenderer::_recalculateRenderDistance()` | fog-distance stepper |
| `0x00BF2A10` | `LevelRenderer::updateFarChunksDistance()` | fog start/end, no cap |
| `0x00AE03D8` | `Options::_load()` | options.txt parsing |

### Static level tables (`.rodata`, 6-slot `int[]`)

| Table | File offset | Stock contents |
|---|---|---|
| A | `0x01A93FF0` | `8 10 12 14 18 22` |
| B | `0x01A94008` | `8 10 12 14 18 22` |
| C | `0x01A94020` | `6 8 10 12 14` |
| D | `0x01A94038` | `4 6 8 10` |

## 4. End-to-end radius pipeline (why no other cap exists beyond the patch points)

```
Settings UI (slider / buttons)
  └─ steps in [8..22]            <- TierMax, tables A/B (patch #2/#3)
Options::setViewDistanceChunks   <- raw store, no clamp
Options::_load (gfx_renderdistance_new)
  └─ chunks = max(levels[0], stored >> 4)   <- MIN clamp only, no upper clamp!
LocalPlayer::requestChunkRadius  <- raw store, no clamp
ServerPlayer::setRequestedChunkRadius
  └─ clamp(requested, 4, serverMax)
       serverMax [ServerPlayer+0x10B4]
       └─ MinecraftClient::startLocalServer
            └─ Options::getMaxViewDistanceChunks   <- patch #1 (constant)
LocalPlayer::getViewBlockRadius = min(requested, server-accepted) * 16
LevelRenderer::onViewRadiusChanged / _recalculateRenderDistance / fog
  └─ no upper cap; the 40.0f constant in _recalculateRenderDistance is a
     FLOOR for its per-frame distance stepper, not a ceiling.
```

Server-side floor: radius is clamped to a minimum of **4** in
`ServerPlayer::setRequestedChunkRadius`, so below 4 the client renders fewer chunks than
the world loads (harmless).

## 5. The patch (what `patch_lib.py` does)

Three edits (all against the stock binary; offsets == vaddrs):

### #1 — `Options::getMaxViewDistanceChunks` @ `0x00AE349A`

Force the device-max accessor to return a constant (`NEW_MAX`):

| | Bytes |
|---|---|
| Original | `D0 F8 BC 01  50 F8 04 0C  70 47` (`ldr.w r0,[r0,#0x1BC]; ldr r0,[r0,#-4]; bx lr`) |
| Patched (64) | `40 20  70 47  00 BF 00 BF 00 BF` (`movs r0,#64; bx lr; nop×3`) |

Thumb encoding: `movs r0, #imm` = `0x2000 | (imm<<8)` → LE bytes `[imm, 0x20]`.

### #2 / #3 — Level tables A/B

Replace both 6-slot tables `[8,10,12,14,18,22]` with `[2,4,8,16,32,NEW_MAX]`
(A @ `0x01A93FF0`, B @ `0x01A94008`, 6× little-endian int32 each).

This changes: new-UI step list, legacy +/- button steps, legacy ordinal ("far") mapping
(last element), and VR halves automatically (64 → 32 VR).

Everything else in the pipeline adapts because it is all computed from these sources.

## 6. Repack / sign / verify pipeline

```bash
cd work
zip patched.apk lib/armeabi-v7a/libminecraftpe.so          # update entry in a copy of the APK
zip -d patched.apk 'META-INF/MANIFEST.MF' 'META-INF/*.SF' 'META-INF/*.RSA'
keytool -genkeypair -alias mcpe -keyalg RSA -keysize 2048 -validity 10000 \
        -keystore rd.keystore -storepass android -keypass android -dname "CN=MCPE Patch"
apksigner sign --ks rd.keystore --ks-pass pass:android --ks-key-alias mcpe \
        --in patched.apk --out patched-signed.apk
apksigner verify -v patched-signed.apk        # expect v1+v2+v3 = true
```

Post-sign verification: re-extract the `.so` from the signed APK and assert
`bytes[0xAE349A:0xAE349C] == [NEW_MAX, 0x20]` and the table values at `0x1A93FF0`/`0x1A94008`.

Install note: the patched APK does not install over the Play/beta signature — uninstall
first (`games/com.mojang` worlds usually survive, but back them up).

## 7. Values tried

| Max | Notes |
|---|---|
| 40 | First attempt; chosen believing `40.0f` in `_recalculateRenderDistance` was a ceiling (it isn't — it's a floor for the transition stepper) |
| 128 | Engine-max experiment; works in code end-to-end, but ≈66k chunks in view → huge RAM/long mesh builds. Theoretical-max territory |
| 64 ✅ | Practical sweet spot; shipped here with power-of-two steps `2/4/8/16/32/64` |

## 8. Reverse-engineering notes

- objdump here was x86-only → all ARM/Thumb-2 disassembly done with **Capstone** (`pip install capstone`, venv).
- Capstone's `disasm()` stops at the first invalid byte → always `md.skipdata = True` when scanning `.text`.
- The lib is linked so that **all internal calls to exported functions go through ARM-mode PLT
  stubs** (12-byte entries: `add ip,pc,#A; add ip,ip,#B; ldr pc,[ip,#C]` in `.plt`,
  `ADD` immediates arrive as `imm8 ROR rot` — parse via `((rm>>rot)|(rm<<(32-rot)))`).
  Map stub→symbol by computing the GOT slot address and looking it up in `readelf -rW`
  (`R_ARM_JUMP_SLOT` entries). `readelf` truncates long C++ names without `-W`.
- The `.got`/table base for `getRenderDistanceLevels` is relocation-filled at load time
  (`.data.rel.ro`), so tier table pointers can't be read statically — find arrays by
  scanning `.rodata` for the integer sequences instead.
- `getViewDistanceChunks`/`setViewDistanceChunks` use field `+0x64` normally and `+0xAC`
  when the VR flag (`byte +0x4C`) is set — two option copies (HoloLens/VR).

## 9. Caveats

- 0.16.2 only: offsets are specific to the stock `libminecraftpe.so` (SHA-256 of the
  original `.so` is what the patcher implicitly guards on; it aborts on any byte mismatch).
- 64 chunks on 2016-era hardware: expect heavy initial mesh build and multi-GB RAM usage
  on large/detailed worlds. Drop the slider to 32/16/8 for normal play.
- LAN/other players: clients negotiate radius via `RequestChunkRadiusPacket`; the
  integrated server offers its (patched) max, so behavior is consistent locally.
