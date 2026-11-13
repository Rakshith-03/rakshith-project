# CALCE INR18650-20R: raw reference data provenance
- Source: CALCE Battery Research Group, University of Maryland, https://calce.umd.edu/battery-data (INR 18650-20R section)
- Downloaded: 2026-11-12, with the user's permission, from https://web.calce.umd.edu/batteries/data/<file>
- Terms: the page describes the data as openly accessible and asks that publications cite the CALCE articles describing the experiments. No licence is named.
- Cell specs stated on the CALCE page: 2000 mAh rated, LiNiMnCo/graphite, 45 g, 18.33 x 64.85 mm. Manufacturer not stated on the page (Samsung per the cell designation; UNVERIFIED from the source).
- Originals are in `zips/` (unchanged). `extracted/` is a straight unzip. The `.xls` files are xlsx inside.
- `SP1_25C_IC_OCV_12_2_2015.zip` is linked on the page but returned HTTP 404.

| File | Bytes | SHA-256 |
|---|---|---|
| SP1_25C_LC_OCV_11_5_2015.zip | 3015812 | 18f7acb1cf74ac18d13102122404f800ed6888f262dce6eb0a49423509a7fb44 |
| SP2_25C_BJDST.zip | 3005609 | df372646a75f495186a58c3f549baecf86e70e0478bf55a97e122bab10f5bf21 |
| SP2_25C_DST.zip | 3189603 | 3d3a90a67574c336eca9d097a5f139aaad70e7fa3106078079da9cd11d1b3661 |
| SP2_25C_FUDS.zip | 3426587 | e2ce8e4626c4263cb8758c9488cec66d31c04a9d11465c14e668428cead1e053 |
| SP2_25C_US06.zip | 3372078 | cedf99281bad6c1f17a879d614f867451cf5994bad0f66d30c56290c1f6bb3fb |
| SP2_Initial_capacity_10_16_2015.zip | 3146319 | d18f9a958e2dabcaef9999bb42e8043ea5092b5d0c557966d92e4ad675d95c9d |
| SP3_25C_LC_OCV_11_16_2015.zip | 11486330 | 0bae869bba13c2d87faa3ae948557c47e5b4be96b93ee45970e571bfc63d58b7 |

## Test structure (SP2 drive cycles, all 25 C, about 1 s sampling in cycles, no temperature channel)
Steps: 1 rest, 2 CC charge 1 A to 4.2 V, 3 CV to 20 mA, 4 rest, 5 1C discharge to the start SOC (0.4 Ah -> 80 %, 1.0 Ah -> 50 %),
6 rest (2 h for DST/FUDS, none for US06/BJDST), 7/8 repeated drive-cycle segments to 2.5 V.
Currents: DST/FUDS -4 to +2 A, US06 -4 to +0.86 A, BJDST -1.67 to +0.44 A (+ = charge).
SP2 1C capacity test: 2.028 Ah. Timestamps: SP1 has 5 and SP3 has 1 duplicated timestamp (dt = 0, near-identical samples); harmless.
