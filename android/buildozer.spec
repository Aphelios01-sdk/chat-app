[app]

title = Chat Terminal
package.name = chatterminal
package.domain = com.example

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json

version = 1.0

requirements = python3,kivy

orientation = portrait

fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

[buildozer]

log_level = 2

warn_on_root = 1

build_dir = ./build

dist_dir = ./dist
