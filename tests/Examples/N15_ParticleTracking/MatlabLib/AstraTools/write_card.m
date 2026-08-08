function [] = write_card(card,fname)
% write "card" into file <fname>
f_out= fopen(fname,'wt+');
fprintf(f_out,'%s\n',card);
fclose(f_out);
