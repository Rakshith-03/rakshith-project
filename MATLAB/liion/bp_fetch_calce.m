function bp_fetch_calce(raw)
%BP_FETCH_CALCE Download the CALCE INR18650-20R 25 C files once into RAW (openly published by CALCE, UMD - cite CALCE).
% Originals are kept as downloaded (zips/) and extracted next to them (extracted/); nothing is modified afterwards.
base = "https://web.calce.umd.edu/batteries/data/";
z = ["SP1_25C_LC_OCV_11_5_2015", "SP3_25C_LC_OCV_11_16_2015", "SP2_Initial_capacity_10_16_2015", ...
     "SP2_25C_DST", "SP2_25C_FUDS", "SP2_25C_US06", "SP2_25C_BJDST"] + ".zip";
if ~isfolder(fullfile(raw, "zips")), mkdir(fullfile(raw, "zips")); end
for k = 1:numel(z)
    zf = fullfile(raw, "zips", z(k));
    if ~isfile(zf), websave(zf, base + z(k)); end
    out = fullfile(raw, "extracted", erase(z(k), ".zip"));
    if ~isfolder(out), unzip(zf, out); end
end
end
