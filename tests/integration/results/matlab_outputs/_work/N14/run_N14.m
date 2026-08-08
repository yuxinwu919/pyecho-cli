function run_wrapper()
    cd('/Users/yuxinwu/my_projects/ECHO2D_CLI/tests/integration/results/matlab_outputs/_work/N14/PostProcessor2D/Round');
    set(0,'DefaultFigureVisible','off');
    addpath('/Users/yuxinwu/my_projects/ECHO2D_CLI/ECHO2D_v3_5/MatLib4ECHO');
    addpath(pwd);
    run('PP_Wake_Monopole.m');
    
    fprintf('VAL_mono_loss=%.10g\n', loss);
    fprintf('VAL_mono_spread=%.10g\n', spread);
    [~,~,pk] = LossShape([s B],[s W]);
    fprintf('VAL_mono_peak=%.10g\n', pk);
    fprintf('N14_COMPLETE\n');
end