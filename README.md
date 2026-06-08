# Sigma Harmonics ROM Reverse Engineering & Translation Tools

This repository contains Python tools to reverse engineer the Japanese Nintendo DS ROM of *Sigma Harmonics* (Square Enix, 2008) and extract all its text contents (dialogue, menus, tutorials) into CSV files for translation.

---

## Suite of Tools

### 1. `nds_unpack.py`
Unpacks the standard Nintendo DS NitroROM filesystem from the `.nds` ROM file.
* **Usage**:
  ```bash
  python3 nds_unpack.py "path/to/game.nds" "unpacked_rom"
  ```
* **Extracted Files**:
  * `unpacked_rom/data/data.cpk` (~121.5 MB): Stores game assets.
  * `unpacked_rom/data/sound_data.sdat` (~4.9 MB): Stores audio.

### 2. `cpk_unpack.py`
Parses the CPK's `@UTF` table headers and ITOC layout, resolves the sequential file list, bypasses zeroed compression headers, decompresses CRILayla streams, and extracts all 8,652 files.
* **Requirements**: `pip3 install hacktools`
* **Usage**:
  ```bash
  python3 cpk_unpack.py "unpacked_rom/data/data.cpk" "extracted_cpk"
  ```

### 3. `text_scanner.py`
Scans all extracted `.bin` files to identify text encodings and search for Japanese characters.
* **Usage**:
  ```bash
  python3 text_scanner.py
  ```

### 4. `text_extractor.py`
Extracts and categorizes all text strings from files in `extracted_cpk/` and saves them to clean CSV files.
* **Usage**:
  ```bash
  python3 text_extractor.py
  ```
* **Output Files**:
  * `dialogue_story.csv` (513 rows): Scene dialogue and story lines.
  * `menu_ui.csv` (168 rows): Button text, options, character and God names.
  * `tutorials.csv` (124 rows): Battle mechanics and tutorial instructions.

---

## Findings Summary
1. **File Format**: The text files use two formats:
   * **Table-based format**: A pointer offset table at the beginning of the file mapping to null-terminated UTF-8 strings.
   * **Bytecode script format (`"Sigma000"`)**: Visual novel scripts containing bytecode at the start and dialogue strings at the end, interspersed with VN engine control codes.
2. **Encoding**: All text strings are encoded in standard **UTF-8**.
3. **Range**: Text files are strictly grouped in CPK file IDs between `4000` and `5600`.
