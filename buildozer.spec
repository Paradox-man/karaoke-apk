[app]
title = Karaoke
package.name = karaokeapp
package.domain = org.karaoke
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,numpy,av,yt-dlp,certifi,openssl
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
