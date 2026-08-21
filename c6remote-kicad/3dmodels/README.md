# 3D model sources

Models the project footprints reference through `${KIPRJMOD}/3dmodels/`. Every file's origin, so a replacement starts from the same source rather than a guess.

- `5221 ANO Rotary Encoder.step`: [GrabCAD, Adafruit 5001 ANO Rotary Encoder](https://grabcad.com/library/adafruit-5001-ano-rotary-encoder-1).
- `Seeed Studio XIAO ESP32-C6.step`: [GrabCAD, Seeed Studio XIAO ESP32-C6](https://grabcad.com/library/seeed-studio-xiao-esp32-c6-1).
- `TL3315NF160Q.wrl`: modelled for this repo from the E-Switch TL3315NF160Q datasheet drawing (4.5 x 4.5 x 0.55 gold snap dome), replacing a wrong 5mm PTS647 model; see commit 8757cb5.
- `TSOP6136.step`: Vishay doc 82826, re-exported already rotated into place, so the footprint's `offset` and `rotate` are all zero on purpose; do not "fix" them.
- `TSOP6136TT.step`: derived from the checked-in Vishay doc 82826 `TSOP6136.step`, rotated into the TT top-view attitude. Lead bend is approximate; body envelope is exact. Footprint offset and rotation stay zero.
- `WS2812C-2020.step`: [Printables model 1760436, WS2812B-2020 / WS2812C-2020](https://www.printables.com/model/1760436-ws2812b-2020-ws2812c-2020). Stands in for the XL-2020RGBC-WS2812B on D2-D5, same 2.0 x 2.0 package; the KiCad stock library carries no 2020-size WS2812 model.
