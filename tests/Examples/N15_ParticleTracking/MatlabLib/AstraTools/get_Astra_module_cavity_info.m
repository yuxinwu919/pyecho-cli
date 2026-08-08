function [cavity_in_module,module_amplitude_phase] = get_Astra_module_cavity_info(Astra_input)
% extract tables: cavity_in_module, module_amplitude_phase


f_in=fopen(Astra_input);
while 1
      Card=fgetl(f_in);
      if ~ischar(Card), break, end
      if length(regexp(Card,'!'))>0
          mm=regexp(Card,'!');m=mm(1);
          card=Card(1:m); card(m:m)=' ';
      else
          card=Card;
      end
      if length(regexpi(card,'Mod_Efield('))>0
          ccard=card;
          mm=regexpi(card,'Mod_Efield(','end');m=mm(1);card(1:m)=' ';
          mm=regexp(card,')');m=mm(1);card(m:m)=' ';
          mm=regexp(card,'=');m=mm(1);card(m:m)=' ';
          ix3=sscanf(card,'%d %f');
          module_amplitude_phase(ix3(1),1)=ix3(2);
          card=ccard;
      end
      if length(regexpi(card,'Mod_Phase('))>0
          ccard=card;
          mm=regexpi(card,'Mod_Phase(','end');m=mm(1);card(1:m)=' ';
          mm=regexp(card,')');m=mm(1);card(m:m)=' ';
          mm=regexp(card,'=');m=mm(1);card(m:m)=' ';
          ix3=sscanf(card,'%d %f');
          module_amplitude_phase(ix3(1),2)=ix3(2);
         card=ccard;
      end
      if length(regexpi(card,'Module('))>0
          ccard=card;
          mm=regexpi(card,'Module(','end');m=mm(1);card(1:m)=' ';
          mm=regexp(card,',');m=mm(1);card(m:m)=' ';
          mm=regexp(card,')','end');m=mm(1);
          i12=sscanf(card(1:m-1),'%d %d');
          mm=regexpi(card,'cavity(','end');m=mm(1);card(1:m)=' ';
          mm=regexp(card,')','end');m=mm(1);
          i3=sscanf(card(1:m-1),'%d');
          cavity_in_module(i3,1)=i12(1);
          cavity_in_module(i3,2)=i12(2);
          card=ccard;
      end
      if length(regexpi(card,'MaxE('))>0
          ccard=card;
          mm=regexpi(card,'MaxE(','end');m=mm(1);card(1:m)=' ';
          mm=regexp(card,')');m=mm(1);card(m:m)=' ';
          mm=regexp(card,'=');m=mm(1);card(m:m)=' ';
          ix3=sscanf(card,'%d %f');
          cavity_in_module(ix3(1),3)=ix3(2);
          card=ccard;
      end
      if length(regexpi(card,'phi('))>0
          ccard=card;
          mm=regexpi(card,'phi(','end');m=mm(1);card(1:m)=' ';
          mm=regexp(card,')');m=mm(1);card(m:m)=' ';
          mm=regexp(card,'=');m=mm(1);card(m:m)=' ';
          ix3=sscanf(card,'%d %f');
          cavity_in_module(ix3(1),4)=ix3(2);
          card=ccard;
      end
      if length(regexpi(card,'c_noscale('))>0
          ccard=card;
          mm=regexpi(card,'c_noscale(','end');m=mm(1);card(1:m)=' ';
          mm=regexp(card,')');m=mm(1);card(m:m)=' ';
          mm=regexp(card,'=');m=mm(1);card(m:m)=' ';
          i3=sscanf(card,'%d');
          if length(regexpi(card,'T'))>0, cavity_in_module(i3,3)=-1; end
          card=ccard;
      end
end
fclose(f_in);

