function [] = set_Astra_phases(Astra_in,cavity_in_module, ...
                               module_amplitude_phase, ...
                               cavity_auto_phase)
% set phases in astra file
global OS_LINUX

[N_cav,dummy]=size(cavity_auto_phase);
[N_mod,dummy]=size(module_amplitude_phase);
      module_set(1:N_mod)=0;
      module_phase(1:N_mod)=module_amplitude_phase(1:N_mod,2);
      module_auto_phase(1:N_mod)=0;
for n_cav=1:N_cav
    if ~(cavity_in_module(n_cav,3)==-1)
        if cavity_auto_phase(n_cav,3)==1
           mod=cavity_in_module(n_cav,1);
           module_set(mod)=module_set(mod)+1;
           module_auto_phase(mod)=cavity_auto_phase(n_cav,2);
        end
    end
end
% module_set
% module_phase
% module_auto_phase

tfile='mytempfile.txt';
fin=fopen(Astra_in,'rt');
fout=fopen(tfile,'wt');
while feof(fin) == 0,
       line = fgets(fin);
       if length(regexpi(line,'AUTO_PHASE'))>0,
            line=sprintf('%s = %s\n','AUTO_PHASE','.F' ) ;
       end;
       card=line;
       if length(regexpi(card,'Mod_Phase('))>0
           mm=regexpi(card,'Mod_Phase(','end');m=mm(1);card(1:m)=' ';
           mm=regexp(card,')');m=mm(1);card(m:m)=' ';
           mm=regexp(card,'=');m=mm(1);card(m:length(card))=' ';
           mod=sscanf(card,'%d');
           if module_set(mod)>0
               fprintf(fout,'%s',['!' line]);
               line=sprintf('%s\n',[' ' line(1:m) num2str(module_auto_phase(mod)+module_phase(mod))] );
           end
       end          
       fprintf(fout,'%s',line);
end;
fclose(fout);
fclose(fin);
if OS_LINUX, cmd='mv', else cmd='move'; end;
[status result]=system([cmd ' ' tfile ' ' Astra_in]);

