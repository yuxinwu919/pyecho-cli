function run_wrapper()
    cd('/Users/yuxinwu/my_projects/ECHO2D_CLI/tests/integration/results/matlab_outputs/_work/N13/PostProcessor2D/Round');
    set(0,'DefaultFigureVisible','off');
    addpath('/Users/yuxinwu/my_projects/ECHO2D_CLI/ECHO2D_v3_5/MatLib4ECHO');
    addpath(pwd);
    run('PP_Wake_Monopole.m');
    
    fprintf('VAL_mono_loss=%.10g\n', loss);
    fprintf('VAL_mono_spread=%.10g\n', spread);
    [~,~,pk] = LossShape([s B],[s W]);
    fprintf('VAL_mono_peak=%.10g\n', pk);
    run('PP_Wake_Dipole.m');
    
    fprintf('VAL_dipole_loss=%.10g\n', loss);
    fprintf('VAL_dipole_spread=%.10g\n', spread);
    fprintf('VAL_dipole_kick=%.10g\n', kick);
    fprintf('VAL_dipole_rms_kick=%.10g\n', rms_kick);
    [~,~,pk] = LossShape([s B],[s W]);
    fprintf('VAL_dipole_peak=%.10g\n', pk);
    fprintf('N13_COMPLETE\n');
end