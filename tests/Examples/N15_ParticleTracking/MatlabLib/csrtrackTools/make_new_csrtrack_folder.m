function [] = make_new_csrtrack_folder(old_folder,new_folder)
% make new_folder, copy files (according to liste) from old_folder
global pltfrm

type_cmn=pltfrm{1};   copy_cmn=pltfrm{2};  move_cmn=pltfrm{3};
mkdir_cmn=pltfrm{4};  dir_cmn=pltfrm{5};   del_cmn=pltfrm{6};

[status result]=system([dir_cmn ' ' new_folder]);
if status~=0
    a=old_folder; b=new_folder;
    [status result]=system([mkdir_cmn ' ' b]);
    [status result]=system([copy_cmn ' ' a filesep '*.* ' b]);
    a=[old_folder filesep 'in']; b=[new_folder filesep 'in'];
    [status result]=system([mkdir_cmn ' ' b]);
    [status result]=system([copy_cmn ' ' a filesep '*.* ' b]);
    b=[new_folder filesep 'out'];
    [status result]=system([mkdir_cmn ' ' b]);
else
end