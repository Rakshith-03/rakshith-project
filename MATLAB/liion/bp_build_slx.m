function mdl = bp_build_slx(folder)
%BP_BUILD_SLX Build MULTI_CHEMISTRY_BATTERY_LAB.slx from standard Simulink blocks.
%   I_total = I_in (From Workspace, ZOH) + Current_Generator (pulse train + ripple)      [A, discharge positive]
%   LiIon_ECM: dz/dt = -I/(3600Q); dv_i/dt = (R_i I - v_i)/tau_i; dh/dt = -|I| gamma/(3600Q) (h + sign I)
%              V = OCV(z) + M h - R0 I - v1 - v2
%   Thermal (PROVISIONAL): C_th dT/dt = Q - (T - T_amb)/R_th,  Q = I (R0 I + v1 + v2)  (ohmic + polarisation; no entropic heat)
%   Generator: pulse  = gate_p(t) [I_base + (I_pulse - I_base) P(t)]     (I_pulse is the total current during a pulse)
%              ripple = gate_r(t) [I_dc + I_rip sin(2 pi f (t - t_r0))]   (both enable flags multiply; outputs add)
% All parameters come from the workspace struct P (see bp_liion_params). Top-level outputs: V_t, SOC, h, I, T, Q_gen.
mdl = 'MULTI_CHEMISTRY_BATTERY_LAB';
if bdIsLoaded(mdl), close_system(mdl, 0); end
new_system(mdl);
set_param(mdl, 'Solver', 'ode23t', 'RelTol', '1e-7', 'AbsTol', '1e-9', 'MaxStep', 'P.max_step', ...
    'SaveOutput', 'on', 'OutputSaveName', 'yout', 'SaveFormat', 'Dataset', 'SaveTime', 'off', ...
    'OutputOption', 'SpecifiedOutputTimes', 'OutputTimes', 't_out', ...
    'Description', ['Li-ion INR18650-20R ECM (2RC + hysteresis, validated on CALCE drive cycles) + current generator + ' ...
                    'PROVISIONAL lumped thermal model. Other subsystems not built yet.']);

add_block('simulink/Sources/From Workspace', [mdl '/Current_Profile'], 'VariableName', 'I_in', ...
    'Interpolate', 'off', 'ZeroCross', 'on', 'OutputAfterFinalValue', 'Holding final value');
build_generator([mdl '/Current_Generator']);
build_ecm([mdl '/LiIon_ECM']);
build_thermal([mdl '/Thermal_Model']);
add_block('simulink/Math Operations/Sum', [mdl '/I_total'], 'Inputs', '++');
outs = ["V_t" "SOC" "h" "I" "T" "Q_gen"];
for o = outs, add_block('simulink/Sinks/Out1', char(mdl + "/" + o)); end
L = @(a, b) add_line(mdl, a, b, 'autorouting', 'on');
L('Current_Profile/1', 'I_total/1'); L('Current_Generator/1', 'I_total/2');
L('I_total/1', 'LiIon_ECM/1'); L('I_total/1', 'Thermal_Model/1'); L('I_total/1', 'I/1');
L('LiIon_ECM/4', 'Thermal_Model/2'); L('LiIon_ECM/5', 'Thermal_Model/3');
L('LiIon_ECM/1', 'V_t/1'); L('LiIon_ECM/2', 'SOC/1'); L('LiIon_ECM/3', 'h/1');
L('Thermal_Model/1', 'T/1'); L('Thermal_Model/2', 'Q_gen/1');
Simulink.BlockDiagram.arrangeSystem(mdl);
save_system(mdl, fullfile(folder, [mdl '.slx']));
end

function build_ecm(s)
add_block('built-in/Subsystem', s);
B = @(name, lib, varargin) add_block(lib, [s '/' name], varargin{:});
B('I_dis_A', 'simulink/Sources/In1');
B('kSOC', 'simulink/Math Operations/Gain', 'Gain', '-1/(3600*P.Q)');
B('SOC_int', 'simulink/Continuous/Integrator', 'InitialCondition', 'P.z0');
B('OCV', 'simulink/Lookup Tables/1-D Lookup Table', 'Table', 'P.ocv_tab', ...
    'BreakpointsForDimension1', 'P.soc_bp', 'ExtrapMethod', 'Clip');
