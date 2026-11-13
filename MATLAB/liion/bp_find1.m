function p = bp_find1(root, pat)
%BP_FIND1 Path of the single file under ROOT (recursive) matching PAT; errors if there are zero or several matches.
d = dir(fullfile(root, "**", pat));
assert(numel(d) == 1, "Expected one file for %s, found %d", pat, numel(d));
p = fullfile(d.folder, d.name);
end
