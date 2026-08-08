function [] = make_new_Astra_folder(old_folder,new_folder,pltfrm)
% make new_folder, copy files (according to liste) from old_folder

type_cmn=pltfrm{1};   copy_cmn=pltfrm{2};  move_cmn=pltfrm{3};
mkdir_cmn=pltfrm{4};  dir_cmn=pltfrm{5};   del_cmn=pltfrm{6};

[status result]=system([dir_cmn ' ' new_folder]);
if ~(status==0)
    [status result]=system([mkdir_cmn ' ' new_folder]);
end
if status==0
   f_in = fopen([old_folder filesep 'file_list.dat' ]);
   while 1
      name=fgetl(f_in);
      if ~ischar(name), break, end
      file = [old_folder filesep name];
      [status result]=system([copy_cmn ' ' file ' ' new_folder]);
   end
   fclose(f_in);
end