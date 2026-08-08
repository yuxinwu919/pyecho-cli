function [L_sol_exists,name_of_solution] = solution_exists(folder)
% check if solution exists

name_of_solution='undefined';
L_sol_exists=false;
f_in=fopen([folder filesep 'name_of_last_solution.txt'],'rt');
if f_in~=-1
   if feof(f_in)==0
       name_of_solution=fgetl(f_in);
       fclose(f_in);
       f_in=fopen(name_of_solution,'r');
       if f_in~=-1
           L_sol_exists=true;
           fclose(f_in);
       end
   end
end