# Validation Rules

This document describes the 8 core validation rules enforced by the `aspen_automation` package. These rules ensure that plant specifications are internally consistent and compatible with Aspen Plus before any simulation is attempted.

## 1. Schema Structure

All mandatory top-level sections must be present in the specification file.

* **Trigger:** Missing `metadata`, `components`, `properties`, `flowsheet`, `streams`, or `blocks`.
* **Example Error Message:**

    ```text
    [ERROR] components
      Field required
      → Check the field 'components' for correct type or presence
    ```

## 2. Component References

Any component referenced in stream compositions or chemistry reactions must be explicitly defined in the `components` section.

* **Trigger:** Using a component ID like `H2O` in a stream without defining it in `components`.
* **Example Error Message:**

    ```text
    [ERROR] streams[0].composition.H2O
      Component 'H2O' used but not defined
      → Add component 'H2O' to components section
    ```

## 3. Stream Connectivity

Every stream name referenced as an input or output in the `flowsheet` section must have a corresponding definition in the `streams` section.

* **Trigger:** Flowsheet references stream `S1`, but only `FEED` and `PROD` are defined.
* **Example Error Message:**

    ```text
    [ERROR] flowsheet[0].inputs[0]
      Stream 'S1' referenced but not defined
      → Add stream 'S1' to streams section
    ```

## 4. Composition Validation

The sum of all component fractions in a stream's composition must equal 1.0 (within a tolerance of ±0.001).

* **Trigger:** `composition: {"CH4": 0.5, "CO2": 0.4}` (Sums to 0.9).
* **Example Error Message:**

    ```text
    [ERROR] streams[0].composition
      Value error, Composition sum is 0.9, expected 1.0 (±0.001)
      → Check the field 'streams[0].composition' for correct type or presence
    ```

## 5. Block References

Every block name referenced in the `flowsheet` section must have a corresponding definition in the `blocks` section.

* **Trigger:** Flowsheet references block `B1`, but the blocks section defines `MIXER1`.
* **Example Error Message:**

    ```text
    [ERROR] flowsheet[0].block
      Block 'B1' referenced but not defined
      → Add block 'B1' to blocks section
    ```

## 6. Unit Validation

Units for pressure, temperature, and flow must be chosen from the set of allowed Aspen Plus units.

* **Trigger:** Using `Kelvin` instead of `K` or `Pascals` instead of `kPa`.
* **Example Error Message:**

    ```text
    [ERROR] metadata.units.pressure
      Invalid unit 'Pascals' for pressure
      → Use one of: bar, psi, atm, kPa, MPa
    ```

## 7. Required Fields

Critical fields within each section must be provided. This includes identifiers, names, and physical conditions like temperature and pressure.

* **Trigger:** A stream definition missing the `pressure` field.
* **Example Error Message:**

    ```text
    [ERROR] streams[0].pressure
      Field required
      → Check the field 'streams[0].pressure' for correct type or presence
    ```

## 8. Type Validation

Values must match the expected data types defined in the schema (e.g., numbers for physical properties, strings for identifiers).

* **Trigger:** Providing `temperature: "hot"` instead of `80.0`.
* **Example Error Message:**

    ```text
    [ERROR] streams[0].temperature
      Input should be a valid number, unable to parse string as a number
      → Check the field 'streams[0].temperature' for correct type or presence
    ```

---

*Note: The package also performs advanced checks for duplicate IDs and required flow specifications (either mass or mole flow must be provided).*
