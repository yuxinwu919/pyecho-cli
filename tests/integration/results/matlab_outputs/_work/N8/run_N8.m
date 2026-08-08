function run_wrapper()
    cd('/Users/yuxinwu/my_projects/ECHO2D_CLI/tests/integration/results/matlab_outputs/_work/N8/PostProcessor2D/Flat');
    set(0,'DefaultFigureVisible','off');
    addpath('/Users/yuxinwu/my_projects/ECHO2D_CLI/ECHO2D_v3_5/MatLib4ECHO');
    addpath(pwd);
    run('PP_Wcc.m');
    run('PP_WakeLQ.m');
    
    fprintf('VAL_wake_lossL=%.10g\n', lossL);
    fprintf('VAL_wake_spreadL=%.10g\n', spreadL);
    fprintf('VAL_wake_lossQ=%.10g\n', lossQ);
    fprintf('VAL_wake_spreadQ=%.10g\n', spreadQ);
    fprintf('N8_COMPLETE\n');
end