B('R0', 'simulink/Math Operations/Gain', 'Gain', 'P.R0');
for k = 1:2
    n = num2str(k);
    B(['R' n], 'simulink/Math Operations/Gain', 'Gain', ['P.R' n]);
    B(['e' n], 'simulink/Math Operations/Sum', 'Inputs', '+-');
    B(['inv_tau' n], 'simulink/Math Operations/Gain', 'Gain', ['1/P.tau' n]);
    B(['v' n], 'simulink/Continuous/Integrator', 'InitialCondition', '0');
end
B('absI', 'simulink/Math Operations/Abs');
B('kH', 'simulink/Math Operations/Gain', 'Gain', 'P.gam/(3600*P.Q)');
B('sgnI', 'simulink/Math Operations/Sign');
B('h_plus_sgn', 'simulink/Math Operations/Sum', 'Inputs', '++');
B('rate', 'simulink/Math Operations/Product', 'Inputs', '**');
B('neg', 'simulink/Math Operations/Gain', 'Gain', '-1');
B('h_int', 'simulink/Continuous/Integrator', 'InitialCondition', 'P.h0');
B('M', 'simulink/Math Operations/Gain', 'Gain', 'P.M');
B('Vt', 'simulink/Math Operations/Sum', 'Inputs', '++---');
for o = ["V_t" "SOC" "h" "v1_out" "v2_out"], B(char(o), 'simulink/Sinks/Out1'); end
L = @(a, b) add_line(s, a, b, 'autorouting', 'on');
for dst = ["kSOC/1", "R0/1", "R1/1", "R2/1", "absI/1", "sgnI/1"], L('I_dis_A/1', char(dst)); end
L('kSOC/1', 'SOC_int/1'); L('SOC_int/1', 'OCV/1'); L('SOC_int/1', 'SOC/1');
for k = 1:2
    n = num2str(k);
    L(['R' n '/1'], ['e' n '/1']); L(['v' n '/1'], ['e' n '/2']);
    L(['e' n '/1'], ['inv_tau' n '/1']); L(['inv_tau' n '/1'], ['v' n '/1']);
    L(['v' n '/1'], ['v' n '_out/1']);
end
L('absI/1', 'kH/1'); L('kH/1', 'rate/1');
L('h_int/1', 'h_plus_sgn/1'); L('sgnI/1', 'h_plus_sgn/2'); L('h_plus_sgn/1', 'rate/2');
L('rate/1', 'neg/1'); L('neg/1', 'h_int/1'); L('h_int/1', 'M/1'); L('h_int/1', 'h/1');
L('OCV/1', 'Vt/1'); L('M/1', 'Vt/2'); L('R0/1', 'Vt/3'); L('v1/1', 'Vt/4'); L('v2/1', 'Vt/5');
L('Vt/1', 'V_t/1');
Simulink.BlockDiagram.arrangeSystem(s);
end

function build_thermal(s)
add_block('built-in/Subsystem', s);
B = @(name, lib, varargin) add_block(lib, [s '/' name], varargin{:});
B('I', 'simulink/Sources/In1'); B('v1', 'simulink/Sources/In1'); B('v2', 'simulink/Sources/In1');
B('R0I', 'simulink/Math Operations/Gain', 'Gain', 'P.R0');
B('drop', 'simulink/Math Operations/Sum', 'Inputs', '+++');
B('Qgen', 'simulink/Math Operations/Product', 'Inputs', '**');
B('Tamb', 'simulink/Sources/Constant', 'Value', 'P.th.Tamb');
B('dT', 'simulink/Math Operations/Sum', 'Inputs', '+-');
B('loss', 'simulink/Math Operations/Gain', 'Gain', '1/P.th.Rth');
B('net', 'simulink/Math Operations/Sum', 'Inputs', '+-');
B('invC', 'simulink/Math Operations/Gain', 'Gain', '1/P.th.Cth');
B('T_int', 'simulink/Continuous/Integrator', 'InitialCondition', 'P.th.T0');
B('T_C', 'simulink/Sinks/Out1'); B('Q_W', 'simulink/Sinks/Out1');
L = @(a, b) add_line(s, a, b, 'autorouting', 'on');
L('I/1', 'R0I/1'); L('R0I/1', 'drop/1'); L('v1/1', 'drop/2'); L('v2/1', 'drop/3');
L('I/1', 'Qgen/1'); L('drop/1', 'Qgen/2');
L('T_int/1', 'dT/1'); L('Tamb/1', 'dT/2'); L('dT/1', 'loss/1');
L('Qgen/1', 'net/1'); L('loss/1', 'net/2'); L('net/1', 'invC/1'); L('invC/1', 'T_int/1');
L('T_int/1', 'T_C/1'); L('Qgen/1', 'Q_W/1');
Simulink.BlockDiagram.arrangeSystem(s);
end

