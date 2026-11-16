#pragma once

#include <cstddef>
#include <cstdint>

// Names of stored IR codes. This header has no ESPHome includes, so a host
// compiler can test the rules that the web page and the firmware share.
namespace ir_name {

// Bytes of a stored name, without the terminator.
static constexpr size_t MAX = 23;
static constexpr unsigned FIRST_SLOT = 3;
static constexpr unsigned LAST_SLOT = 20;

// The bytes that IrCodeStore::set_name() keeps. The page prints a name into
// JSON and the code block without an escape, so a quote and a backslash go.
inline bool keeps(char value) { return value >= 0x20 && value <= 0x7E && value != '"' && value != '\\'; }

// True when set_name() stores the text unchanged and the code block reads it
// back the same. The parser trims the value of a name line, so an end space is out.
inline bool fits(const char *text, size_t length) {
  if (length > MAX)
    return false;
  if (length > 0 && (text[0] == ' ' || text[length - 1] == ' '))
    return false;
  for (size_t i = 0; i < length; i++) {
    if (!keeps(text[i]))
      return false;
  }
  return true;
}

// The code block must carry a name line to stay a valid Flipper signal, so a
// code with no name prints "Slot<n>". Any slot number counts, because a copy
// can carry the placeholder of another input.
inline bool placeholder(const char *text, size_t length) {
  if (length < 5 || length > 6 || text[0] != 'S' || text[1] != 'l' || text[2] != 'o' || text[3] != 't')
    return false;
  if (text[4] == '0')
    return false;
  unsigned value = 0;
  for (size_t i = 4; i < length; i++) {
    if (text[i] < '0' || text[i] > '9')
      return false;
    value = value * 10 + static_cast<unsigned>(text[i] - '0');
  }
  return value >= FIRST_SLOT && value <= LAST_SLOT;
}

}  // namespace ir_name
