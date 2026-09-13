# IASS 2026 Workshop — Second Lives

Materials for the IASS 2026 "Second Lives" workshop on reuse potential and embodied
carbon savings of salvaged structural elements.

## Repository layout

```
wokshop-day/
  wokshop-day/
    data/
      harmonized_source_A_gsr_reno_hss.csv        # Source A — GSR renovation, HSS steel
      harmonized_source_B_cambridge_pavilion.csv  # Source B — Cambridge pavilion
```

## Data schema

Both CSVs share a harmonized schema, one row per structural element:

| Column | Description |
| --- | --- |
| `element_id` | Identifier of the element in its source model |
| `source` | Donor project the element comes from |
| `material_type` | Material class (e.g. `Steel`) |
| `section_or_species` | Section designation for steel, or timber species |
| `length_ft` | Total element length, in feet |
| `reusable_length_ft` | Length judged recoverable for reuse, in feet |
| `mass_kg` | Element mass, in kilograms |
| `percent_reusable` | `reusable_length_ft` as a fraction of `length_ft` |
| `embodied_carbon_savings_kgco2e` | Avoided embodied carbon from reuse, in kg CO2e |

Fields are left blank where the source model did not provide a value. Source B uses
`#NotDesigned` in `section_or_species` for elements without a resolved section.
