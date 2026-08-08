function [L_solved] = Astra_folder_solved(WD,pltfrm)
% check if Astra folder solved

type_cmn=pltfrm{1};   copy_cmn=pltfrm{2};  move_cmn=pltfrm{3};
mkdir_cmn=pltfrm{4};  dir_cmn=pltfrm{5};   del_cmn=pltfrm{6};

[status result]=system([dir_cmn ' ' folder]);
if ~(status==0)
   L_solved=false; 
else
   L_solved=length(strfind(result,'Log.001'))>0;
end