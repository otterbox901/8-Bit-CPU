# 8-Bit CPU

A CPU built from ~97 individual 74HC-series logic ICs. Custom instruction set, microcoded control unit, and a from-scratch ALU with flag logic, laid out on a 4-layer PCB.

## Status: In progress

- [x] Instruction set architecture (11 instructions, custom encoding)
- [x] ALU design — adder/subtractor, bitwise AND/OR, Z/C/N flag generation
- [x] Register file (4 general-purpose registers) and microcoded control-ROM addressing scheme
- [x] PCB component placement — 97 ICs, board outline drawn (173.5 mm × 115.5 mm, 4-layer)
- [x] Microcode ROM generator — Python script producing control-ROM contents from the ISA/microcode design, checked against the control-unit addressing scheme
- [x] Emulator — Python simulator + assembler that executes `microcode_table.csv` directly, with the full ISA exercised by a bundled test program
- [x] Control unit — the schematic's control-ROM addressing, register-file/ALU
      enable logic, and memory control signals are now actually wired
- [x] PCB routing — fully autorouted (4-layer, 755 nets, 0 DRC errors)
- [ ] Power input connector + regulator (not yet designed — see Known Issues)
- [ ] HLT (clock/sequencer halt) — control-ROM signal exists but isn't wired
      to anything yet
- [ ] Burn control ROM onto physical EEPROMs and hardware bring-up

## Overview

| | |
|---|---|
| Data path | 8-bit |
| Registers | 4 general-purpose (R0–R3), plus PC, MAR, IR, and internal ALU staging registers |
| Control unit | Microcoded — control ROM addressed by opcode, execution step, and ALU status flags (no hardwired branch/decision logic) |
| ALU | Add, subtract (two's complement), AND, OR — with Zero, Carry, and Negative flags |
| Memory | Harvard-style — separate address space for program storage (EEPROM) and data storage (SRAM) |
| Clock target | 1–4 MHz |
| Logic family | 74HC/74LS discrete logic |
| IC count | ~97 |
| Board | 4-layer, 1.6 mm, 173.5 mm × 115.5 mm |

## Instruction Set

| Opcode | Mnemonic | Format | Operation |
|---|---|---|---|
| `0000` | `NOP` | — | No operation |
| `0001` | `LOAD Rd, addr` | Address (3 bytes) | Rd ← MEM[addr] |
| `0010` | `STORE Rd, addr` | Address (3 bytes) | MEM[addr] ← Rd |
| `0011` | `ADD Rd, Rs` | Reg-reg (1 byte) | Rd ← Rd + Rs |
| `0100` | `SUB Rd, Rs` | Reg-reg (1 byte) | Rd ← Rd − Rs |
| `0101` | `JMP addr` | Address (3 bytes) | PC ← addr |
| `0110` | `JZ addr` | Address (3 bytes) | PC ← addr if Zero flag set |
| `0111` | `JC addr` | Address (3 bytes) | PC ← addr if Carry flag set |
| `1000` | `MOV Rd, Rs` | Reg-reg (1 byte) | Rd ← Rs |
| `1001` | `AND Rd, Rs` | Reg-reg (1 byte) | Rd ← Rd AND Rs |
| `1010` | `OR Rd, Rs` | Reg-reg (1 byte) | Rd ← Rd OR Rs |
| `1111` | `HLT` | — | Stop the clock |

Opcodes `1011`–`1110` are reserved for future extension (e.g. a stack pointer with `CALL`/`RET`, or additional ALU operations). Currently they fetch and decode as a no-op.

Instructions are encoded as either one byte (reg-reg) or three bytes (address):

| Format | Byte 0 | Byte 1 | Byte 2 |
|---|---|---|---|
| Reg-reg | `[opcode:4][Rd:2][Rs:2]` | — | — |
| Address | `[opcode:4][Rd:2][--:2]` | addr low | addr high |

The 3-bit step counter cycles 0–7 (wrapping); step 0 is always the fetch (`IROM_OUT` + `IR_IN` + `PC_INC`), steps 1–3 execute the operand/operation, and any trailing steps are no-ops. Conditional jumps are resolved entirely by the control ROM's addressing (the flag bits are part of the ROM address), with no separate comparator logic needed.

## Control ROM

The control ROM is generated rather than hand-populated. A Python script (`microcode_rom_gen.py`) walks every `(opcode, step, Z, C)` combination — a 9-bit, 512-word address space, and derives the 20-bit control word for each from the microcode step tables for each instruction. The control word is split across three 28C256 EEPROMs (8 + 8 + 4 bits), and the script emits both a human-readable CSV (`microcode_table.csv`) and three raw 32 KB binary chip images (`rom1.bin`, `rom2.bin`, `rom3.bin`) ready to burn, with unused upper addresses zero-padded to an all-signals-off state.

## Emulator

`emulator.py` is a cycle-accurate Python model of the CPU driven entirely by the generated control ROM. It arbitrates the 8-bit bus, latches registers and flags per the microcode control signals, and assembles + runs programs, so it can be used to develop and verify software before the hardware comes up.

### Usage

```bash
# Generate the control ROM table first (run from ROM/)
python3 microcode_rom_gen.py

# Run the full instruction-set test program (7/7 checks pass)
python3 emulator.py test_program.asm

# Run the bundled default test (no file argument)
python3 emulator.py

# Per-micro-step trace of bus, registers, and control signals
python3 emulator.py test_program.asm --trace-micro

# Quiet mode — suppress trace, show results only
python3 emulator.py -q test_program.asm
```

The built-in two-pass assembler understands the instruction mnemonics, labels, hex/decimal numbers, `.byte` (program ROM data) and `.ram addr, val` (pre-loads the data SRAM) directives. `test_program.asm` exercises every instruction — LOAD, STORE, ADD, SUB, AND, OR, MOV, NOP, JMP, JZ, JC, HLT — and auto-verifies the resulting data RAM contents against expected values.

## Repo Contents

```
8-Bit-CPU/
├── 8-bit cpu.kicad_sch     KiCad schematic (single flat sheet)
├── 8-bit cpu.kicad_pcb     KiCad PCB layout (routed, 0 DRC errors)
├── microcode_rom_gen.py    Control ROM generator (opcode/step/flags → EEPROM images)
├── emulator.py             Microcode-driven CPU emulator + assembler
├── test_program.asm        Full instruction-set test for the emulator
└── README.md
```

## Known Issues

- **No power input connector or regulator.** All 63 live ICs now share a
  single, correctly-named `+5V` net, but nothing in the schematic actually
  sources it — there's no barrel jack/header and no regulator IC modeled.
  This needs to be designed and added before the board can be powered.
- **HLT isn't wired to anything.** The control ROM correctly asserts the
  `HLT` signal per the microcode, but no hardware currently reads it (no
  clock-gating or sequencer-halt logic exists). Without it, a running CPU
  won't literally stop on `HLT` — it'll keep re-fetching the same
  instruction harmlessly forever rather than actually halting.
- **Cosmetic-only DRC/ERC output remains**: ~55 silkscreen text/outline
  overlaps among tightly-packed passives, and footprint-library-name
  mismatches (PCB footprints reference a `fasteda` library not present in
  every environment — the footprint geometry is embedded in the file
  regardless, so this doesn't affect fabrication).
- None of this has been verified against real hardware yet — see Roadmap.

## Roadmap

1. Design and add a power input connector + regulator
2. Wire HLT to a sequencer-halt/clock-gate
3. Burn the generated control ROM contents onto the EEPROMs
4. Bring-up and testing
5. Print and test on physical hardware
