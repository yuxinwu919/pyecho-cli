function run_wrapper()
    cd('/Users/yuxinwu/my_projects/ECHO2D_CLI/tests/integration/results/matlab_outputs/_work/N16/ECHO2D');
    set(0,'DefaultFigureVisible','off');
    addpath('/Users/yuxinwu/my_projects/ECHO2D_CLI/ECHO2D_v3_5/MatLib4ECHO');
    W = load('WakeL_Tm_Tq_Td.txt');
    s = W(:,1); Wlong=W(:,2); Wm=W(:,3); Wquad=W(:,4); Wdipole=W(:,5);
    fprintf('VAL_n16_peakWlong=%.10g\n', max(abs(Wlong)));
    fprintf('VAL_n16_peakWm=%.10g\n', max(abs(Wm)));
    fprintf('VAL_n16_peakWquad=%.10g\n', max(abs(Wquad)));
    fprintf('VAL_n16_peakWdipole=%.10g\n', max(abs(Wdipole)));
    K = load('kick.txt');
    fprintf('VAL_n16_kick_max=%.10g\n', max(abs(K(:,2))));
    fprintf('VAL_n16_kick_min=%.10g\n', min(K(:,2)));
    fprintf('N16_COMPLETE\n');
end
