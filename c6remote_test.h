// Render helpers shared by c6remote-test-v1/v2 via `esphome: includes:`.
// Pure functions only: this header is emitted ahead of the generated globals
// in main.cpp, so it cannot reference them.

#pragma once

#include <cstdint>

#include "esphome/core/color.h"
#include "esphome/core/helpers.h"

namespace c6remote_test {

using esphome::Color;

// strip goes green while the mic is listening
constexpr float MIC_HUE = 120.0f;

inline float clamp01(float v) { return v < 0.0f ? 0.0f : (v > 1.0f ? 1.0f : v); }

// output ceiling; falls back on NaN or out-of-range, which would blank the strip
inline float safe_cap(float raw, float fallback = 0.4f) {
  return (raw > 0.0f && raw <= 1.0f) ? raw : fallback;
}

// IR frame surges to full, then decays linearly
inline float ir_boost(uint32_t now, uint32_t last, uint32_t decay_ms = 700) {
  if (last == 0)
    return 0.0f;
  const uint32_t age = now - last;
  if (age >= decay_ms)
    return 0.0f;
  return 1.0f - (float) age / (float) decay_ms;
}

// envelope follower, fast attack slow release; `env` is caller state, updated in place
inline float mic_boost(float &env, float peak, float gain = 8.0f) {
  const float m = clamp01(peak * gain);
  env += (m - env) * (m > env ? 0.6f : 0.06f);
  return env;
}

// boost only adds, never pulls below the set level
inline float apply_boost(float v, float boost) { return v + (1.0f - v) * boost; }

// rate 1 = 1.6s period, 8 = 200ms, 0 steady
inline bool blink_gate(uint32_t now, int rate) {
  if (rate <= 0)
    return true;
  const uint32_t period = 1600 / (uint32_t) rate;
  return (now % period) < period / 2;
}

// white flash overlay, `pulses` blinks at 130ms on / 130ms off
inline bool flash_on(uint32_t now, uint32_t start, int pulses) {
  if (pulses <= 0)
    return false;
  const uint32_t dt = now - start;
  return dt < (uint32_t) pulses * 260 && (dt / 130) % 2 == 0;
}

// which LED the chase self test lights now
inline int chase_index(uint32_t now, int count) {
  return count > 0 ? (int) ((now / 200) % (uint32_t) count) : 0;
}

inline Color hsv(float hue, float sat, float val) {
  float r, g, b;
  esphome::hsv_to_rgb((int) hue, sat, val, r, g, b);
  return Color((uint8_t) (r * 255), (uint8_t) (g * 255), (uint8_t) (b * 255));
}

}  // namespace c6remote_test
