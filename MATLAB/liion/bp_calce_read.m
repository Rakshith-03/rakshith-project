function D = bp_calce_read(file)
%BP_CALCE_READ Read a CALCE Arbin export into t_s, step, V, I_A (+ = charge). The CALCE .xls files are xlsx inside.
tmp = [tempname '.xlsx'];
copyfile(file, tmp); cleanup = onCleanup(@() delete(tmp));
sh = sheetnames(tmp); sh = sh(startsWith(sh, "Channel"));
assert(~isempty(sh), "No Channel_* sheet in %s", file);
C = cell(numel(sh), 1);
for k = 1:numel(sh), C{k} = readtable(tmp, 'Sheet', sh(k), 'VariableNamingRule', 'preserve'); end
T = vertcat(C{:});
D = table(T.("Test_Time(s)"), T.Step_Index, T.("Voltage(V)"), T.("Current(A)"), ...
    'VariableNames', ["t_s", "step", "V", "I_A"]);
end