function build_generator(s)
add_block('built-in/Subsystem', s);
B = @(name, lib, varargin) add_block(lib, [s '/' name], varargin{:});
L = @(a, b) add_line(s, a, b, 'autorouting', 'on');
B('clk', 'simulink/Sources/Clock');
% pulse train
B('pulse', 'simulink/Sources/Pulse Generator', 'PulseType', 'Time based', 'Amplitude', '1', ...
    'Period', 'P.gen.p_interval', 'PulseWidth', '100*P.gen.p_dur/P.gen.p_interval', 'PhaseDelay', 'P.gen.p_start');
B('dI', 'simulink/Math Operations/Gain', 'Gain', '(P.gen.p_pulse - P.gen.p_base)');
B('Ibase', 'simulink/Sources/Constant', 'Value', 'P.gen.p_base');
B('p_sum', 'simulink/Math Operations/Sum', 'Inputs', '++');
gate(s, 'p', 'P.gen.p_start', 'P.gen.p_stop');
B('p_out', 'simulink/Math Operations/Product', 'Inputs', '**');
B('p_on', 'simulink/Math Operations/Gain', 'Gain', 'P.gen.p_on');
L('pulse/1', 'dI/1'); L('dI/1', 'p_sum/1'); L('Ibase/1', 'p_sum/2');
L('p_sum/1', 'p_out/1'); L('p_gate/1', 'p_out/2'); L('p_out/1', 'p_on/1');
% ripple
B('sine', 'simulink/Sources/Sine Wave', 'SineType', 'Time based', 'Amplitude', 'P.gen.r_amp', 'Bias', 'P.gen.r_dc', ...
    'Frequency', '2*pi*P.gen.r_freq', 'Phase', '-2*pi*P.gen.r_freq*P.gen.r_start', 'SampleTime', '0');
gate(s, 'r', 'P.gen.r_start', 'P.gen.r_stop');
B('r_out', 'simulink/Math Operations/Product', 'Inputs', '**');
B('r_on', 'simulink/Math Operations/Gain', 'Gain', 'P.gen.r_on');
L('sine/1', 'r_out/1'); L('r_gate/1', 'r_out/2'); L('r_out/1', 'r_on/1');
B('I_gen', 'simulink/Math Operations/Sum', 'Inputs', '++');
B('I_gen_A', 'simulink/Sinks/Out1');
L('p_on/1', 'I_gen/1'); L('r_on/1', 'I_gen/2'); L('I_gen/1', 'I_gen_A/1');
Simulink.BlockDiagram.arrangeSystem(s);
end

function gate(s, x, t0, t1)
% <x>_gate = double(t >= t0 && t < t1), driven by the subsystem's clock 'clk'
B = @(name, lib, varargin) add_block(lib, [s '/' x '_' name], varargin{:});
B('t0', 'simulink/Sources/Constant', 'Value', t0);
B('t1', 'simulink/Sources/Constant', 'Value', t1);
B('ge', 'simulink/Logic and Bit Operations/Relational Operator', 'Operator', '>=');
B('lt', 'simulink/Logic and Bit Operations/Relational Operator', 'Operator', '<');
B('and', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND');
B('gate', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', 'double');
L = @(a, b) add_line(s, a, b, 'autorouting', 'on');
L('clk/1', [x '_ge/1']); L([x '_t0/1'], [x '_ge/2']);
L('clk/1', [x '_lt/1']); L([x '_t1/1'], [x '_lt/2']);
L([x '_ge/1'], [x '_and/1']); L([x '_lt/1'], [x '_and/2']); L([x '_and/1'], [x '_gate/1']);
end
