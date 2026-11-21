#include "wake_stub.h"

#include "esphome/core/defines.h"
#include "esp_attr.h"

RTC_DATA_ATTR idle_sleep_latch_t idle_sleep_latch;

#ifdef USE_IDLE_SLEEP_WAKE_STUB

#include "esp_cpu.h"
#include "esp_private/esp_pmu.h"
#include "esp_rom_sys.h"
#include "esp_sleep.h"
#include "esp_wake_stub.h"
#include "soc/gpio_reg.h"
#include "soc/gpio_sig_map.h"
#include "soc/io_mux_reg.h"
#include "soc/lp_timer_reg.h"
#include "soc/soc.h"

// The stub runs before the bootloader: only RTC code, ROM calls and direct
// register access. Every helper is RTC_IRAM_ATTR so an out-of-line copy
// cannot land in flash.

#define STUB_SDA 22
#define STUB_SCL 23
#define STUB_ADDR_READ ((0x20u << 1) | 1u)
// 10 us is 50 kHz. It stays inside the 100 kHz limits even if the ROM delay
// scale is off by 2x.
#define STUB_HALF_US 10
#define STUB_IOMUX_GPIO (FUN_IE | (2u << FUN_DRV_S) | (PIN_FUNC_GPIO << MCU_SEL_S))

static RTC_IRAM_ATTR void stub_drive_low(uint32_t pin) { REG_WRITE(GPIO_ENABLE_W1TS_REG, 1u << pin); }

static RTC_IRAM_ATTR void stub_release(uint32_t pin) { REG_WRITE(GPIO_ENABLE_W1TC_REG, 1u << pin); }

static RTC_IRAM_ATTR uint32_t stub_level(uint32_t pin) { return (REG_READ(GPIO_IN_REG) >> pin) & 1u; }

static RTC_IRAM_ATTR void stub_clock_high(void) {
  stub_release(STUB_SCL);
  for (uint32_t i = 0; i < 100 && stub_level(STUB_SCL) == 0; i++)
    esp_rom_delay_us(1);
  esp_rom_delay_us(STUB_HALF_US);
}

static RTC_IRAM_ATTR void stub_send_bit(uint32_t high) {
  if (high)
    stub_release(STUB_SDA);
  else
    stub_drive_low(STUB_SDA);
  esp_rom_delay_us(STUB_HALF_US);
  stub_clock_high();
  stub_drive_low(STUB_SCL);
}

static RTC_IRAM_ATTR uint32_t stub_take_bit(void) {
  stub_release(STUB_SDA);
  esp_rom_delay_us(STUB_HALF_US);
  stub_clock_high();
  const uint32_t level = stub_level(STUB_SDA);
  stub_drive_low(STUB_SCL);
  return level;
}

static RTC_IRAM_ATTR uint32_t stub_read_byte(uint32_t ack) {
  uint32_t value = 0;
  for (uint32_t bit = 0; bit < 8; bit++)
    value = (value << 1) | stub_take_bit();
  stub_send_bit(!ack);
  stub_release(STUB_SDA);
  return value;
}

static RTC_IRAM_ATTR void stub_stop(void) {
  stub_drive_low(STUB_SDA);
  esp_rom_delay_us(STUB_HALF_US);
  stub_clock_high();
  stub_release(STUB_SDA);
  esp_rom_delay_us(STUB_HALF_US);
}

// Output value 0 on both pins, so a set enable bit pulls the line low and a
// clear one leaves it to R4/R5.
static RTC_IRAM_ATTR void stub_pins_open(void) {
  const uint32_t both = (1u << STUB_SDA) | (1u << STUB_SCL);
  REG_WRITE(GPIO_ENABLE_W1TC_REG, both);
  REG_WRITE(GPIO_OUT_W1TC_REG, both);
  REG_WRITE(GPIO_FUNC22_OUT_SEL_CFG_REG, SIG_GPIO_OUT_IDX);
  REG_WRITE(GPIO_FUNC23_OUT_SEL_CFG_REG, SIG_GPIO_OUT_IDX);
  REG_WRITE(IO_MUX_GPIO22_REG, STUB_IOMUX_GPIO);
  REG_WRITE(IO_MUX_GPIO23_REG, STUB_IOMUX_GPIO);
}

static RTC_IRAM_ATTR void stub_stamp(void) {
  REG_SET_BIT(LP_TIMER_UPDATE_REG, LP_TIMER_MAIN_TIMER_UPDATE);
  idle_sleep_latch.lp_ticks_lo = REG_READ(LP_TIMER_MAIN_BUF0_LOW_REG);
  idle_sleep_latch.lp_ticks_hi = REG_READ(LP_TIMER_MAIN_BUF0_HIGH_REG) & LP_TIMER_MAIN_TIMER_BUF0_HIGH;
}

void RTC_IRAM_ATTR esp_wake_deep_sleep(void) {
  esp_default_wake_deep_sleep();

  idle_sleep_latch.cycles = esp_cpu_get_cycle_count();
  idle_sleep_latch.ticks_per_us = esp_rom_get_cpu_ticks_per_us();
  const uint32_t cause = esp_wake_stub_get_wakeup_cause();
  idle_sleep_latch.cause = cause;
  idle_sleep_latch.port = 0xFFFFu;

  if ((cause & (RTC_EXT1_TRIG_EN | RTC_GPIO_TRIG_EN)) == 0) {
    idle_sleep_latch.flags = IDLE_SLEEP_STUB_SKIPPED;
    stub_stamp();
    idle_sleep_latch.magic = IDLE_SLEEP_LATCH_MAGIC;
    return;
  }

  stub_pins_open();
  esp_rom_delay_us(STUB_HALF_US);

  // A device left mid-byte holds SDA. Nine clocks let it finish.
  for (uint32_t i = 0; i < 9 && stub_level(STUB_SDA) == 0; i++) {
    stub_drive_low(STUB_SCL);
    esp_rom_delay_us(STUB_HALF_US);
    stub_clock_high();
  }

  // START while SCL is high.
  stub_drive_low(STUB_SDA);
  esp_rom_delay_us(STUB_HALF_US);
  stub_drive_low(STUB_SCL);

  for (int bit = 7; bit >= 0; bit--)
    stub_send_bit((STUB_ADDR_READ >> bit) & 1u);
  const uint32_t acked = stub_take_bit() == 0;

  uint32_t flags = IDLE_SLEEP_STUB_READ;
  if (acked) {
    flags |= IDLE_SLEEP_STUB_ACK;
    const uint32_t low = stub_read_byte(1);
    const uint32_t high = stub_read_byte(0);
    idle_sleep_latch.port = low | (high << 8);
  }
  stub_stop();

  stub_release(STUB_SDA);
  stub_release(STUB_SCL);

  stub_stamp();
  idle_sleep_latch.flags = flags;
  idle_sleep_latch.magic = IDLE_SLEEP_LATCH_MAGIC;
}

#endif  // USE_IDLE_SLEEP_WAKE_STUB
