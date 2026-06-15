# Where Aspen Stores Databank Binary Parameters (SQL Server LocalDB)

When the COM engine can't retrieve a databank parameter
(see [com-under-appsanywhere.md](com-under-appsanywhere.md)) and you need to know what the
"real" value is, the databank itself is a local SQL Server LocalDB database. This note
documents its structure so you can **read** it to confirm provenance.

> **DRM boundary — do not cross.** The numeric `cValue` cells are AES-encrypted (16-byte
> blocks) under Aspen's DRM. **Do not reverse-engineer or attempt to decrypt them.** Use
> this database to confirm *structure and provenance* (which databank, which pair, how
> many parameters). To recover the actual numeric values, use the sanctioned
> activity-coefficient calibration in
> [binary-parameter-calibration.md](binary-parameter-calibration.md), which reads γ that
> Aspen's own batch engine computes from the decrypted parameters.

## Locating the instance

- LocalDB binary: `SqlLocalDB.exe`, typically under
  `C:\Program Files\Microsoft SQL Server\150\Tools\Binn`.
- Instance name: **`AspenInstance40`**
- Connect read-only via ODBC Driver 17, server `(localdb)\AspenInstance40`.
- Database: **`APV140`** (matches the Aspen Plus V14 / APV140 databank version).

```powershell
& "C:\Program Files\Microsoft SQL Server\150\Tools\Binn\SqlLocalDB.exe" info
& "C:\Program Files\Microsoft SQL Server\150\Tools\Binn\SqlLocalDB.exe" info AspenInstance40
```

## Schema map

**Table `CompoundsBinaryNumericProperties`** holds binary interaction parameters:

| Column            | Meaning                                                    |
| ----------------- | ---------------------------------------------------------- |
| `databankIndex`   | which databank (e.g. VLE-IG)                               |
| `compound1Index`  | first compound id (directional: 1→2)                       |
| `compound2Index`  | second compound id                                         |
| `propertyName`    | model name (e.g. NRTL)                                     |
| `cIndex`          | element slot within the parameter block                    |
| `cValue`          | the value — **AES-encrypted (DRM), do not decrypt**        |

**Resolving compound ids** — table `CompoundIdentifiers`, identifier `identifierId 4`
is the CASRN. For methanol–water:

- methanol (CH3OH) = `compoundId 526`
- water (H2O)      = `compoundId 1188`

**Resolving databank ids** — VLE-IG = `databankId 33`.

## NRTL pair layout

For the methanol–water NRTL pair in VLE-IG there are **12 rows**, `cIndex 1410–1421`, in
this element order:

```
[aij, aji, bij, bji, cij, dij, eij, eji, fij, fji, Tlower, Tupper]
```

Note the alternating directional pairing (`aij, aji, bij, bji, …`) and the trailing
temperature limits. This matches the Aspen NRTL form
`τ_ij = a_ij + b_ij/T + e_ij·lnT + f_ij·T`, `α_ij = c_ij + d_ij·(T − 273.15)`.

## How to use this safely

1. Connect read-only and confirm the pair exists and how many elements it has.
2. Map element order so you know which slots a calibration must reproduce.
3. **Recover the numbers** via calibration, not decryption — see
   [binary-parameter-calibration.md](binary-parameter-calibration.md).
4. Emit them with the directional BPVAL form in
   [nrtl-bpval-syntax.md](nrtl-bpval-syntax.md).
