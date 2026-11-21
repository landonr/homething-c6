#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define IDLE_SLEEP_LATCH_MAGIC 0x4C415431u

// flags
#define IDLE_SLEEP_STUB_READ 0x1u     // the stub ran the bus read
#define IDLE_SLEEP_STUB_ACK 0x2u      // the address byte was acknowledged
#define IDLE_SLEEP_STUB_SKIPPED 0x4u  // the wake cause was not a GPIO wake

// Written by the wake stub, read once by IdleSleep::setup(). RTC_DATA_ATTR
// lies outside the RTC region the ROM CRC-checks before it calls the stub.
typedef struct {
  uint32_t magic;
  uint32_t flags;
  uint32_t port;          // PCF8575 P00..P17, bit n = expander pin n, 0 = pressed
  uint32_t cause;         // raw PMU wake cause bits
  uint32_t cycles;        // CPU cycles from wake to stub entry
  uint32_t ticks_per_us;  // ROM delay scale at stub time
  uint32_t lp_ticks_lo;   // LP timer at the end of the stub read
  uint32_t lp_ticks_hi;
} idle_sleep_latch_t;

extern idle_sleep_latch_t idle_sleep_latch;

#ifdef __cplusplus
}
#endif
