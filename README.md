# mcpe-0.16-render-distance-patch

Binary patcher for **Minecraft Pocket Edition 0.16.2 (Android, armeabi-v7a)** that raises the
render distance cap beyond the stock maximum of 22 chunks.

- `patch_lib.py` — patches `libminecraftpe.so` in place (idempotent-safe: verifies original bytes first, aborts on mismatch)
- `CONTEXT.md` — full reverse-engineering dump: how the cap is decided, every relevant function/offset, and the rebuild/sign/verify pipeline

## Quick start

```bash
# 1. Extract the native lib from your own APK
unzip minecraft-pe-0-16-2.apk 'lib/armeabi-v7a/libminecraftpe.so' -d work
cd work/lib/armeabi-v7a
cp libminecraftpe.so libminecraftpe.so.orig     # keep a pristine copy

# 2. Patch (edit NEW_MAX / NEW_TABLE at the top of the script)
python3 patch_lib.py

# 3. Repack + sign
cp minecraft-pe-0-16-2.apk mcpe-0-16-2-patched.apk
cd work  # dir containing lib/
zip ../../mcpe-0-16-2-patched.apk lib/armeabi-v7a/libminecraftpe.so
zip -d ../../mcpe-0-16-2-patched.apk 'META-INF/MANIFEST.MF' 'META-INF/*.SF' 'META-INF/*.RSA'
keytool -genkeypair -alias mcpe -keyalg RSA -keysize 2048 -validity 10000 \
        -keystore rd.keystore -storepass android -keypass android -dname "CN=MCPE Patch"
apksigner sign --ks rd.keystore --ks-pass pass:android --ks-key-alias mcpe \
        --in mcpe-0-16-2-patched.apk --out mcpe-0-16-2-patched-signed.apk
apksigner verify -v mcpe-0-16-2-patched-signed.apk
```

Install note: the APK must be uninstalled/reinstalled (signature differs from the Play build).

## Default patch

- Render distance steps in Settings: **2 / 4 / 8 / 16 / 32 / 64** chunks
- `Options::getMaxViewDistanceChunks()` returns **64**

Tested values: 40 / 128 / 64. 64 is the practical sweet spot; 128 works but is brutal on RAM and mesh build time.

## Legal

This repo contains only an offset-based patcher and reverse-engineering notes. No game files,
assets, or binaries are included. You need your own copy of MCPE 0.16.2.
