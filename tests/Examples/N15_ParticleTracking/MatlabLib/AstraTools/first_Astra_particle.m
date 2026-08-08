function [] = first_Astra_particle(in_file,out_file)
% first particle from in_file --> out_file

f_in=fopen(in_file);
f_out=fopen(out_file,'w+');
  card=fgetl(f_in);
  fprintf(f_out,'%s\n',card);
fclose(f_in);
fclose(f_out);