import csv

EEPROM1_BITS = ["IROM_OUT", "RAM_OUT", "RAM_IN", "IR_IN",
                "MAR_LOW_IN", "MAR_HIGH_IN", "PC_INC", "PC_LOAD"]
EEPROM2_BITS = ["RS_SEL", "REG_IN", "REG_OUT", "A_IN",
                "TEMP_IN", "ALU_SEL0", "ALU_SEL1", "SU"]
EEPROM3_BITS = ["EO", "FI_ZN", "FI_C", "HLT"]  # only 4 bits used
ALL_BIT_TABLES = [EEPROM1_BITS, EEPROM2_BITS, EEPROM3_BITS]


RS_RD = ()                 # RS_SEL absent -> decoder reads Rd field
RS_RS = ("RS_SEL",)        # RS_SEL present -> decoder reads Rs field
def alu_sel(value):
    bits = []
    if value & 0b01:
        bits.append("ALU_SEL0")
    if value & 0b10:
        bits.append("ALU_SEL1")
    return tuple(bits)
SEL_SUM  = alu_sel(0b00)   # adder result (ADD uses SU=0, SUB uses SU=1)
SEL_AND  = alu_sel(0b01)
SEL_OR   = alu_sel(0b10)
SEL_PASS = alu_sel(0b11)   # pass-through of B/TEMP (used by MOV)
FETCH            = ("IROM_OUT", "IR_IN", "PC_INC")
FETCH_ADDR_LOW   = ("IROM_OUT", "MAR_LOW_IN", "PC_INC")
FETCH_ADDR_HIGH  = ("IROM_OUT", "MAR_HIGH_IN", "PC_INC")

OPCODES = {
    0b0000: "NOP",   0b0001: "LOAD",  0b0010: "STORE", 0b0011: "ADD",
    0b0100: "SUB",   0b0101: "JMP",   0b0110: "JZ",    0b0111: "JC",
    0b1000: "MOV",   0b1001: "AND",   0b1010: "OR",    0b1111: "HLT",
}
def build_steps(mnemonic, z, c):
    """Return a list of signal-tuples, one per micro-step (index 0-3 used)."""
    if mnemonic is None:                       # reserved/undefined opcode
        return [FETCH]                         # behaves as NOP -- see MICROCODE.md
    if mnemonic == "NOP":
        return [FETCH]
    if mnemonic == "HLT":
        return [FETCH, ("HLT",)]
    if mnemonic == "MOV":
        step1 = RS_RS + ("REG_OUT", "TEMP_IN")
        step2 = RS_RD + ("EO", "REG_IN") + SEL_PASS
        return [FETCH, step1, step2]
    if mnemonic in ("ADD", "SUB", "AND", "OR"):
        step1 = RS_RD + ("REG_OUT", "A_IN")
        step2 = RS_RS + ("REG_OUT", "TEMP_IN")
        if mnemonic == "ADD":
            step3 = RS_RD + ("EO", "REG_IN", "FI_ZN", "FI_C") + SEL_SUM
        elif mnemonic == "SUB":
            step3 = RS_RD + ("EO", "REG_IN", "FI_ZN", "FI_C", "SU") + SEL_SUM
        elif mnemonic == "AND":
            step3 = RS_RD + ("EO", "REG_IN", "FI_ZN") + SEL_AND
        else:  # OR
            step3 = RS_RD + ("EO", "REG_IN", "FI_ZN") + SEL_OR
        return [FETCH, step1, step2, step3]
    if mnemonic in ("LOAD", "STORE", "JMP", "JZ", "JC"):
        if mnemonic == "LOAD":
            step3 = RS_RD + ("RAM_OUT", "REG_IN")
        elif mnemonic == "STORE":
            step3 = RS_RD + ("REG_OUT", "RAM_IN")
        elif mnemonic == "JMP":
            step3 = ("PC_LOAD",)
        elif mnemonic == "JZ":
            step3 = ("PC_LOAD",) if z else ()
        else:  # JC
            step3 = ("PC_LOAD",) if c else ()
        return [FETCH, FETCH_ADDR_LOW, FETCH_ADDR_HIGH, step3]
    raise ValueError(f"unhandled mnemonic {mnemonic}")
def signals_to_bytes(signals):
    """Convert a set/tuple of asserted signal names into the 3 ROM bytes."""
    active = set(signals)
    out_bytes = []
    for table in ALL_BIT_TABLES:
        byte = 0
        for i, name in enumerate(table):
            if name in active:
                byte |= (1 << i)
        out_bytes.append(byte)
    return out_bytes  # [eeprom1_byte, eeprom2_byte, eeprom3_byte]
def generate():
    rows = []
    for opcode in range(16):
        mnemonic = OPCODES.get(opcode)
        for step in range(8):
            for flags in range(4):
                z = (flags >> 1) & 1
                c = flags & 1
                steps = build_steps(mnemonic, z, c)
                sig = steps[step] if step < len(steps) else ()
                b1, b2, b3 = signals_to_bytes(sig)
                addr = (opcode << 5) | (step << 2) | (z << 1) | c
                rows.append({
                    "address": addr,
                    "opcode_bin": format(opcode, "04b"),
                    "mnemonic": mnemonic or "(reserved)",
                    "step": step,
                    "Z": z, "C": c,
                    "signals": "+".join(sig) if sig else "(none)",
                    "rom1_hex": format(b1, "02X"),
                    "rom2_hex": format(b2, "02X"),
                    "rom3_hex": format(b3, "02X"),
                })
    return rows
def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
def write_bin_images(rows, out_prefix, chip_size=32768):
    """Write 3 chip_size-byte binary images, one per EEPROM.
    Only addresses 0-511 are meaningful; everything above is zero-padded
    (all control signals off / safe no-op state)."""
    images = [bytearray(chip_size) for _ in range(3)]
    for row in rows:
        addr = row["address"]
        images[0][addr] = int(row["rom1_hex"], 16)
        images[1][addr] = int(row["rom2_hex"], 16)
        images[2][addr] = int(row["rom3_hex"], 16)
    for i, img in enumerate(images, start=1):
        with open(f"{out_prefix}{i}.bin", "wb") as f:
            f.write(img)
if __name__ == "__main__":
    rows = generate()
    write_csv(rows, "microcode_table.csv")
    write_bin_images(rows, "rom")
    print(f"Generated {len(rows)} address rows.")
    print("Wrote microcode_table.csv, rom1.bin, rom2.bin, rom3.bin")
