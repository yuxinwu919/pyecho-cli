function [L_log_exists] = Astra_log_exists(folder)
% check if Astra folder solved
global pltfrm

type_cmn=pltfrm{1};   copy_cmn=pltfrm{2};  move_cmn=pltfrm{3};
mkdir_cmn=pltfrm{4};  dir_cmn=pltfrm{5};   del_cmn=pltfrm{6};

[status result]=system([dir_cmn ' ' folder]);
if ~(status==0)
   L_log_exists=false; 
else
   L_log_exists=length(strfind(result,'Log.001'))>0;
end